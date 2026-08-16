"""仓库内私有文件路径集中管理（全部位于 gitignored 区域）。

路径单点定义：CLI / 测试 / 阶段检测统一通过 QaPaths 引用，
避免字符串散落各处；根目录可注入（测试用 tmp 仓库根）。
"""

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
    def PENDING_SUBMITS(self) -> Path:  # noqa: N802
        return self.root / "secrets" / "pending_submits.json"

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

    # ---- 本地知识库（experience/，gitignored，账户专属不上传）----
    @property
    def EXPERIENCE_DIR(self) -> Path:  # noqa: N802
        return self.root / "experience"

    @property
    def KNOWLEDGE_FIELDS_DIR(self) -> Path:  # noqa: N802
        return self.EXPERIENCE_DIR / "fields"

    @property
    def KNOWLEDGE_FIELDS_JSON(self) -> Path:  # noqa: N802
        return self.KNOWLEDGE_FIELDS_DIR / "fields.json"

    @property
    def KNOWLEDGE_TOP_FIELDS_JSON(self) -> Path:  # noqa: N802
        return self.KNOWLEDGE_FIELDS_DIR / "top_fields.json"

    @property
    def KNOWLEDGE_META_JSON(self) -> Path:  # noqa: N802
        return self.KNOWLEDGE_FIELDS_DIR / "meta.json"

    @property
    def PLAYBOOK(self) -> Path:  # noqa: N802
        return self.EXPERIENCE_DIR / "playbook.md"

    @property
    def FAILURES(self) -> Path:  # noqa: N802
        return self.EXPERIENCE_DIR / "failures.md"
