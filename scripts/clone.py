"""Shallow-clone the analysed repositories into external/ at the pinned commits.

    python scripts/clone.py            # pinned commits from scripts/repos.py
    python scripts/clone.py --latest   # default-branch HEAD; prints the new hashes
"""
from __future__ import annotations

import argparse
import subprocess

from repos import EXTERNAL, REPOS


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", action="store_true", help="fetch default-branch HEAD instead of the pinned commit")
    latest = ap.parse_args().latest

    EXTERNAL.mkdir(exist_ok=True)
    for repo in REPOS.values():
        d = str(repo.dir)
        if not (repo.dir / ".git").exists():
            git("init", "-q", d)
            git("-C", d, "config", "core.longpaths", "true")  # Windows: deep snippet paths
            git("-C", d, "remote", "add", "origin", repo.url)
        target = "HEAD" if latest else repo.commit
        if not latest and repo.dir.joinpath(".git").exists():
            try:
                if git("-C", d, "rev-parse", "HEAD") == repo.commit:
                    print(f"{repo.slug:50s} {repo.commit} (already present)")
                    continue
            except subprocess.CalledProcessError:
                pass  # empty repository, nothing checked out yet
        git("-C", d, "fetch", "-q", "--depth", "1", "origin", target)
        git("-C", d, "checkout", "-q", "--detach", "FETCH_HEAD")
        head = git("-C", d, "rev-parse", "HEAD")
        note = "" if head == repo.commit else "  <-- differs from pinned commit in scripts/repos.py"
        print(f"{repo.slug:50s} {head}{note}")


if __name__ == "__main__":
    main()
