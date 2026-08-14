from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 让 `qa` 包可直接导入（未安装时）
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def tmp_qa(tmp_path: Path) -> Path:
    """构造带标准子目录的临时仓库根。"""
    (tmp_path / "secrets").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "audit").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports" / "daily").mkdir(parents=True, exist_ok=True)
    return tmp_path
