from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class QaPaths:
    """仓库内所有私有文件路径（gitignored 区域）。"""

    root: Path = field(default_factory=Path.cwd)

    @property
    def COOKIE(self) -> Path:  # noqa: N802 - 常量风格
        return self.root / "secrets" / "worldquant_cookies.txt"

    @property
    def ACCOUNT_INFO(self) -> Path:  # noqa: N802
        return self.root / "secrets" / "account_info.json"

    @property
    def DB(self) -> Path:  # noqa: N802
        return self.root / "data" / "qa.db"

    @property
    def AUDIT_DIR(self) -> Path:  # noqa: N802
        return self.root / "data" / "audit"

    @property
    def REPORTS_DIR(self) -> Path:  # noqa: N802
        return self.root / "reports"

    @property
    def CANDIDATES_DIR(self) -> Path:  # noqa: N802
        return self.root / "data" / "candidates"
