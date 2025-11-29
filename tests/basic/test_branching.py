import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from aider.coders import Coder
from aider.commands import Commands
from aider.io import InputOutput


class TestBranching(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.io = InputOutput(pretty=False, yes=True)
        self.main_model = MagicMock()
        self.main_model.edit_format = "diff"
        self.main_model.name = "gpt-4"

        # Mock root to be the test dir
        self.coder = Coder.create(self.main_model, None, self.io)
        self.coder.root = self.test_dir
        self.coder.abs_fnames = set()
        self.coder.abs_read_only_fnames = set()

        # Initialize branch repo manually since create() might have run before we set root
        self.coder.init_branch_repo()

        # Initialize Commands
        self.commands = Commands(self.io, self.coder)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_branching_persistence(self):
        # Initial state
        self.coder.cur_messages = [{"role": "user", "content": "hello"}]
        self.coder.abs_fnames = {str(Path(self.test_dir) / "foo.py")}

        # Create branch 'feature'
        self.coder.save_branch("feature")

        # Verify branch exists in git
        self.assertIn("feature", self.coder.branch_repo.heads)
        self.assertEqual(self.coder.get_current_branch(), "feature")

        # Modify state
        self.coder.cur_messages.append({"role": "assistant", "content": "hi"})
        self.coder.abs_fnames.add(str(Path(self.test_dir) / "bar.py"))

        # Checkout default branch (usually main or master)
        default_branch = "main" if "main" in self.coder.branch_repo.heads else "master"
        self.coder.checkout_branch(default_branch)
        self.assertEqual(self.coder.get_current_branch(), default_branch)

        # Verify persistence when switching back
        self.coder.checkout_branch("feature")
        self.assertEqual(len(self.coder.cur_messages), 2)
        self.assertIn(str(Path(self.test_dir) / "bar.py"), self.coder.abs_fnames)

    def test_list_branches(self):
        self.coder.save_branch("b1")
        self.coder.save_branch("b2")
        branches = self.coder.list_branches()
        self.assertIn("b1", branches)
        self.assertIn("b2", branches)
        default_branch = "main" if "main" in self.coder.branch_repo.heads else "master"
        self.assertIn(default_branch, branches)

    def test_branch_diff(self):
        # Create branch b1
        self.coder.save_branch("b1")
        self.coder.cur_messages = [{"role": "user", "content": "msg1"}]
        self.coder.save_branch()  # Save state to b1

        # Create branch b2
        self.coder.save_branch("b2")
        self.coder.cur_messages = [{"role": "user", "content": "msg2"}]
        self.coder.save_branch()  # Save state to b2

        # Diff b1 against b2 (current)
        diff = self.coder.branch_diff("b1")
        self.assertIn("state.json", diff)
        self.assertIn("chat_history.md", diff)

    def test_branch_subcommands(self):
        # Test /branch checkout
        self.commands.cmd_branch("b1")  # Create b1
        self.commands.cmd_branch("b2")  # Create b2

        self.commands.cmd_branch("checkout b1")
        self.assertEqual(self.coder.get_current_branch(), "b1")

        # Test /branch list (just ensure no error)
        self.commands.cmd_branch("list")

        # Test /branch diff
        self.commands.cmd_branch("diff b2")

        # Test /branch delete
        self.commands.cmd_branch("delete b2")
        branches = self.coder.list_branches()
        self.assertNotIn("b2", branches)


if __name__ == "__main__":
    unittest.main()
