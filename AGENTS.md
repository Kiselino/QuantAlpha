# QuantAlpha — Agent 工作流入口（文档驱动导航）

> 任何 AI agent（opencode / claude code / codex）打开本仓库后的**第一读取文件**。
> 本文档只做导航与约束：**流程细节全部在 `document/flows/`，按环节到点才读**。
> 权威系统设计见 `document/quantalpha-design.md`（v1.7）。

## 项目是什么

WorldQuant BRAIN 平台 AI 辅助量化研究闭环系统。对话式 agent 驱动：**生成候选 alpha → 本地预检 → 平台 API 云端模拟 → 门槛筛选 → 人工确认提交 → 经验沉淀**。

仓库以**文档为核心**（文档驱动）：流程与代码都受文档控制，agent 按流程走到相关步骤才读对应文档。公开仓库（工具+知识分享，私有数据 gitignore 隔离）。

## 流程 → 文档导航表（核心）

| 流程环节 | 何时读 | 读取文档 |
|---|---|---|
| 会话启动 | 每次会话第一步 | `document/flows/startup.md`（六项检查/模式询问/主题来源） |
| 生成（三模式） | 进入生成环节前 | `document/flows/generation.md`（教学/随机/快速） |
| 系统学习（bootcamp） | 教程未通过时（启动检查第 6 项） | 教材 `document/courses/`（官方课笔记 + 教程/作业提取 + 官方学习指南）；闭环协议与模板 `document/courses/bootcamp/`（公开）；个人档案 `docs/bootcamp/`（gitignored） |
| 权限决策 | 决定可用功能时 | `document/flows/access.md`（用户 vs 顾问能力矩阵） |
| 提交 | 有 PASS 待提交时 | `document/flows/submission.md`（检查清单/人工确认） |
| 经验沉淀 | run/submit 结束后 | `document/flows/experience.md`（playbook/failures/模版总结） |
| 知识库更新/平台调研 | 更新知识或调研前 | `document/flows/update-knowledge.md` |
| 人机交互学习 | 用户问"为什么/是什么"时 | `document/flows/learning.md`（教学定位/四大方向） |
| 知识参考 | 需要时查阅（不属流程） | `document/reference/`（operators/rules/pitfalls/fields/community/templates） |
| 系统设计真源 | 理解架构/改代码时 | `document/quantalpha-design.md` |

## 启动流程（简述，细节见 startup.md）

1. `qa status` → 六项检查（新用户判定/知识库就绪/cookie 有效/账号阶段/待提交暂存/**教程进度**）→ 动态配置
2. 有 PASS 暂存 → 先报告等确认提交（不叠加新循环）
3. **教程未通过**（检查第 6 项）→ 进入生成前先完成当日学习段（教材 `document/courses/`，闭环协议 `document/courses/bootcamp/protocol.md`；个人执行副本与档案在本地 `docs/bootcamp/`）
4. 询问**运行模式三选一**：① 教学模式 ② 随机模式 ③ 快速模式（定义见 generation.md）
5. 教学模式/随机模式：询问主题来源三选一（随机/网络热门/用户指定）

## 命令清单

| 命令 | 功能 | 状态 |
|---|---|---|
| `qa login [--username ...] [--password ...]` | 账号密码登录 → 写 cookie（凭据不落盘；Persona 人机验证会提示） | ✅ 已实现 |
| `qa status` | 阶段检测 + cookie 验证 + 本地知识库状态（六项检查，含教程进度提示） | ✅ 已实现（第一批） |
| `qa run [--candidates-file ...] [--concurrency N]` | 完整闭环（读入候选→预检→模拟→筛选→报告）。候选文件由 agent 先写入 `data/candidates/`；PASS 自动暂存（v1.5）；并发可调（v1.6）；中断恢复续查（v1.6） | ✅ 已实现（第一批） |
| `qa report [--daily] [--pending]` | 当日候选清单 / 每日累计汇总；`--pending` 批量预览待提交清单 | ✅ 已实现（第一批） |
| `qa submit <alpha_id> [--yes]` | 人工确认后提交（展示全部检查 + 免费相关门，回查 ACTIVE） | ✅ 已实现 |
| `qa reset [--yes]` | 清除积累的经验，回到初始状态（见下方"经验清除范围"） | ✅ 已实现 |
| `qa update-knowledge [--regions ...] [--force]` | 按账户抓取字段知识 → 写本地 `experience/fields/`（首次运行必做；24h 内跳过，--force 刷新） | ✅ 已实现（v1.4） |
| `qa suggest` | 随机建议研究方向，供生成候选 | ✅ 已实现（v1.4） |

### 经验清除范围（`qa reset`）

**清除（经验积累）：** `data/qa.db`、`data/audit/`、`data/candidates/`、`reports/daily/`、`secrets/pending_submits.json`（⚠️ 含未提交 alpha 时清除前必须警告用户）、`experience/playbook.md` + `failures.md`（恢复为模板）

**保留（非经验）：** `secrets/`（cookie 与 account_info.json）、`document/`（公开文档）、`experience/fields/`（账户字段知识）、`qa/` 代码与配置

> `qa reset` 执行前必须展示将清除的清单 + 等待用户确认；`--yes` 仅限用户已显式确认后使用。

## 合规红线（不可违背）

1. **禁止无人值守自动提交**——提交必须展示检查结果 + 等待用户显式确认
2. **禁止**分享真实 alpha 表达式/账号 ID/盈亏数据（playbook/模版必须脱敏）
3. **允许**：AI 生成初步想法、批量模拟、优化流程、复盘（平台官方 AI 立场）
4. 模拟配额内运行，不做 24h 刷量/挂机
5. 表达式仅发往 BRAIN API 与 LLM API
6. **严禁收集/整理/传播面试真题、答案、题库、面经**（平台零容忍，违规取消资格）——学习内容仅限官方公开材料 + 仓库脱敏经验
7. **模版只写脱敏结构模式**（算子组合骨架 + 适用场景 + 参数经验值），永不写真实 alpha 表达式/字段依赖

## 关键知识速查

- **提交门槛：** Fitness≥1.0(D1)/1.3(D0)、Sharpe>1.25(D1)/2.0(D0)、TO 1-70%、自相关<0.7（Sharpe≥1.375 豁免）、子宇宙 `0.75·√(sub/alpha)·sharpe`
- **ATOM：** 单数据集 alpha 放宽（只看 2Y Sharpe D1>1）→ 优先单数据集表达
- **计分：** 非顾问每天 1-2 个成功即可；顾问提交 3+ 封顶；相对分；美东 3AM 结算；小宇宙+D1 分更高
- **黄金组合：** `group_rank(ts_rank(x,N),subindustry)`；字段优先级：基本面 40% > 混合 12.7% > 纯技术 5.3%
- **decay 经验值：** 基本面 0 / 分析师 0-4 / 技术 10-30；truncation 0.05-0.1
- **用户覆盖原则：** 知识库与经验是参考而非束缚——用户明确要求忽略某条经验时以用户为准（平台硬约束除外，validate 强制无法绕过）
- **测试只在平台：** 本地零回测，所有性能测试 = 平台 API 模拟
- **生成架构：** 项目不调 LLM——候选生成由 agent 完成：读 `document/`（公开）+ `experience/`（本地字段/playbook/failures）后写 `data/candidates/YYYY-MM-DD.json`

## 项目结构与文档导航

```
QuantAlpha/
├── AGENTS.md                    # 本文件（工作流入口 + 导航表）
├── README.md                    # 人类说明：安装、认证配置、快速开始
├── document/                    # ✅ 公开文档（仓库核心，随仓库分发）
│   ├── quantalpha-design.md     # ⭐ 权威设计 v1.8
│   ├── flows/                   # 流程控制文档（startup/generation/submission/experience/access/update-knowledge/learning）
│   ├── courses/                 # 官方课程与学习素材（零基础学量化课程笔记 + 官方教程/作业提取 + 官方学习指南）
│   │   └── bootcamp/            # 学习闭环协议/评分/考点模板/双计划（公开模板，随仓库分发）
│   └── reference/               # 知识参考（operators/rules/pitfalls/fields/community/templates）
├── qa/                          # Python 工具库（auth/stage/brain_client/validate/commands/...）
├── docs/                        # 🔒 gitignored：skill 产物（设计/计划存档）+ bootcamp 个人学习档案（mastery/错题本/摸底卷）
├── experience/                  # 🔒 gitignored：本地账户知识库（fields/ + playbook.md + failures.md）
├── data/                        # 🔒 gitignored：qa.db + audit/ + candidates/
├── reports/                     # 🔒 gitignored：个人成果
├── secrets/                     # 🔒 gitignored：cookie、account_info.json
└── pyrightconfig.json           # LSP 配置（basedpyright）
```

## COMMANDS

- 实现后：`qa login` / `qa status` / `qa run` / `qa submit` / `qa report` / `qa reset` / `qa update-knowledge` / `qa suggest`
- 测试：`pytest qa/tests/`（设计 v1.7 §10）
- 开发节奏：每 2-3 功能更新再提交

## 最终提交范围（用户约定，提交时遵守）

**只提交：**
1. 跑通全流程的代码：`qa/`（含测试）、`pyproject.toml`、`.gitignore`
2. 让 agent 理解设计思想与全流程的文件：`AGENTS.md`、`README.md`、`document/`

**不提交（中间态/skill 产物/私有数据）：**
- `data/`、`reports/`、`experience/`、`secrets/`（私有数据，gitignored）
- `docs/`（skill 产物 + bootcamp 个人学习档案：mastery/错题本/摸底卷——gitignored；**bootcamp 协议与模板已公开于 `document/courses/bootcamp/`，随 document/ 提交**）
- 其他草稿/临时文件

## 个人信息约定（用户要求，提交时遵守）

- **个人账号信息集中存放**于 `secrets/account_info.json`（gitignored，永不提交）
- 提交范围内的**所有文件必须零个人痕迹**：不含账号 ID、分数、邮箱、电话、姓名、教育信息、个人研究字段依赖等
- 若需在提交文件中提及账号状态，仅可用"用户/顾问"二元描述，**不写具体等级、分数、数值**
- 提交前扫描（把 `<账号ID>`/`<分数>`/`<邮箱>` 替换为实际值后执行）：`grep -rn "<账号ID>\|<分数>\|<邮箱>" --include="*.py" --include="*.md" AGENTS.md README.md document/`

## ANTI-PATTERNS（本项目）

- 不写本地回测（无平台数据，P1）
- 不自动提交（ToS 红线，P2）
- 不分享真实表达式/账号 ID（P5）
- 不收集面试题/面经（平台零容忍，P0）
- 不过度工程（P6：MVP 不做向量检索/Web UI/多用户/定时任务/D0）
