"""qa suggest 命令：随机建议研究方向（本地知识库数据集+字段+主题）。"""

from __future__ import annotations

import random

from qa import knowledge
from qa.config import AppConfig
from qa.knowledge import KnowledgeMissingError
from qa.paths import QaPaths

_THEMES_BY_CATEGORY: dict[str, list[dict[str, str]]] = {
    "fundamental": [
        {
            "name": "价值修复",
            "template": "低估值维度（{field} 衡量价值），预期低估标的均值回归",
        },
        {
            "name": "质量溢价",
            "template": "盈利质量维度（{field} 衡量质量），高质量公司持续占优",
        },
        {"name": "增长动能", "template": "成长维度（{field} 衡量增速），高增长延续"},
    ],
    "analyst": [
        {
            "name": "预期修正",
            "template": "分析师预期上调（{field} 衡量修正），共识改善领先价格",
        },
        {
            "name": "盈利惊喜",
            "template": "实际盈余相对预期（{field}），超预期标的动量延续",
        },
    ],
    "alternative": [
        {
            "name": "情绪反转",
            "template": "情绪极端后反转（{field} 衡量情绪），均值回归",
        },
        {
            "name": "新闻漂移",
            "template": "信息冲击后的价格漂移（{field} 衡量冲击），滞后反应",
        },
    ],
    "technical": [
        {"name": "趋势动量", "template": "动量维度（{field} 衡量趋势强度），强者恒强"},
        {
            "name": "短期反转",
            "template": "短期超跌反弹（{field} 衡量近期涨跌），反向布局",
        },
        {
            "name": "低波动溢价",
            "template": "低波动维度（{field} 衡量波动），低风险异象",
        },
    ],
}


def _signal_fields(top: list[dict]) -> list[dict]:
    """过滤不可用于标量表达式的字段（UNIVERSE/SYMBOL/VECTOR；VECTOR 需 vec_* 转换）。"""
    return [f for f in top if f.get("type") not in ("UNIVERSE", "SYMBOL", "VECTOR")]


def _theme_for_dataset(ds: str) -> list[dict[str, str]]:
    """数据集 id → 主题模板组（基本面/分析师/另类/技术 四类）。"""
    if ds.startswith(("analyst", "earnings")):
        return _THEMES_BY_CATEGORY["analyst"]
    if ds.startswith("fundamental"):
        return _THEMES_BY_CATEGORY["fundamental"]
    if ds.startswith(("news", "socialmedia", "sentiment")):
        return _THEMES_BY_CATEGORY["alternative"]
    return _THEMES_BY_CATEGORY["technical"]


def cmd_suggest(paths: QaPaths) -> int:
    """随机建议研究方向（本地知识库随机数据集+字段+主题），供 agent 生成候选。"""
    try:
        top = knowledge.load_top_fields(paths)
    except KnowledgeMissingError as e:
        print(f"[suggest] 错误: {e}")
        print("[suggest] 提示: 先运行 `qa update-knowledge` 生成本地知识库。")
        return 1
    signal = _signal_fields(top)
    if not signal:
        print("[suggest] 本地知识库无可用信号字段，请先运行 `qa update-knowledge`。")
        return 1
    by_ds: dict[str, list[dict]] = {}
    for f in signal:
        by_ds.setdefault(str(f.get("dataset", "")), []).append(f)
    ds = random.choice(sorted(by_ds))
    picks = random.sample(by_ds[ds], min(3, len(by_ds[ds])))
    theme = random.choice(_theme_for_dataset(ds))
    print(f"[suggest] 建议研究方向（随机）: {theme['name']}")
    print(f"  数据集: {ds}")
    print(
        "  候选字段: "
        + ", ".join(
            f"{f.get('id')}（{str(f.get('description', ''))[:24]}）" for f in picks
        )
    )
    print(f"  逻辑模板: {theme['template'].format(field=picks[0].get('id'))}")
    print("  → agent 依据以上方向 + 本地字段生成 10-20 个候选写入 data/candidates/")
    return 0


def main(paths: QaPaths, cfg: AppConfig, args) -> int:
    """命令入口：qa suggest（argparse 分发）。"""
    return cmd_suggest(paths)
