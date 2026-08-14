# QuantAlpha — Agent 工作流入口 + 项目知识库

> 任何 AI agent（opencode / claude code / codex）打开本仓库后的**第一读取文件**。
> 权威系统设计见 `design/quantalpha-design.md`（v1.1）。实现以设计文档为准。

## 项目是什么

WorldQuant BRAIN 平台 AI 辅助量化研究闭环系统。对话式 agent 驱动，自动完成：

**生成候选 alpha → 本地预检 → 平台 API 云端模拟 → 门槛筛选 → 人工确认提交 → 经验沉淀**

目标：冲 10,000 分拿顾问邀请（当前等级状态见私有 account_info.json）+ 学习量化研究。仓库可分享给朋友（工具+知识分享，私有数据 gitignore 隔离）。

## 启动流程（每次会话第一步，勿跳过）

```
1. 运行 `qa status`（或读取 secrets/worldquant_cookies.txt 调 API）
   → 账号阶段检测（level/geniusLevel/consultant）+ cookie 有效性 + 配额/限流状态
   → 动态配置：并发数、可用区域、字段范围、表达式语言
2. 询问用户本次意图（生成候选？查看报告？提交确认？更新知识库？）
   不要擅自开始生成/提交
```

## 工作流（九步闭环）

| 步骤 | 动作 | 自动/人工 |
|---|---|---|
| 0 | 启动：阶段检测 + cookie 验证 + 配额状态 | 自动 |
| 1 | 用户给研究方向/点子（或 agent 提议） | 人工 |
| 2 | **agent（你）读 knowledge/ 知识库 → 生成 10-20 个候选表达式 → 写入 `data/candidates/YYYY-MM-DD.json`**（项目不调 LLM，生成是你的事） | 自动 |
| 3 | validate 预检：语法 lint + 字段白名单 + 去重 + 复杂度 | 自动 |
| 4 | 批量云端模拟（3 并发 / 分钟限流管理） | 自动 |
| 5 | 门槛过滤 + 组合视角排序 + 免费相关门 | 自动 |
| 6 | 候选清单报告（指标/解释/提交建议） | 自动 |
| 7 | **用户逐条确认** → agent 代提交 → 回查 ACTIVE | **人工确认** |
| 8 | 经验教训写入 playbook（脱敏）+ 证伪库 | 自动 |

## 命令清单

| 命令 | 功能 | 状态 |
|---|---|---|
| `qa status` | 阶段检测 + cookie 验证 + 配额（启动首查） | ✅ 已实现（第一批） |
| `qa run [--candidates-file ...]` | 完整闭环（读入候选→预检→模拟→筛选→报告）。**候选文件由你（agent）先写入 `data/candidates/`** | ✅ 已实现（第一批） |
| `qa report [--daily]` | 当日候选清单 / 每日累计汇总 | ✅ 已实现（第一批） |
| `qa submit <alpha_id>` | 人工确认后提交（提交前展示全部检查，提交后回查 ACTIVE） | ⏳ 第二批 |
| `qa update-knowledge` | 更新知识库（算子/字段/教程；成顾问后 12 区域 40 万字段） | ⏳ 第三批 |

## 合规红线（不可违背）

1. **禁止无人值守自动提交**——提交必须展示检查结果 + 等待用户显式确认
2. **禁止**分享真实 alpha 表达式/账号 ID/盈亏数据（playbook 必须脱敏）
3. **允许**：AI 生成初步想法、批量模拟、优化流程、复盘（平台官方 AI 立场）
4. 模拟配额内运行，不做 24h 刷量/挂机
5. 表达式仅发往 BRAIN API 与 LLM API

## 关键知识速查

- **提交门槛：** Fitness≥1.0(D1)/1.3(D0)、Sharpe>1.25(D1)/2.0(D0)、TO 1-70%、自相关<0.7（Sharpe≥1.375 豁免）、子宇宙 `0.75·√(sub/alpha)·sharpe`
- **ATOM：** 单数据集 alpha 放宽（只看 2Y Sharpe D1>1）→ 优先单数据集表达
- **计分：** 非顾问阶段每天生成 1-2 个成功的 alpha 即可；顾问阶段提交 3+ 个当天奖励封顶；相对分（看当天其他用户）；美东 3AM 结算；小宇宙+D1 分更高
- **生成架构：** 项目内不调用 LLM API——候选生成由 agent（你）完成：读 knowledge/ 后写 `data/candidates/YYYY-MM-DD.json`，项目只做预检/模拟/筛选/报告
- **测试只在平台：** 本地零回测，所有性能测试 = 平台 API 模拟
- **组合视角：** alpha 非独立，平台按整体评判 → 生成/筛选考虑与现有组合相关性
- **字段优先级：** 基本面 40% > 混合 12.7% > 纯技术 5.3%；黄金组合 `group_rank(ts_rank(x,N),subindustry)`
- **decay 经验值：** 基本面 0 / 分析师 0-4 / 技术 10-30；truncation 0.05-0.1

## 项目结构与文档导航

```
QuantAlpha/
├── AGENTS.md                    # 本文件（工作流入口）
├── README.md                    # 人类说明（待创建）
├── design/                      # 设计文档 + 变更清单
│   ├── quantalpha-design.md     # ⭐ 权威设计 v1.1（模块职责/数据模型/错误处理/MVP）
│   └── 变更清单-v1.1-待拍板.md
├── qa/                          # Python 工具库（待实现）
├── knowledge/                   # 静态知识库（待从 platform-data 整理）
├── data/                        # 🔒 gitignored：qa.db + audit/
├── experience/                  # 🔒 gitignored：原始经验
├── reports/                     # 🔒 gitignored：个人成果
└── .omo/                        # 🔒 gitignored：secrets/ + 调研资产
```

**调研资产（已抓取，位于 `.omo/ulw-research/20260814-090436/`）：**
- `platform-data/` — 22MB：67 算子参考、8642 字段元数据、291 官方文章、2022 论坛帖索引、1974 评论、28 教程、279 比赛、42 alpha 全量检查
- `需求分析预备报告.md` — 信息资产清单 + 初步分析
- `需求分析与搭建步骤.md` — v1.1 早期需求文档
- `SYNTHESIS.md` — 调研收敛总结

## COMMANDS

- 实现后：`qa status` / `qa run` / `qa submit` / `qa report` / `qa update-knowledge`
- 测试：`pytest qa/tests/`（设计 v1.1 §10）
- 开发节奏：1.0 可跑通版本后首次 commit；之后每 2-3 功能更新再提交

## 最终提交范围（用户约定，提交时遵守）

**只提交：**
1. 跑通全流程的代码：`qa/`（含测试）、`pyproject.toml`、`.gitignore`
2. 让 agent 理解设计思想与全流程的文件：`AGENTS.md`、`README.md`、`design/quantalpha-design.md`、`knowledge/`

**不提交（中间态/skill 产物/私有数据）：**
- `design/plans/`（实施计划，skill 中间态）
- `design/变更清单-v1.1-待拍板.md`（需求分析过程产物）
- `.omo/`（secrets + 调研资产）、`data/`、`experience/`、`reports/`（私有数据，gitignored）
- 其他草稿/临时文件

## 个人信息约定（用户要求，提交时遵守）

- **个人账号信息集中存放**于 `secrets/account_info.json`（账号 ID、分数、诊断数据等——该目录 gitignored，永不提交）
- 提交范围内的**所有文件必须零个人痕迹**：不含账号 ID、分数、邮箱、电话、姓名、教育信息、个人研究字段依赖等
- 若需在提交文件中提及账号状态，仅可用"用户/顾问"二元描述（如"当前为用户阶段"），**不写具体等级、分数、数值**
- 提交前扫描（把 `<账号ID>`/`<分数>` 替换为实际值后执行）：`grep -rn "<账号ID>\|<分数>\|<邮箱>" --include="*.py" --include="*.md" AGENTS.md README.md design/ qa/`

## ANTI-PATTERNS（本项目）

- 不写本地回测（无平台数据，P1）
- 不自动提交（ToS 红线，P2）
- 不分享真实表达式/账号 ID（P5）
- 不过度工程（P6：MVP 不做向量检索/Web UI/多用户/定时任务/D0）
