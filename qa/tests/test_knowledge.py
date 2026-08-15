"""knowledge 模块单测：本地知识库构建/读取/经验沉淀（mock HTTP，不真调 API）。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from qa import knowledge
from qa.knowledge import KnowledgeMissingError
from qa.paths import QaPaths


class FakeClient:
    """mock BrainClient.get_json：按路径/参数返回分页数据（{results, count} 形态）。"""

    def __init__(self, datasets: list[str], fields_by_dataset: dict[str, list[dict]]):
        self.datasets = datasets
        self.fields_by_dataset = fields_by_dataset
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get_json(self, path: str, params: dict[str, Any] | None = None):
        self.calls.append((path, params))
        if path == "/data-sets":
            offset = params.get("offset", 0) if params else 0
            page = self.datasets[offset : offset + 50]
            return {"results": [{"id": d} for d in page], "count": len(self.datasets)}
        if path == "/data-fields":
            ds = params.get("dataset.id", "") if params else ""
            offset = params.get("offset", 0) if params else 0
            fields = self.fields_by_dataset.get(ds, [])
            return {"results": fields[offset : offset + 50], "count": len(fields)}
        raise AssertionError(f"unexpected path {path}")


class ListClient(FakeClient):
    """裸数组形态响应（防御解析覆盖）。"""

    def get_json(self, path: str, params: dict[str, Any] | None = None):
        self.calls.append((path, params))
        if path == "/data-sets":
            return [{"id": d} for d in self.datasets]
        if path == "/data-fields":
            ds = params.get("dataset.id", "") if params else ""
            return self.fields_by_dataset.get(ds, [])
        raise AssertionError(f"unexpected path {path}")


def _field(fid: str, ds: str, uc: int) -> dict:
    return {
        "id": fid,
        "description": f"desc of {fid}",
        "type": "MATRIX",
        "coverage": 0.8,
        "userCount": uc,
    }


def _make_client() -> FakeClient:
    pv = [_field(f"pv1_f{i:03d}", "pv1", 100 + i) for i in range(60)]  # 60 → 触发分页
    fnd = [_field("fnd_roe", "fnd6", 500), _field("fnd_cfoe", "fnd6", 300)]
    return FakeClient(["pv1", "fnd6"], {"pv1": pv, "fnd6": fnd})


@pytest.fixture
def seeded(tmp_path):
    """已构建本地知识库的临时仓库根。"""
    paths = QaPaths(tmp_path)
    client = _make_client()
    meta = knowledge.build_local_knowledge(
        paths, client, ["USA"], pace=0.0, callback=None
    )
    return paths, client, meta


# ---- 构建 ----

def test_build_writes_fields_json(seeded):
    paths, _, _ = seeded
    assert paths.KNOWLEDGE_FIELDS_JSON.exists()
    data = json.loads(paths.KNOWLEDGE_FIELDS_JSON.read_text(encoding="utf-8"))
    assert len(data) == 62  # 60 + 2
    ids = {f["id"] for f in data}
    assert "pv1_f000" in ids and "fnd_roe" in ids
    # 精简字段结构
    sample = data[0]
    assert set(sample) == {"id", "description", "dataset", "type", "coverage", "userCount"}


def test_build_paginates_fields(seeded):
    paths, client, meta = seeded
    field_calls = [(p, pa) for p, pa in client.calls if p == "/data-fields"]
    offsets = {pa.get("offset") for _, pa in field_calls}
    assert 0 in offsets and 50 in offsets  # 60 字段触发第二页


def test_fetch_fields_params_include_instrument_type(seeded):
    """实测：/data-fields 必须带 instrumentType 参数，否则 400 Invalid query。"""
    paths, client, meta = seeded
    field_calls = [(p, pa) for p, pa in client.calls if p == "/data-fields"]
    assert field_calls
    for _, params in field_calls:
        assert params.get("instrumentType") == "EQUITY"
        assert params.get("dataset.id") in ("pv1", "fnd6")


def test_build_writes_top_fields_per_dataset(seeded):
    paths, _, _ = seeded
    data = json.loads(paths.KNOWLEDGE_TOP_FIELDS_JSON.read_text(encoding="utf-8"))
    by_ds: dict[str, list[dict]] = {}
    for f in data:
        by_ds.setdefault(f["dataset"], []).append(f)
    assert len(by_ds["pv1"]) == 15  # 60 中取 top15
    assert len(by_ds["fnd6"]) == 2  # 不足 15 全保留
    # userCount 降序
    ucs = [f["userCount"] for f in by_ds["pv1"]]
    assert ucs == sorted(ucs, reverse=True)


def test_build_writes_meta(seeded):
    paths, client, meta = seeded
    stored = json.loads(paths.KNOWLEDGE_META_JSON.read_text(encoding="utf-8"))
    assert stored["field_count"] == 62
    assert stored["dataset_count"] == 2
    assert stored["regions"] == ["USA"]
    assert stored["generated_at"]


def test_build_handles_plain_list_response(tmp_path):
    paths = QaPaths(tmp_path)
    client = ListClient(["pv1"], {"pv1": [_field("close", "pv1", 10)]})
    meta = knowledge.build_local_knowledge(
        paths, client, ["USA"], pace=0.0, callback=None
    )
    assert meta["field_count"] == 1
    assert knowledge.load_field_ids(paths) == {"close"}


def test_build_skips_invalid_field_entries(tmp_path):
    paths = QaPaths(tmp_path)
    client = FakeClient(["pv1"], {"pv1": [_field("ok", "pv1", 1), {"junk": True}]})
    knowledge.build_local_knowledge(paths, client, ["USA"], pace=0.0, callback=None)
    assert knowledge.load_field_ids(paths) == {"ok"}


# ---- 读取 ----

def test_load_field_ids_returns_set(seeded):
    paths, _, _ = seeded
    ids = knowledge.load_field_ids(paths)
    assert isinstance(ids, set)
    assert "pv1_f000" in ids


def test_load_field_ids_missing_raises(tmp_path):
    paths = QaPaths(tmp_path)
    with pytest.raises(KnowledgeMissingError):
        knowledge.load_field_ids(paths)


def test_load_fields_returns_ids_and_types(seeded):
    """v1.4.1：字段白名单 + 类型映射（validate 类型检查的数据源）。"""
    paths, _, _ = seeded
    ids, types = knowledge.load_fields(paths)
    assert "pv1_f000" in ids
    assert types.get("pv1_f000") == "MATRIX"
    assert set(types) == ids


def test_knowledge_status_meta_or_none(seeded, tmp_path):
    paths, _, _ = seeded
    assert knowledge.knowledge_status(paths) is not None
    assert knowledge.knowledge_status(QaPaths(tmp_path / "empty")) is None


# ---- 经验沉淀 ----

def test_ensure_templates_creates_playbook_and_failures(tmp_path):
    paths = QaPaths(tmp_path)
    knowledge.ensure_experience_templates(paths)
    assert paths.PLAYBOOK.exists()
    assert paths.FAILURES.exists()
    assert "Playbook" in paths.PLAYBOOK.read_text(encoding="utf-8")


def test_append_lesson_dedupes_by_id(seeded):
    paths, _, _ = seeded
    knowledge.append_experience(
        paths, "lesson", "h1", "盈利质量有效", "- 假设: ROE 双确认\n- 结论: 有效"
    )
    knowledge.append_experience(
        paths, "lesson", "h1", "盈利质量有效", "- 假设: ROE 双确认\n- 结论: 有效"
    )
    text = paths.PLAYBOOK.read_text(encoding="utf-8")
    assert text.count("盈利质量有效") == 1
    assert "h1" in text


def test_append_failure(seeded):
    paths, _, _ = seeded
    knowledge.append_experience(paths, "failure", "h2", "杠杆信号无效", "- 原因: Sharpe 0.5")
    text = paths.FAILURES.read_text(encoding="utf-8")
    assert "杠杆信号无效" in text
    assert "h2" in text


def test_restore_templates_removes_entries(seeded):
    paths, _, _ = seeded
    knowledge.append_experience(paths, "lesson", "h1", "某经验", "内容")
    knowledge.restore_experience_templates(paths)
    text = paths.PLAYBOOK.read_text(encoding="utf-8")
    assert "某经验" not in text
    assert "Playbook" in text
