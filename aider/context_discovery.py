import os
import shutil
import warnings
from pathlib import Path

from aider import utils

# Suppress warnings from llama_index
warnings.simplefilter("ignore", category=FutureWarning)


class ContextDiscoverer:
    def __init__(self, io, verbose=False):
        self.io = io
        self.verbose = verbose
        self.index = None
        self.retriever = None

        try:
            from llama_index.core import Settings
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding

            # Configure settings
            os.environ["TOKENIZERS_PARALLELISM"] = "true"
            Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

        except ImportError:
            # Dependencies will be checked before use
            pass

    def ensure_dependencies(self):
        pip_install_cmd = [
            "aider-chat[help]",
            "--extra-index-url",
            "https://download.pytorch.org/whl/cpu",
        ]
        return utils.check_pip_install_extra(
            self.io,
            "llama_index.embeddings.huggingface",
            "To use /discover you need to install the help extras",
            pip_install_cmd,
        )

    def get_cache_dir(self, git_root):
        if not git_root:
            # Fallback for non-git usage, though less ideal
            git_root = os.getcwd()

        # Create a hash of the git root path to separate caches per repo
        import hashlib

        repo_hash = hashlib.md5(str(git_root).encode()).hexdigest()

        # No version in path - preserve index across aider updates
        return Path.home() / ".aider" / "caches" / "context_discovery" / repo_hash

    def load_or_create_index(self, fnames, git_root):
        from llama_index.core import (
            StorageContext,
            VectorStoreIndex,
            load_index_from_storage,
        )
        from llama_index.core.node_parser import SentenceSplitter

        dname = self.get_cache_dir(git_root)

        # Try to load existing index
        try:
            if dname.exists():
                storage_context = StorageContext.from_defaults(persist_dir=str(dname))
                self.index = load_index_from_storage(storage_context)
                if self.verbose:
                    self.io.tool_output("Loaded context index from cache.")
        except (OSError, Exception):
            if self.verbose:
                self.io.tool_output("Failed to load index from cache, recreating...")
            shutil.rmtree(dname, ignore_errors=True)

        # If no index loaded, create an empty one
        if not self.index:
            self.io.tool_output("Creating new context index...")
            splitter = SentenceSplitter(
                chunk_size=1024,
                chunk_overlap=200,
            )
            self.index = VectorStoreIndex.from_documents([], transformations=[splitter])

        # Refresh the index (incremental update)
        self.refresh_index(fnames, git_root)

    def refresh_index(self, fnames, git_root):
        from llama_index.core import Document

        if not fnames:
            return

        # Get existing docs info
        # ref_doc_info maps doc_id (which we set to fname) to metadata
        existing_docs = self.index.ref_doc_info if self.index.ref_doc_info else {}

        # Identify changes
        current_fnames = set(fnames)
        existing_fnames = set(existing_docs.keys())

        new_files = current_fnames - existing_fnames
        deleted_files = existing_fnames - current_fnames
        modified_files = []

        for fname in current_fnames.intersection(existing_fnames):
            if not os.path.isfile(fname):
                continue

            current_mtime = os.path.getmtime(fname)
            # Check stored mtime
            # ref_doc_info[fname] is a RefDocInfo object, accessing metadata attribute
            doc_info = existing_docs[fname]
            stored_mtime = doc_info.metadata.get("mtime", 0) if doc_info.metadata else 0

            if current_mtime > stored_mtime:
                modified_files.append(fname)

        if not new_files and not deleted_files and not modified_files:
            if self.verbose:
                self.io.tool_output("Context index is up to date.")
            return

        self.io.tool_output(
            f"Updating context index: {len(new_files)} new, {len(modified_files)} modified,"
            f" {len(deleted_files)} deleted."
        )

        # Process deletions
        for fname in deleted_files:
            self.index.delete_ref_doc(fname, delete_from_docstore=True)

        # Process additions and updates
        files_to_index = list(new_files) + modified_files

        # For modified files, we need to delete them first to avoid duplicates?
        # insert() usually appends. delete_ref_doc handles cleanup of old nodes.
        for fname in modified_files:
            self.index.delete_ref_doc(fname, delete_from_docstore=True)

        count = 0
        if not files_to_index and git_root:
            # Load .aiderignore patterns if present
            ignore_patterns = []
            ignore_file = Path(git_root) / ".aiderignore"
            if ignore_file.exists():
                try:
                    ignore_patterns = [
                        line.strip()
                        for line in ignore_file.read_text().splitlines()
                        if line.strip() and not line.startswith("#")
                    ]
                except Exception:
                    pass

            import fnmatch

            for root, dirs, files in os.walk(git_root):
                # Skip hidden dirs
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for file in files:
                    fname = os.path.join(root, file)
                    rel_fname = os.path.relpath(fname, git_root)

                    # Check against ignore patterns
                    if any(fnmatch.fnmatch(rel_fname, pat) for pat in ignore_patterns):
                        continue

                    # Skip common binary/large file extensions
                    if file.endswith(
                        (
                            ".DS_Store",
                            ".woff2",
                            ".ico",
                            ".png",
                            ".jpg",
                            ".jpeg",
                            ".gif",
                            ".pdf",
                            ".zip",
                            ".tar",
                            ".gz",
                        )
                    ):
                        continue

                    # Skip files that are likely binary or too large
                    try:
                        if os.path.getsize(fname) > 1024 * 1024:  # Skip files larger than 1MB
                            continue
                    except OSError:
                        continue

                    files_to_index.append(fname)

        for fname in files_to_index:
            if not os.path.isfile(fname):
                continue

            try:
                # Check for binary content by reading first chunk
                with open(fname, "rb") as f:
                    chunk = f.read(1024)
                    if b"\0" in chunk:
                        continue

                content = self.io.read_text(fname)
                if not content:
                    continue

                mtime = os.path.getmtime(fname)
                doc = Document(
                    text=content,
                    doc_id=fname,  # Use absolute path as ID for tracking
                    metadata=dict(
                        filename=fname,
                        relative_path=os.path.relpath(fname, git_root) if git_root else fname,
                        mtime=mtime,
                    ),
                )
                self.index.insert(doc)
                count += 1
            except Exception as e:
                if self.verbose:
                    self.io.tool_warning(f"Failed to index {fname}: {e}")

        # Persist
        dname = self.get_cache_dir(git_root)
        dname.parent.mkdir(parents=True, exist_ok=True)
        self.index.storage_context.persist(str(dname))

        if count > 0 or deleted_files:
            self.io.tool_output("Index updated.")

    def query(self, query_text, top_k=5):
        if not self.index:
            return []

        if not self.retriever:
            self.retriever = self.index.as_retriever(similarity_top_k=top_k)

        nodes = self.retriever.retrieve(query_text)

        results = []
        for node in nodes:
            results.append(
                {
                    "file": node.metadata.get("relative_path", node.metadata.get("filename")),
                    "score": node.score,
                    "text": node.text,
                    "node": node,
                }
            )

        return results
