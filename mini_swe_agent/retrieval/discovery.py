"""Repository and file discovery component (Step 2.1).

Discovers source files across a repository while safely filtering out
version control metadata, caches, build artifacts, and virtual environments.
"""

import os
from pathlib import Path
from typing import List, Set, Optional


class FileDiscovery:
    """Discovers source and configuration files in a repository workspace."""

    DEFAULT_IGNORE_DIRS: Set[str] = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "build",
        "dist",
        ".egg-info",
        ".idea",
        ".vscode",
        ".tox",
        "coverage",
        "htmlcov",
    }

    DEFAULT_IGNORE_EXTS: Set[str] = {
        ".pyc",
        ".pyo",
        ".pyd",
        ".so",
        ".dll",
        ".dylib",
        ".class",
        ".exe",
        ".bin",
        ".zip",
        ".tar",
        ".gz",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".pdf",
        ".log",
    }

    SUPPORTED_CODE_EXTS: Set[str] = {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".md",
        ".txt",
    }

    def __init__(
        self,
        workspace_dir: str,
        ignore_dirs: Optional[Set[str]] = None,
        ignore_exts: Optional[Set[str]] = None,
        supported_exts: Optional[Set[str]] = None,
    ):
        self.workspace_dir = Path(workspace_dir).resolve()
        if not self.workspace_dir.exists():
            raise FileNotFoundError(f"Workspace directory does not exist: {self.workspace_dir}")

        self.ignore_dirs = ignore_dirs or self.DEFAULT_IGNORE_DIRS
        self.ignore_exts = ignore_exts or self.DEFAULT_IGNORE_EXTS
        self.supported_exts = supported_exts or self.SUPPORTED_CODE_EXTS

    def discover_files(self) -> List[Path]:
        """
        Scan workspace and return a sorted list of relative Paths for all valid source files.
        """
        discovered: List[Path] = []

        for root, dirs, files in os.walk(self.workspace_dir):
            # Prune ignored directories in-place so os.walk does not descend into them
            dirs[:] = [
                d for d in dirs
                if d not in self.ignore_dirs
                and not d.startswith(".")
                and not d.endswith(".egg-info")
            ]

            for file_name in files:
                ext = Path(file_name).suffix.lower()
                if ext in self.ignore_exts:
                    continue
                if self.supported_exts and ext not in self.supported_exts:
                    continue

                abs_path = Path(root) / file_name
                rel_path = abs_path.relative_to(self.workspace_dir)
                discovered.append(rel_path)

        return sorted(discovered)
