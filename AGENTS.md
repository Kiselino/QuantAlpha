# QuantAlpha — Agent 工作流入口 + 项目知识库

> 任何 AI agent（opencode / claude code / codex）打开本仓库后的**第一读取文件**。
> 权威系统设计见 `quantalpha-design.md`（v1.4）。实现以设计文档为准。

## 项目是什么

WorldQuant BRAIN 平台 AI 辅助量化研究闭环系统。对话式 agent 驱动，自动完成：

**生成候选 alpha → 本地预检 → 平台 API 云端模拟 → 门槛筛选 → 人工确认提交 → 经验沉淀**

目标：冲 10,000 分拿顾问邀请（当前等级状态见私有 account_info.json）+ 学习量化研究。仓库公开（工具+知识分享，私有数据 gitignore 隔离）。

## 启动流程（每次会话第一步，勿跳过）

```
1. 运行 `qa status`（或读取 secrets/worldquant_cookies.txt 调 API）
   → 账号阶段检测（level/geniusLevel/consultant）+ cookie 有效性 + 配额/限流状态
   → 动态配置：并发数、可用区域、字段范围、表达式语言
   → 同时检查本地知识库 `experience/fields/`（v1.4 起字段数据本地化）：
     缺失 → 主动提示用户"首次运行需先 `qa update-knowledge` 生成账户专属字段知识库"
2. 检查待提交暂存 `secrets/pending_submits.json`：
   → 有内容 → 主动告知用户"有 N 个已达标 alpha 暂存待提交"
     （列出每个的 local_id/描述/指标），询问是否提交（用户确认后逐个
     `qa submit <local_id> --yes`，提交成功后从该文件删除对应条目）
   → 无文件/为空 → 正常继续
3. cookie 无效时：`qa login --username ... --password ...`（账号密码方式）
   或让用户提供 Copy as cURL（敏感用户可选用）
4. 询问用户本次意图（生成候选？查看报告？提交确认？更新知识库？）
   不要擅自开始生成/提交
5. 若本次要生成候选：**先询问主题来源，三选一**——
   ① 随机抽取（agent 跑 `qa suggest` 或自行随机）
   ② 网络热门（agent 用 web 搜索 BRAIN 社区/论坛/教程的热门研究方向）
   ③ 用户指定（用户直接给方向/点子）
   用户选择后再进入生成（不擅自替用户选主题）
```

## 工作流（九步闭环）

| 步骤 | 动作 | 自动/人工 |
|---|---|---|
| 0 | 启动：阶段检测 + cookie 验证 + 配额状态 + 本地知识库检查 | 自动 |
| 1 | **生成前询问主题来源三选一**：① `qa suggest`/agent 随机抽取 ② agent 网络调研热门主题 ③ 用户指定方向 | 人工 |
| 2 | **agent（你）读知识库（公开 `knowledge/` + 本地 `experience/`：字段/playbook/failures）→ 生成 10-20 个候选表达式 → 写入 `data/candidates/YYYY-MM-DD.json`**（项目不调 LLM，生成是你的事） | 自动 |
| 3 | validate 预检：语法 lint + 字段白名单（**读本地 experience/fields/**）+ 去重 + 复杂度 | 自动 |
| 4 | 批量云端模拟（3 并发 / 分钟限流管理） | 自动 |
| 5 | 门槛过滤 + 组合视角排序 + 免费相关门 | 自动 |
| 6 | 候选清单报告（指标/解释/提交建议） | 自动 |
| 7 | **用户逐条确认** → agent 代提交 → 回查 ACTIVE | **人工确认** |
| 8 | 经验自动沉淀：模拟 PASS→lessons、FAIL→failures（SQLite + experience/playbook.md/failures.md 自动追加，v1.4 已接线） | 自动 |

## 命令清单

| 命令 | 功能 | 状态 |
|---|---|---|
| `qa login [--username ...] [--password ...]` | 账号密码登录 → 写 cookie（凭据不落盘；Persona 人机验证会提示） | ✅ 已实现 |
| `qa status` | 阶段检测 + cookie 验证 + 配额 + 本地知识库状态（启动首查） | ✅ 已实现（第一批） |
| `qa run [--candidates-file ...]` | 完整闭环（读入候选→预检→模拟→筛选→报告）。**候选文件由你（agent）先写入 `data/candidates/`** | ✅ 已实现（第一批） |
| `qa report [--daily]` | 当日候选清单 / 每日累计汇总 | ✅ 已实现（第一批） |
| `qa submit <alpha_id> [--yes]` | 人工确认后提交（提交前展示全部检查 + 免费相关门，提交后回查 ACTIVE） | ✅ 已实现 |
| `qa reset [--yes]` | **清除积累的经验，回到初始状态**（见下方"经验清除范围"） | ✅ 已实现 |
| `qa update-knowledge [--regions ...]` | **按账户抓取字段知识 → 写本地 experience/fields/**（首次运行必做；数据 gitignored 不上传；顾问可 --regions 限定区域） | ✅ 已实现（v1.4） |
| `qa suggest` | 随机建议研究方向（本地知识库随机数据集+字段+主题），供生成候选 | ✅ 已实现（v1.4） |

### 经验清除范围（用户说"清除经验/重置"时，agent 执行 `qa reset`）

**清除（经验积累）：**
- `data/qa.db` — 全部记录（候选/模拟/提交/经验/证伪/日收益）
- `data/audit/`、`data/candidates/`、`reports/daily/` — 审计/候选/每日汇总
- `secrets/pending_submits.json` — 待提交暂存（⚠️ 含未提交 alpha 时清除前必须警告用户）
- `experience/playbook.md` + `failures.md` — 本地经验沉淀恢复为模板

**保留（非经验）：**
- `secrets/` 下 cookie 与 account_info.json（登录凭证，重置后无需重新登录）
- `knowledge/` 公开静态知识库（operators/rules/pitfalls/fields 策略说明）
- `experience/fields/` 账户字段知识（按账户生成，非经验积累）
- `qa/` 代码、`pyproject.toml`、`pyrightconfig.json`

> `qa reset` 执行前必须展示将清除的清单 + 等待用户确认（与提交同级的合规要求）；`--yes` 仅限用户在对话中已显式确认后由 agent 使用。

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
- **生成架构：** 项目内不调用 LLM API——候选生成由 agent（你）完成：读公开 `knowledge/` + 本地 `experience/`（字段/playbook/failures）后写 `data/candidates/YYYY-MM-DD.json`，项目只做预检/模拟/筛选/报告
- **测试只在平台：** 本地零回测，所有性能测试 = 平台 API 模拟
- **组合视角：** alpha 非独立，平台按整体评判 → 生成/筛选考虑与现有组合相关性
- **字段优先级：** 基本面 40% > 混合 12.7% > 纯技术 5.3%；黄金组合 `group_rank(ts_rank(x,N),subindustry)`
- **decay 经验值：** 基本面 0 / 分析师 0-4 / 技术 10-30；truncation 0.05-0.1
- **知识库拆分（v1.4）：** 公开 `knowledge/`（operators/rules/pitfalls，平台公开文档）随仓库分发；本地 `experience/`（字段元数据 + playbook + failures，账户专属）gitignored 不上传——**生成前必须读本地 experience/ 的字段与经验**

## 项目结构与文档导航

```
QuantAlpha/
├── AGENTS.md                    # 本文件（工作流入口）
├── README.md                    # 人类说明：安装、认证配置（双选）、快速开始
├── quantalpha-design.md         # ⭐ 权威设计 v1.4（模块职责/数据模型/错误处理/MVP）
├── qa/                          # Python 工具库（auth/stage/brain_client/validate/knowledge/...）
├── knowledge/                   # ✅ 公开静态知识库：operators/rules/pitfalls/fields 策略说明
├── pyrightconfig.json           # LSP 配置（basedpyright）
├── experience/                  # 🔒 gitignored：本地账户知识库（fields/ + playbook.md + failures.md）
├── data/                        # 🔒 gitignored：qa.db + audit/ + candidates/
├── reports/                     # 🔒 gitignored：个人成果
├── secrets/                     # 🔒 gitignored：cookie、account_info.json
└── .omo/                        # 🔒 gitignored：session 存档（调研资产未随仓库分发）
```

## COMMANDS

- 实现后：`qa login` / `qa status` / `qa run` / `qa submit` / `qa report` / `qa reset` / `qa update-knowledge` / `qa suggest`
- 测试：`pytest qa/tests/`（设计 v1.4 §10）
- 开发节奏：1.0 可跑通版本后首次 commit；之后每 2-3 功能更新再提交

## 最终提交范围（用户约定，提交时遵守）

**只提交：**
1. 跑通全流程的代码：`qa/`（含测试）、`pyproject.toml`、`.gitignore`
2. 让 agent 理解设计思想与全流程的文件：`AGENTS.md`、`README.md`、`quantalpha-design.md`、`knowledge/`

**不提交（中间态/skill 产物/私有数据）：**
- `.omo/`（secrets + 调研资产）、`data/`、`reports/`（私有数据，gitignored）
- 其他草稿/临时文件（含历史 `design/` 目录残留）

## 个人信息约定（用户要求，提交时遵守）

- **个人账号信息集中存放**于 `secrets/account_info.json`（账号 ID、分数、诊断数据等——该目录 gitignored，永不提交）
- 提交范围内的**所有文件必须零个人痕迹**：不含账号 ID、分数、邮箱、电话、姓名、教育信息、个人研究字段依赖等
- 若需在提交文件中提及账号状态，仅可用"用户/顾问"二元描述（如"当前为用户阶段"），**不写具体等级、分数、数值**
- 提交前扫描（把 `<账号ID>`/`<分数>` 替换为实际值后执行）：`grep -rn "<账号ID>\|<分数>\|<邮箱>" --include="*.py" --include="*.md" AGENTS.md README.md quantalpha-design.md qa/`

## ANTI-PATTERNS（本项目）

- 不写本地回测（无平台数据，P1）
- 不自动提交（ToS 红线，P2）
- 不分享真实表达式/账号 ID（P5）
- 不过度工程（P6：MVP 不做向量检索/Web UI/多用户/定时任务/D0）
