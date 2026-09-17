"""Analysed repositories, pinned commits and corpus definitions.

Every other script imports this module; it is the single place where the
analysed commits and the "main sources" rule are defined.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTERNAL = ROOT / "external"


@dataclass(frozen=True)
class Repo:
    slug: str  # owner/name on GitHub
    commit: str  # pinned HEAD at clone time

    @property
    def url(self) -> str:
        return f"https://github.com/{self.slug}.git"

    @property
    def dir(self) -> Path:
        return EXTERNAL / self.slug.replace("/", "__")


REPOS = {
    "api": Repo("bpm-crafters/process-engine-api", "b02569855596de4fb423dc181489e72595235503"),
    "adapter": Repo("bpm-crafters/process-engine-adapters-camunda-7", "d2be36eca2edf24d1e1a43540cee77d9e9dffd21"),
    "examples": Repo("camunda/camunda-bpm-examples", "6c7f4c4adb4beb9a2f5d4c5e49fc1ddfc6dab3fc"),
    "consulting": Repo("camunda-consulting/code", "c9ef30b62a47a7063c077397cb3340b28fb4cc3c"),
}
CLONE_DATE = "2026-09-17"


@dataclass(frozen=True)
class Corpus:
    """A set of Camunda 7 main-source Java files inside one repository."""

    name: str
    repo: Repo
    # Folders that are not Camunda 7 content (C8 / Zeebe).
    exclude_prefixes: tuple[str, ...] = field(default=())

    def tracked_java(self) -> list[str]:
        out = subprocess.run(
            ["git", "-C", str(self.repo.dir), "ls-files", "-z", "*.java"],
            capture_output=True, text=True, check=True,
        ).stdout
        return sorted(p for p in out.split("\0") if p)

    def main_java(self) -> list[str]:
        """Main sources: Maven/Gradle `src/main/` layout, C8 folders excluded.

        Every tracked .java file in both repositories is under `src/main/` or
        `src/test/`, except one Maven wrapper helper (`.mvn/wrapper/`), which
        this rule drops.
        """
        return [
            p for p in self.tracked_java()
            if "/src/main/" in f"/{p}" and not p.startswith(self.exclude_prefixes)
        ]

    def draft_rule_java(self) -> list[str]:
        """The rule the draft used: any .java path not containing `/test/`."""
        return [p for p in self.tracked_java() if "/test/" not in p.lower()]


CORPORA = [
    Corpus("examples", REPOS["examples"]),
    # snippets/reverse-adapter is a Camunda 8 (Zeebe job worker) bridge.
    Corpus("consulting", REPOS["consulting"], exclude_prefixes=("snippets/reverse-adapter/",)),
]
