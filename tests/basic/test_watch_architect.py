from pathlib import Path

from aider.io import InputOutput
from aider.watch import FileWatcher
from aider.watch_prompts import watch_architect_prompt


class MinimalCoder:
    def __init__(self, io):
        self.io = io
        self.root = "."
        self.abs_fnames = set()

    def get_rel_fname(self, fname):
        return fname


def test_architect_trigger_with_ai_at():
    io = InputOutput(pretty=False, fancy_input=False, yes=False)
    coder = MinimalCoder(io)
    watcher = FileWatcher(coder)

    import tempfile

    with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False) as tf:
        tf.write("# ai@ propose refactor\n")
        tf.flush()
        tmp_path = str(Path(tf.name))

    try:
        lines, comments, action = watcher.get_ai_comments(tmp_path)
        assert action == "@"
        assert len(lines) >= 1

        watcher.changed_files = {tmp_path}
        cmd = watcher.process_changes()
        assert cmd.strip().startswith(watch_architect_prompt.strip().splitlines()[0])
    finally:
        Path(tmp_path).unlink()