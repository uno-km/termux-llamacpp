import os
import subprocess
from pathlib import Path

root = Path(r"c:\Users\GAME\Desktop\uno-km\dev")

print(f"{'Directory':<30} {'Has .git':<10} {'Remote Origin URL'}")
print("-" * 80)

for item in sorted(root.iterdir()):
    if item.is_dir():
        git_dir = item / ".git"
        has_git = "YES" if git_dir.exists() else "NO"
        remote_url = "None"
        if git_dir.exists():
            res = subprocess.run(["git", "remote", "get-url", "origin"], cwd=str(item), capture_output=True, text=True)
            if res.returncode == 0:
                remote_url = res.stdout.strip()
            else:
                remotes = subprocess.run(["git", "remote", "-v"], cwd=str(item), capture_output=True, text=True)
                remote_url = remotes.stdout.strip().replace("\n", " | ") if remotes.stdout.strip() else "No Remote Configured"
        print(f"{item.name:<30} {has_git:<10} {remote_url}")
