---
parent: Usage
nav_order: 55
description: Use semantic search to find relevant files and add them to the chat.
---

# Context Discovery

Aider's Context Discovery feature helps you find relevant code in your repository using semantic search. This is useful when you're not sure which files contain the code you need to modify or reference.

## Usage

You can use the `/discover` command to search for relevant code.

```bash
/discover <query>
```

For example:

```bash
/discover authentication logic
```

Aider will search your codebase and present a ranked list of relevant files with relevance scores.

### Auto-Adding Files

If you want to automatically add the discovered files to the chat, use the `--add` (or `-a`) flag:

```bash
/discover authentication logic --add
```

### Limiting Results

By default, `/discover` shows the top 5 results. You can change this with the `--limit` (or `-l`) flag:

```bash
/discover authentication logic --limit 3
```

### Refreshing the Index

Aider maintains a local cache of your codebase's embeddings to make searches fast. It automatically detects file changes and updates the index incrementally.

If you want to force a re-scan of the codebase, you can use the `--refresh` (or `-r`) flag:

```bash
/discover authentication logic --refresh
```

## Configuration

### Ignoring Files

You can exclude specific files or directories from being indexed by creating a `.aiderignore` file in the root of your git repository. The syntax is similar to `.gitignore`.

Example `.aiderignore`:
```gitignore
# Ignore secret test files
aider/secret_test.py

# Ignore large data directories
data/
```

By default, aider also ignores:
- Hidden directories (starting with `.`)
- Common binary file extensions (`.png`, `.jpg`, `.pdf`, etc.)
- Files larger than 1MB

## How it Works

1.  **Indexing**: Aider chunks your code into semantically meaningful parts and generates embeddings using a local model (`BAAI/bge-small-en-v1.5`).
2.  **Storage**: The embeddings are stored locally in `~/.aider/caches/context_discovery/`. The cache is scoped by repository, so you can switch between projects without conflicts.
3.  **Privacy**: Everything runs locally on your machine. Your code is not sent to any external service for indexing.
