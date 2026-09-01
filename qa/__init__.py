"""QuantAlpha — WorldQuant BRAIN AI-assisted alpha research loop.

包职责：本地预检 → 平台 API 云端模拟 → 门槛筛选 → 报告。
候选生成不在本项目内（项目零 LLM 调用）——由对话层 agent 读 document/
后写入 data/candidates/，本项目只读入并执行后续流程（P6 架构决策）。

命令入口：qa.cli.main（qa status / run / report / submit）。
"""

__version__ = "0.1.0"
