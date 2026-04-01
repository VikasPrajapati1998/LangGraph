import subprocess
import os
from datetime import datetime
from config import GITHUB_REPO_DIR
from logger import get_logger

# Initialize logger for this module
log = get_logger("GitHub")


def run_git_command(command, repo_dir):
    """Run a git command in the given repository directory."""
    try:
        log.debug(f"Running command: {command}")

        result = subprocess.run(
            command,
            cwd=repo_dir,
            text=True,
            capture_output=True,
            shell=True
        )

        if result.returncode != 0:
            log.error(f"Command failed: {command}")
            log.error(f"Error output: {result.stderr.strip()}")
        else:
            output = result.stdout.strip()
            if output:
                log.info(output)
            log.debug(f"Command succeeded: {command}")

    except Exception as e:
        log.exception(f"Exception while running command: {command}")


def generate_commit_message():
    """Generate default commit message."""
    now = datetime.now()
    return f"Blog {now.strftime('%d-%m-%Y-%H-%M-%S')}"


def auto_git_push(repo_dir, commit_message=None):
    """Automatically add, commit, and push changes."""

    if not os.path.isdir(repo_dir):
        log.error(f"Invalid repository directory: {repo_dir}")
        return

    # Use custom message if provided, else auto-generate
    if not commit_message:
        commit_message = generate_commit_message()

    log.info(f"Starting Git automation")
    log.info(f"Commit message: {commit_message}")

    # Step 1: git add .
    run_git_command("git add .", repo_dir)

    # Step 2: git commit
    run_git_command(f'git commit -m "{commit_message}"', repo_dir)

    # Step 3: git push
    run_git_command("git push origin main", repo_dir)

    log.info("Git automation completed successfully")


if __name__ == "__main__":
    repo_path = GITHUB_REPO_DIR

    # Option 1: Auto message
    auto_git_push(repo_path)

    # Option 2: Custom message
    # auto_git_push(repo_path, commit_message="Blog 30th March 2026")

