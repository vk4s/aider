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
            Document,
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
                return
        except (OSError, Exception):
            if self.verbose:
                self.io.tool_output("Failed to load index from cache, recreating...")
            shutil.rmtree(dname, ignore_errors=True)

        # Create new index
        self.io.tool_output("Indexing codebase for context discovery... (this may take a while)")

        documents = []
        # Use SentenceSplitter to avoid tree_sitter_languages dependency
        splitter = SentenceSplitter(
            chunk_size=1024,
            chunk_overlap=200,
        )

        # Filter files to index
        files_to_index = []
        if fnames:
            files_to_index = fnames
        elif git_root:
            # If no specific files provided, walk the git repo
            # This is a simplified approach; ideally we'd respect .gitignore
            # For now, let's assume fnames are passed from the coder which handles gitignore
            pass

        # If fnames is empty (e.g. first run), we might need to find files.
        # But usually aider is started with files or in a repo.
        # Let's rely on what's passed or available.

        if not files_to_index and git_root:
            for root, dirs, files in os.walk(git_root):
                # Skip hidden dirs
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for file in files:
                    if file.endswith((".py", ".md", ".txt", ".js", ".ts", ".html", ".css")):
                        files_to_index.append(os.path.join(root, file))

        count = 0
        for fname in files_to_index:
            if not os.path.isfile(fname):
                continue

            try:
                content = self.io.read_text(fname)
                if not content:
                    continue

                doc = Document(
                    text=content,
                    metadata=dict(
                        filename=fname,
                        relative_path=os.path.relpath(fname, git_root) if git_root else fname,
                    ),
                )
                documents.append(doc)
                count += 1
            except Exception as e:
                if self.verbose:
                    self.io.tool_warning(f"Failed to index {fname}: {e}")

        if not documents:
            self.io.tool_warning("No documents found to index.")
            return

        self.index = VectorStoreIndex.from_documents(
            documents, transformations=[splitter], show_progress=True
        )

        # Persist
        dname.parent.mkdir(parents=True, exist_ok=True)
        self.index.storage_context.persist(str(dname))
        self.io.tool_output(f"Indexed {count} files.")

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
