import shutil
import subprocess
from pathlib import Path


def check_gh_installed(coder):
    """Check if the 'gh' CLI tool is installed."""
    if not shutil.which("gh"):
        coder.io.tool_error("`gh` CLI tool not found. Please install it to use /review-pr.")
        coder.io.tool_output("See https://cli.github.com/ for installation instructions.")
        return False
    return True


def get_pr_diff(coder, pr_identifier):
    """Get the diff for a given pull request identifier."""
    try:
        if not coder.repo:
            coder.io.tool_error("Not in a git repository.")
            return None

        # Check for a github remote
        remotes = coder.repo.repo.remotes
        is_github_repo = any("github.com" in remote.url for remote in remotes)
        if not is_github_repo:
            coder.io.tool_error("This does not appear to be a GitHub repository.")
            return None

        command = ["gh", "pr", "diff", pr_identifier]
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, cwd=coder.root
        )

        if result.returncode != 0:
            coder.io.tool_error(f"Error getting diff for PR '{pr_identifier}':")
            coder.io.tool_error(result.stderr)
            return None

        return result.stdout

    except FileNotFoundError:
        # This case is handled by check_gh_installed, but as a fallback
        return None
    except Exception as e:
        coder.io.tool_error(f"An unexpected error occurred while getting PR diff: {e}")
        return None


def cmd_review_pr(coder, args):
    """
    Review a GitHub pull request.
    Usage: /review-pr <pr_number_or_url>
    """
    if not check_gh_installed(coder):
        return

    pr_identifier = args.strip()
    if not pr_identifier:
        coder.io.tool_error("Please provide a PR number or URL.")
        return

    coder.io.tool_output(f"Fetching diff for PR '{pr_identifier}'...")
    diff = get_pr_diff(coder, pr_identifier)

    if diff:
        # Check for a repo-specific checklist
        review_instructions = None
        checklist_path = Path(coder.root) / ".aider" / "pr_review_checklist.md"
        if checklist_path.exists():
            try:
                review_instructions = checklist_path.read_text()
                coder.io.tool_output(
                    "Using custom review checklist from .aider/pr_review_checklist.md"
                )
            except Exception as e:
                coder.io.tool_error(f"Error reading review checklist: {e}")

        if not review_instructions:
            review_instructions = (
                "Look for potential bugs, suggest improvements, and check for adherence to coding"
                " standards."
            )

        coder.io.tool_output("Diff fetched successfully. Asking for review...")
        prompt = (
            f"Please review the following pull request diff for PR '{pr_identifier}'.\n"
            f"{review_instructions}\n\n"
            f"```diff\n{diff}\n```\n"
        )
        return prompt


def register_aider_plugins(commands):
    """Register the /review-pr command."""
    commands.register_command(
        "review-pr",
        cmd_review_pr,
        "Review a GitHub pull request. Usage: /review-pr <pr_number_or_url>",
    )
