import os
import fnmatch

IGNORE_NAMES = ["__pycache__", "_*", "__*", ".git", "logs", "output", "node_modules", "dir.py"]

def should_ignore(name):
    """Check if a file/folder should be ignored based on patterns."""
    for pattern in IGNORE_NAMES:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False

def explain_directory(path, indent=""):
    if not os.path.exists(path):
        print(f"Path '{path}' does not exist.")
        return
    
    if not os.path.isdir(path):
        print(f"Path '{path}' is not a directory.")
        return

    entries = os.listdir(path)

    # Filter ignored names
    entries = [e for e in entries if not should_ignore(e)]

    for i, entry in enumerate(entries):
        entry_path = os.path.join(path, entry)
        is_last = i == len(entries) - 1
        prefix = "└── " if is_last else "├── "

        if os.path.isdir(entry_path):
            print(f"{indent}{prefix}[DIR] {entry}")
            # Skip entire subtree if ignored (extra safety)
            if not should_ignore(entry):
                explain_directory(entry_path, indent + ("    " if is_last else "│   "))
        else:
            size = os.path.getsize(entry_path)
            print(f"{indent}{prefix}[FILE] {entry} ({size} bytes)")

if __name__ == "__main__":
    # dir_path = r"D:\Study\LangGraph\Workflow_27_BlogWriter\Frontend"
    dir_path = r"D:\Study\LangGraph\Workflow_27_BlogWriter\Backend\Blogs"
    print(f"Directory tree for: {dir_path}\n")
    explain_directory(dir_path)
