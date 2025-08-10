import os
import subprocess
import sys
import re

def get_changed_files(base_sha, head_sha, folder):
    result = subprocess.run([
        "git", "diff", "--name-only", f"{base_sha}..{head_sha}", "--", folder
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"Error getting changed files: {result.stderr}")
        sys.exit(1)
    return [f for f in result.stdout.splitlines() if f]

def get_version_from_file(commit_sha, file_path):
    result = subprocess.run([
        "git", "show", f"{commit_sha}:{file_path}"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"Error reading {file_path} at {commit_sha}: {result.stderr}")
        sys.exit(1)
    match = re.search(r'__version__\s*=\s*"([^"]+)"', result.stdout)
    if not match:
        print(f"Could not find __version__ in {file_path} at {commit_sha}")
        sys.exit(1)
    return match.group(1)

def main():
    # Get base and head refs from environment variables set by GitHub Actions
    base_sha = os.environ.get("GITHUB_EVENT_BEFORE", "origin/main")
    head_sha = os.environ.get("GITHUB_SHA", "HEAD")
    folder = sys.argv[1] if len(sys.argv) > 1 else "discord-bot/bot/"
    version_file = os.path.join(folder, "version.py")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    def print_and_summary(msg):
        print(msg)
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")

    changed_files = get_changed_files(base_sha, head_sha, folder)
    if not changed_files:
        print_and_summary(f"✅ No files changed in {folder}. Skipping version check.")
        sys.exit(0)

    base_version = get_version_from_file(base_sha, version_file)
    head_version = get_version_from_file(head_sha, version_file)

    print_and_summary(f"Base Version: ![base](https://img.shields.io/badge/version-{base_version}-blue)")
    print_and_summary(f"Head Version: ![head](https://img.shields.io/badge/version-{head_version}-blue)")
    if base_version == head_version:
        print_and_summary("❌ version.py was not incremented.")
        sys.exit(1)
    print_and_summary(f"✅ version.py incremented: {base_version} -> {head_version}")
    sys.exit(0)

if __name__ == "__main__":
    main()
