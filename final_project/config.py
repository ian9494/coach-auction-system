"""Side-effect-free local configuration. Never reads production data or secrets.

Paths are rooted at this checkout, not the caller's working directory.
Configuration loading does not create directories, open a DB, or start a server.
"""

from dataclasses import dataclass
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ProjectConfig:
    host: str = "127.0.0.1"
    port: int = 3001
    runtime_dir: str = "runtime/final_project"
    sqlite_file: str = "runtime/final_project/auction.sqlite3"
    coach_file: str = "examples/final_project/coach.csv"
    member_file: str = "examples/final_project/member.csv"
    # Explicit test isolation root; never read from the example JSON.
    project_root: Path = PROJECT_ROOT

    def __post_init__(self) -> None:
        if type(self.port) is not int or not 1 <= self.port <= 65535 or self.port == 3000:
            raise ValueError("Use a valid dedicated project port, never production port 3000")
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("host must be a non-empty string")
        self._within(self.runtime_dir, "runtime/final_project", allow_equal=True)
        self._within(self.sqlite_file, self.runtime_dir)
        if self.path(self.sqlite_file).suffix != ".sqlite3":
            raise ValueError("sqlite_file must have .sqlite3 extension")
        self._within(self.coach_file, "examples/final_project")
        self._within(self.member_file, "examples/final_project")

    def path(self, relative: str) -> Path:
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("Project paths must be relative without parent traversal")
        root = self.project_root.resolve()
        resolved = (root / relative).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("Project path escapes this checkout")
        if resolved.is_relative_to((root / "data").resolve()):
            raise ValueError("Final project paths must never target production data")
        return resolved

    def _within(self, relative: str, allowed: str, *, allow_equal: bool = False) -> None:
        target = self.path(relative)
        base = self.path(allowed)
        if not target.is_relative_to(base) or (target == base and not allow_equal):
            raise ValueError(f"Path must be inside {allowed}")


def load_config(path: Path | None = None) -> ProjectConfig:
    """Load an explicitly supplied project JSON, or return isolated defaults.

Unknown fields are rejected by the dataclass constructor. No .env auto-loading.
"""
    if path is None:
        return ProjectConfig()
    values = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(values, dict):
        raise ValueError("Configuration must be a JSON object")
    if "project_root" in values:
        raise ValueError("project_root is only an explicit test constructor option")
    return ProjectConfig(**values)
