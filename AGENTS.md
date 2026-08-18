# QuantAlpha — Agent 工作流入口 + 项目知识库

> 任何 AI agent（opencode / claude code / codex）打开本仓库后的**第一读取文件**。
> 权威系统设计见 `quantalpha-design.md`（v1.6）。实现以设计文档为准。

## 项目是什么

WorldQuant BRAIN 平台 AI 辅助量化研究闭环系统。对话式 agent 驱动，自动完成：

**生成候选 alpha → 本地预检 → 平台 API 云端模拟 → 门槛筛选 → 人工确认提交 → 经验沉淀**

目标：冲 10,000 分拿顾问邀请（当前等级状态见私有 account_info.json）+ 学习量化研究。仓库公开（工具+知识分享，私有数据 gitignore 隔离）。

## 启动流程（每次会话第一步，勿跳过）

```
1. 运行 `qa status`（或读取 secrets/worldquant_cookies.txt 调 API）
   → 账号阶段检测（level/geniusLevel/consultant）+ cookie 有效性
   → **status 输出五项检查——新用户判定/知识库就绪/cookie 有效/账号阶段/待提交暂存**
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
4. **调研访问规则**：BRAIN 平台匿名访问是登录墙（返回 JS 空壳页面）。agent 做官网/API 调研
   （算子文档、字段、模拟示例等）前，先确认 cookie 有效（`qa status` 验证 / 失效则 `qa login`
   刷新），再携带 cookie（`secrets/worldquant_cookies.txt`）访问；遇到官网墙异常时优先怀疑
   cookie 过期——更新登录状态后重试，不要盲目换信息来源
5. **询问运行模式**（每次会话启动问一次）：
   ① **简易模式**（Quick Mode）——agent 自动跑完整个生成流程（见下方"简易模式"章节），
   静默等确认结果；适合用户有正事、只需 agent 后台跑
   ② **详细模式**——每步讲解思路/经验分析，随时可干预（默认现状）
   用户也可在会话中随时口头切换模式
6. 若本次要生成候选（详细模式）：**先询问主题来源，三选一**——
   ① 随机抽取（agent 跑 `qa suggest` 或自行随机）
   ② 网络热门（agent 用 web 搜索 BRAIN 社区/论坛/教程的热门研究方向）
   ③ 用户指定（用户直接给方向/点子）
   用户选择后再进入生成（不擅自替用户选主题）
```

## 简易模式（Quick Mode）

> 触发：启动流程步骤 5 选 ①。目的：生成环节全自动，不输出思路/经验分析，只等用户确认结果。
> 用户需要思路、经验分析时可随时提出（"看看这轮思路"），agent 按需补充。

**执行流程（agent 自主，无需用户中途指令）：**

1. 检查待提交暂存（步骤 2 照常）——有 PASS 暂存则先报告等确认，不叠加新循环
2. 自动循环，**默认最多 10 轮**（用户显式要求"一直循环直到 PASS"时覆盖；429/THROTTLED/配额受限即停并报告）：
   - 每轮：`qa suggest` 随机主题 → 读知识（generation-guide + experience/）→ 生成 10-15 候选
     （同字段集去重、避开 failures、settings 经验值）→ 写入 `data/candidates/YYYY-MM-DD-quick-N.json` → `qa run`
   - **每轮只输出一行进度**：`[轮次 N/10] 主题：xxx | 模拟 M 个 | PASS K | 最佳 Fitness/S
   - **主题止损**：该主题第一批全灭 → 给**一次**优化机会（读 failures 归因 → 调参/同方向变体 → `-opt.json`）；
     优化后仍无 PASS 且 **Fitness < 0.75 且 Sharpe < 1.0** → 换新主题（再跑 `qa suggest`）
   - PASS 候选自动暂存（现有机制）→ 达到 PASS 即提前停止循环
3. 循环结束（10 轮满 / 有 PASS / 用户打断）→ 输出**完整摘要**：
   每轮主题+结果、PASS 候选指标、暂存清单 → **等待用户确认提交**（提交环节合规红线不变：展示检查结果 + 逐条人工确认）
4. 经验沉淀照常自动执行（playbook/failures），**不主动输出**给用户；用户要求时再展示

## 工作流（九步闭环）

| 步骤 | 动作 | 自动/人工 |
|---|---|---|
| 0 | 启动：阶段检测 + cookie 验证 + 本地知识库检查 | 自动 |
| 1 | **生成前询问主题来源三选一**：① `qa suggest`/agent 随机抽取 ② agent 网络调研热门主题 ③ 用户指定方向 | 人工 |
| 2 | **agent（你）读 `knowledge/generation-guide.md`（生成指南）→ 按指南六环节执行（固化输入 → 加载知识 → 字段/表达式 → 设置三层决策 → 输出候选 → 质量自检）→ 生成 10-20 个候选 → 写入 `data/candidates/YYYY-MM-DD.json`**（项目不调 LLM，生成是你的事）。**候选格式：`[{description, hypothesis, expression, dataset_ids, settings?, language?}]`——settings 可选（v1.5）：decay/neutralization/truncation 按数据集类型给经验值（基本面 decay 0 / 分析师 0-4 / 技术 10-30）；language 默认 FASTEXPR（v1.6）；设计逻辑三件套写进 hypothesis；完整流程见 generation-guide.md** | 自动 |
| 3 | validate 预检：语法 lint + 字段白名单（**读本地 experience/fields/**）+ 字段类型 + **settings 值域 + language** + 去重 + 复杂度 + **同字段集簇去重（v1.5：同信号簇只模拟最简者）** | 自动 |
| 4 | 批量云端模拟（默认 3 并发 / `--concurrency` 可调 / 分钟限流管理 / 429/THROTTLED 提示时暂停并提示（无本地预算、无主动配额检查）/ **中断恢复续查（v1.6）**） | 自动 |
| 5 | 门槛过滤 + **PASS 免费相关门排序（v1.5：corr 低者优先）+ PASS 自动暂存待提交（v1.5）** | 自动 |
| 6 | 候选清单报告（指标/解释/提交建议） | 自动 |
| 7 | **用户逐条确认** → agent 代提交 → 回查 ACTIVE | **人工确认** |
| 8 | 经验自动沉淀：模拟 PASS→lessons、FAIL→failures（SQLite + experience/playbook.md/failures.md 自动追加，v1.4 已接线） | 自动 |

## 命令清单

| 命令 | 功能 | 状态 |
|---|---|---|
| `qa login [--username ...] [--password ...]` | 账号密码登录 → 写 cookie（凭据不落盘；Persona 人机验证会提示） | ✅ 已实现 |
| `qa status` | 阶段检测 + cookie 验证 + 本地知识库状态（启动首查；**输出五项检查：新用户判定/知识库就绪/cookie 有效/账号阶段/待提交暂存**） | ✅ 已实现（第一批） |
| `qa run [--candidates-file ...] [--concurrency N]` | 完整闭环（读入候选→预检→模拟→筛选→报告）。**候选文件由你（agent）先写入 `data/candidates/`**；PASS 候选自动暂存待提交（v1.5）；**`--concurrency` 并发数可调（默认 3，v1.6）；中断恢复续查（v1.6）** | ✅ 已实现（第一批） |
| `qa report [--daily] [--pending]` | 当日候选清单 / 每日累计汇总；**`--pending` 批量预览待提交清单（含指标，提交仍逐个人工确认，v1.6）** | ✅ 已实现（第一批） |
| `qa submit <alpha_id> [--yes]` | 人工确认后提交（提交前展示全部检查 + 免费相关门，提交后回查 ACTIVE） | ✅ 已实现 |
| `qa reset [--yes]` | **清除积累的经验，回到初始状态**（见下方"经验清除范围"） | ✅ 已实现 |
| `qa update-knowledge [--regions ...] [--force]` | **按账户抓取字段知识 → 写本地 experience/fields/**（首次运行必做；数据 gitignored 不上传；顾问可 --regions 限定区域；**v1.5：24h 内已生成默认跳过，--force 强制刷新**） | ✅ 已实现（v1.4） |
| `qa suggest` | 随机建议研究方向（本地知识库随机数据集+字段+主题），供生成候选 | ✅ 已实现（v1.4） |

### 经验清除范围（用户说"清除经验/重置"时，agent 执行 `qa reset`）

**清除（经验积累）：**
- `data/qa.db` — 全部记录（候选/模拟/提交/经验/证伪/日收益）
- `data/audit/`、`data/candidates/`、`reports/daily/` — 审计/候选/每日汇总
- `secrets/pending_submits.json` — 待提交暂存（⚠️ 含未提交 alpha 时清除前必须警告用户）
- `experience/playbook.md` + `failures.md` — 本地经验沉淀恢复为模板

**保留（非经验）：**
- `secrets/` 下 cookie 与 account_info.json（登录凭证，重置后无需重新登录）
- `knowledge/` 公开静态知识库（operators/rules/pitfalls/fields 策略说明/generation-guide/community，平台公开文档）
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
- **生成流程：** 见 `knowledge/generation-guide.md`（六环节操作指南；顾问阶段差异以 qa status 输出为准；生成候选前必读）
- **用户覆盖原则：** 知识库与经验是参考而非束缚——用户明确要求忽略某条经验时以用户为准（字段类型/算子上限/设置值域等平台硬约束除外，validate 强制无法绕过）
- **测试只在平台：** 本地零回测，所有性能测试 = 平台 API 模拟
- **组合视角：** alpha 非独立，平台按整体评判 → 生成/筛选考虑与现有组合相关性
- **字段优先级：** 基本面 40% > 混合 12.7% > 纯技术 5.3%；黄金组合 `group_rank(ts_rank(x,N),subindustry)`
- **decay 经验值：** 基本面 0 / 分析师 0-4 / 技术 10-30；truncation 0.05-0.1
- **知识库拆分（v1.4）：** 公开 `knowledge/`（operators/rules/pitfalls/generation-guide/community，平台公开文档）随仓库分发；本地 `experience/`（字段元数据 + playbook + failures，账户专属）gitignored 不上传——**生成前必须读本地 experience/ 的字段与经验**

## 项目结构与文档导航

```
QuantAlpha/
├── AGENTS.md                    # 本文件（工作流入口）
├── README.md                    # 人类说明：安装、认证配置（双选）、快速开始
├── quantalpha-design.md         # ⭐ 权威设计 v1.6（模块职责/数据模型/错误处理/MVP）
├── qa/                          # Python 工具库（auth/stage/brain_client/validate/knowledge/...）
├── knowledge/                   # ✅ 公开静态知识库：operators/rules/pitfalls/fields 策略说明 + generation-guide/community
├── pyrightconfig.json           # LSP 配置（basedpyright）
├── experience/                  # 🔒 gitignored：本地账户知识库（fields/ + playbook.md + failures.md）
├── data/                        # 🔒 gitignored：qa.db + audit/ + candidates/
├── reports/                     # 🔒 gitignored：个人成果
├── secrets/                     # 🔒 gitignored：cookie、account_info.json
```

## COMMANDS

- 实现后：`qa login` / `qa status` / `qa run` / `qa submit` / `qa report` / `qa reset` / `qa update-knowledge` / `qa suggest`
- 测试：`pytest qa/tests/`（设计 v1.6 §10）
- 开发节奏：1.0 可跑通版本后首次 commit；之后每 2-3 功能更新再提交

## 最终提交范围（用户约定，提交时遵守）

**只提交：**
1. 跑通全流程的代码：`qa/`（含测试）、`pyproject.toml`、`.gitignore`
2. 让 agent 理解设计思想与全流程的文件：`AGENTS.md`、`README.md`、`quantalpha-design.md`、`knowledge/`

**不提交（中间态/skill 产物/私有数据）：**
- `data/`、`reports/`（私有数据，gitignored）
- 其他草稿/临时文件

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
