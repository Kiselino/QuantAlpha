"""本地知识库管理（账户专属，gitignored，不上传公开仓库）。

知识库拆分（v1.4）：
- 公开（knowledge/）：operators / rules / pitfalls —— 平台公开文档，随仓库分发
- 本地（experience/）：字段元数据 + playbook / failures —— 按账户权限生成、
  经验沉淀，全部位于 gitignored 的 experience/，克隆者不会拿到。

字段元数据抓取走 BRAIN API（/data-sets + /data-fields，设计 §12 实测备忘），
按账户阶段（用户=USA / 顾问=12 区域）动态决定区域范围。
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Callable

from qa.paths import QaPaths

BASE_PACE_SECONDS = 2.1  # 30 req/min 限流下的安全间隔（分钟配额实测）

_PLAYBOOK_TEMPLATE = (
    "# 经验 Playbook（本地，不上传）\n"
    "\n"
    "> 从每次 alpha 的研究/模拟/提交中沉淀的可复用经验（脱敏方法论）。\n"
    "> 由 `qa run` / `qa submit` 自动追加；手动沉淀可直接编辑本文件。\n"
    "\n"
    "## 格式\n"
    "\n"
    "每条经验：触发条件 → 假设 → 结论。\n"
)

_FAILURES_TEMPLATE = (
    "# 证伪库（本地，不上传）\n"
    "\n"
    "> 已证伪方向（模拟未过/提交被拒/相关门饱和），避免 agent 重复走死路。\n"
    "> 由 `qa run` / `qa submit` 自动追加。\n"
)

_FIELD_KEYS = ("id", "description", "dataset", "type", "coverage", "userCount")


class KnowledgeMissingError(FileNotFoundError):
    """本地知识库未生成（首次运行需先 `qa update-knowledge`）。"""


# ---- 构建 ----


def _page_items(payload: Any) -> list[dict]:
    """防御解析分页响应：{results:[...]} 与裸数组两种形态。"""
    if isinstance(payload, dict):
        return payload.get("results") or []
    return payload or []


def _paged_results(
    client: Any, path: str, base_params: dict[str, Any]
) -> list[dict[str, Any]]:
    """分页拉取全部 items（limit=50 offset 翻页；{results:[]} 与裸数组均支持）。"""
    items: list[dict[str, Any]] = []
    offset = 0
    limit = 50
    while True:
        payload = client.get_json(
            path, params={**base_params, "limit": limit, "offset": offset}
        )
        page = _page_items(payload)
        items.extend(it for it in page if isinstance(it, dict))
        if len(page) < limit:
            break
        offset += limit
    return items


def fetch_dataset_ids(
    client: Any, region: str, callback: Callable[[str], None] | None = None
) -> list[str]:
    """分页拉取区域数据集 id 列表。"""
    return [
        it["id"]
        for it in _paged_results(
            client,
            "/data-sets",
            {
                "region": region,
                "universe": "TOP3000",
                "delay": 1,
                "instrumentType": "EQUITY",
            },
        )
        if it.get("id")
    ]


def fetch_dataset_fields(
    client: Any, dataset_id: str, region: str
) -> list[dict[str, Any]]:
    """分页拉取单数据集全部字段元数据（精简字段集）。"""
    return [
        {k: it.get(k) for k in _FIELD_KEYS if k != "dataset"} | {"dataset": dataset_id}
        for it in _paged_results(
            client,
            "/data-fields",
            {
                "dataset.id": dataset_id,  # 实测参数名是点号写法
                "region": region,
                "delay": 1,
                "universe": "TOP3000",
                "instrumentType": "EQUITY",  # 实测必带，缺失返回 400 Invalid query
            },
        )
        if it.get("id")
    ]


def _user_count(f: dict[str, Any]) -> int | float:
    v = f.get("userCount")
    return v if isinstance(v, (int, float)) else 0


def _top_fields(all_fields: list[dict[str, Any]], n: int = 15) -> list[dict[str, Any]]:
    """每数据集按 userCount 取 top N（缺失视为 0），供 agent 生成时参考。"""
    by_ds: dict[str, list[dict[str, Any]]] = {}
    for f in all_fields:
        by_ds.setdefault(f["dataset"], []).append(f)
    out: list[dict[str, Any]] = []
    for ds in sorted(by_ds):
        ranked = sorted(by_ds[ds], key=_user_count, reverse=True)
        out.extend(ranked[:n])
    return out


def build_local_knowledge(
    paths: QaPaths,
    client: Any,
    regions: list[str],
    stage_info: Any = None,
    pace: float = BASE_PACE_SECONDS,
    callback: Callable[[str], None] | None = print,
) -> dict[str, Any]:
    """抓取账户字段知识 → 写 experience/fields/{fields,top_fields,meta}.json。"""
    all_fields: list[dict[str, Any]] = []
    dataset_count = 0
    for region in regions:
        if callback:
            callback(f"[knowledge] 区域 {region}: 拉取数据集……")
        ds_ids = fetch_dataset_ids(client, region, callback)
        dataset_count += len(ds_ids)
        for ds_id in ds_ids:
            if callback:
                callback(f"[knowledge]   数据集 {ds_id}: 拉取字段……")
            all_fields.extend(fetch_dataset_fields(client, ds_id, region))
            if pace > 0:
                time.sleep(pace)
        if pace > 0:
            time.sleep(pace)

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": {
            "level": stage_info.level if stage_info else "UNKNOWN",
            "is_consultant": bool(stage_info and stage_info.is_consultant),
        },
        "regions": list(regions),
        "dataset_count": dataset_count,
        "field_count": len(all_fields),
    }
    paths.KNOWLEDGE_FIELDS_DIR.mkdir(parents=True, exist_ok=True)
    paths.KNOWLEDGE_FIELDS_JSON.write_text(
        json.dumps(all_fields, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    paths.KNOWLEDGE_TOP_FIELDS_JSON.write_text(
        json.dumps(_top_fields(all_fields), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    paths.KNOWLEDGE_META_JSON.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ensure_experience_templates(paths)
    return meta


# ---- 读取 ----


def load_fields(paths: QaPaths) -> tuple[set[str], dict[str, str]]:
    """读取本地字段白名单 + 类型映射（validate 类型检查用；缺失抛错）。"""
    p = paths.KNOWLEDGE_FIELDS_JSON
    if not p.exists():
        raise KnowledgeMissingError(
            f"本地知识库未生成: {p}\n"
            "首次运行请先执行 `qa update-knowledge` 按账户抓取字段知识（约几分钟）。"
        )
    data = json.loads(p.read_text(encoding="utf-8"))
    ids: set[str] = set()
    types: dict[str, str] = {}
    for f in data:
        if isinstance(f, dict) and f.get("id"):
            ids.add(f["id"])
            types[f["id"]] = str(f.get("type") or "MATRIX")
    return ids, types


def load_top_fields(paths: QaPaths) -> list[dict[str, Any]]:
    """读取每数据集 top 字段（qa suggest 用；缺失抛 KnowledgeMissingError）。"""
    p = paths.KNOWLEDGE_TOP_FIELDS_JSON
    if not p.exists():
        raise KnowledgeMissingError(
            f"本地知识库未生成: {p}\n"
            "首次运行请先执行 `qa update-knowledge` 按账户抓取字段知识。"
        )
    data = json.loads(p.read_text(encoding="utf-8"))
    return [f for f in data if isinstance(f, dict)]


def knowledge_status(paths: QaPaths) -> dict[str, Any] | None:
    """返回知识库 meta（未生成/损坏返回 None），供 qa status 展示。"""
    p = paths.KNOWLEDGE_META_JSON
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


# ---- 经验沉淀（experience/playbook.md + failures.md）----


def ensure_experience_templates(paths: QaPaths) -> None:
    """确保 playbook/failures 模板存在（首次构建/沉淀时自动创建）。"""
    paths.EXPERIENCE_DIR.mkdir(parents=True, exist_ok=True)
    if not paths.PLAYBOOK.exists():
        paths.PLAYBOOK.write_text(_PLAYBOOK_TEMPLATE, encoding="utf-8")
    if not paths.FAILURES.exists():
        paths.FAILURES.write_text(_FAILURES_TEMPLATE, encoding="utf-8")


def append_experience(
    paths: QaPaths,
    kind: str,
    entry_id: str,
    title: str,
    body: str,
) -> None:
    """追加一条经验/证伪到 experience markdown（幂等：按 entry_id 注释去重）。

    kind: "lesson" → playbook.md；其他 → failures.md。
    """
    ensure_experience_templates(paths)
    path = paths.PLAYBOOK if kind == "lesson" else paths.FAILURES
    marker = f"<!-- {entry_id} -->"
    if marker in path.read_text(encoding="utf-8"):
        return
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n## {date} {title}\n\n{body}\n\n{marker}\n")


def restore_experience_templates(paths: QaPaths) -> None:
    """qa reset 用：playbook/failures 恢复模板（保留 fields/ 账户知识）。"""
    ensure_experience_templates(paths)
    paths.PLAYBOOK.write_text(_PLAYBOOK_TEMPLATE, encoding="utf-8")
    paths.FAILURES.write_text(_FAILURES_TEMPLATE, encoding="utf-8")
