# QuantAlpha — 系统设计文档（项目职能说明书）

**版本:** v1.2 · **日期:** 2026-08-14 · **状态:** 第一批已实现跑通（login/status/run/report）
**读者:** 任何 AI agent / 人类协作者。打开本仓库后，先读 `AGENTS.md`（工作流入口），再读本文（系统全貌）。

> 本文档是 QuantAlpha 系统的唯一权威设计来源。实现、修改、扩展均以本文为准。
> 本仓库公开分发：工具 + 静态知识库 + 脱敏 playbook 随仓库分发；私有数据（cookie、账号密码、原始经验、个人成果）gitignore 隔离。
>
> **v1.1 更新（外部经验复查 + 实测验证）：** ① 新增**账号阶段检测**（启动时判定 用户/顾问，动态配置并发/区域/字段/语言）② 限流机制实测修正（`x-ratelimit-*-minute` 30/分，非日配额）③ 新增 `validate.py` 前置校验层（省无效模拟配额）④ 提交前免费相关门 `/correlations/self`（实测可用）⑤ 提交后二次确认 `status==ACTIVE` ⑥ 自相关改算**日收益**相关 ⑦ 每日提交 1-2 个即达 2000 分封顶（官方计分规则）；用户口径补充：**顾问阶段提交 3+ 个当日奖励封顶** ⑧ 字段优先级/decay 经验值写入生成提示词 ⑨ 经验 schema 扩展 + 证伪库 ⑩ 知识库 RAG 可开关 ⑪ **生成架构调整：项目内不调用 LLM API——生成由对话层 agent（harness）完成，agent 读 knowledge/ 后写候选到 `data/candidates/`，项目只做执行**。
>
> **v1.2 更新（第一批实现落地 + 实测修正）：** ① **新增 `auth.py` 账号密码登录**（`qa login`：`POST /authentication` + HTTP Basic Auth → 提取 Set-Cookie `t=` JWT；凭据不落盘不进审计；Persona 人机验证检测提示；保留浏览器复制 cURL 方式）② **会话时长实测 ~4h**（登录响应 `token.expiry ≈ 14222s`；API 登录 JWT `amr=['pwd']` 证实无需验证码——Altcha 仅用于注册）③ **并发模拟落地**（cli `ThreadPoolExecutor`，并发数取阶段检测值，写库回主线程避免 sqlite 跨线程）④ **去重修复**：模拟完成 `save_alpha`（此前只写 simulations 导致 `alpha_hash_exists` 永远不命中、中断重跑重复模拟）⑤ **审计接线**：`append_audit` 返回时间戳写入 `simulations.audit_path`，错误路径也审计 ⑥ 新增 `paths.py`（私有文件路径单点定义）⑦ 全库类型注解补全（basedpyright 零 error）+ `pyrightconfig.json` LSP 配置 ⑧ 设计文档移至仓库根目录（删除 `design/` 目录）。**明确未实现（后续批次）：** `optimizer.py`/`knowledge.py` 模块、`qa submit`、`qa update-knowledge`、`--smoke`/`--batch` 参数、RAG 向量检索。

---

## 1. 项目定位与目标

WorldQuant BRAIN 平台 AI 辅助量化研究闭环系统。用户通过对话式 agent 驱动，自动完成：

**生成候选 alpha → 平台 API 云端模拟 → 门槛筛选 → 人工确认提交 → 经验沉淀**

### 1.1 用户目标（优先级排序）

1. **冲 10,000 分拿顾问邀请**（当前等级状态见私有 `account_info.json`）
2. **系统先跑通闭环**（MVP 优先，不过度工程）
3. **学习量化研究**（每个候选附研究逻辑解释）

### 1.2 成功标准

- **非顾问阶段：每天稳定产出 1-2 个成功（可提交）候选**——用户口径：非顾问每天生成 1-2 个成功的 alpha 即可。
- **顾问阶段：每日提交 3 个或以上**当天奖励即封顶（Base Payment 计入口径，用户修正）。
- 学习价值伴随：每个候选附研究逻辑解释。

---

## 2. 核心设计原则（不可违背）

| # | 原则 | 说明 |
|---|---|---|
| P1 | **测试只在平台** | 本地零回测。所有性能测试 = BRAIN API 云端模拟（`POST /simulations` 返回 `is.checks`）。本地仅做表达式规则校验 + 结构简单优化 |
| P2 | **模拟全自动，提交人工确认** | 生成/模拟/筛选/报告全自动；提交必须逐条展示检查结果 + 研究逻辑，等待用户显式确认后 agent 代提交。**禁止无人值守自动提交**（ToS 红线） |
| P3 | **组合视角（alpha 非独立）** | 平台按全部 alpha 的整体表现评判：SELF_CORRELATION 检查（对已提交集 max corr <0.7）、IQC 合并计分（新 alpha 不加值即降分）、Base Quality Factor（低相关得分）。生成与筛选必须考虑与现有组合的关系，不能只盯单 alpha 指标 |
| P4 | **单数据集优先（ATOM）** | 优先生成单数据集表达（ATOM 原则放宽提交标准：只看 2Y Sharpe D1>1）；多数据集需显式标记 |
| P5 | **可分享** | 工具 + 静态知识 + 脱敏 playbook 随仓库分发；私有数据（cookie/原始经验/个人成果）gitignore 隔离。**严禁在分享内容中包含真实 alpha 表达式/账号 ID/盈亏数据** |
| P6 | **YAGNI** | 不做：本地回测、Web UI、多用户、定时任务、D0 支持（需 5000 分解锁）、顾问专属功能（PYTHON/ML、12 区域——由阶段检测启用但 MVP 不实现）。向量检索初期 TF-IDF，**RAG 做成可开关**（FAFM 领域无定论，保留零样本基线 A/B） |

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│  对话层：opencode / claude code / codex 等 agent          │
│  （用户 ↔ agent 自然语言；agent 读 AGENTS.md 后执行）     │
│  （**agent 自身 = 生成引擎**：读 knowledge/ → 生成候选） │
│  （**项目内不调用任何 LLM API**）                         │
└──────────────────────┬──────────────────────────────────┘
                       │ 写入候选文件 / 调用 CLI
┌──────────────────────▼──────────────────────────────────┐
│  Python 工具库 `qa/`                                     │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐              │
│  │ auth      │→│ stage     │→│ brain_    │              │
│  │ (账号登录)│ │ (阶段检测)│ │ client    │              │
│  └───────────┘ └───────────┘ └─────┬─────┘              │
│  ┌───────────┐ ┌─────▼─────┐ ┌─────▼─────┐              │
│  │ candidates│ │  store    │ │  screener │              │
│  │ (读入候选)│ │ (SQLite)  │ │ (门槛+去重)│              │
│  └───────────┘ └───────────┘ └───────────┘              │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐              │
│  │ validate  │ │  report   │ │  paths    │              │
│  │ (本地预检)│ │ (清单+解释)│ │ (路径单点)│              │
│  └───────────┘ └───────────┘ └───────────┘              │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS（仅 BRAIN API 一种外部调用）
┌──────────────────────▼──────────────────────────────────┐
│  BRAIN API（认证/模拟/状态）                              │
└─────────────────────────────────────────────────────────┘
```

### 3.0 启动流程（agent 每次会话的第一步）

```
agent 启动 → 读 cookie（secrets/worldquant_cookies.txt）
  ├─ cookie 缺失/过期 → 认证双选：
  │    ① `qa login --username ... --password ...`（账号密码，凭据不落盘）
  │    ② 用户提供 Copy as cURL → agent 解析写入（对账号密码敏感者）
  ├─ GET /users/self：
  │    401/403 → 会话失效 → 重新认证（上述任一方式）
  │    200 → 解析阶段字段：
  │      level       = BRONZE/SILVER/GOLD（Challenge 等级）
  │      geniusLevel = 顾问 Genius 等级（null = 非顾问）
  │      consultant  = 顾问信息（null = 非顾问）
  └─ 阶段判定 → 动态配置系统变量（见 §4 stage.py）
```

### 3.1 每日闭环数据流（九步）

| 步骤 | 动作 | 组件 | 自动化 |
|---|---|---|---|
| 0 | **启动：阶段检测 + cookie 验证 + 配额状态** | stage / brain_client | 自动 |
| 1 | 用户给研究方向/点子（或让 agent 自主提议） | 对话 | 人工 |
| 2 | **agent（对话层自身）读 knowledge/ 知识库 → 生成 10-20 个候选表达式 → 写入 `data/candidates/YYYY-MM-DD.json`**（项目不调 LLM） | 对话层 + candidates | 自动 |
| 3 | **validate 前置预检**（AST 语法 lint + 字段白名单 + 哈希去重 + 复杂度控制） | validate | 自动 |
| 4 | 批量云端模拟（3 并发 / 分钟限流头管理 / 429 区分处理 / JSONL 审计） | brain_client | 自动 |
| 5 | 门槛过滤（用平台 `is.checks` 结果）+ 组合视角排序 + 免费相关门预检 | screener | 自动 |
| 6 | 生成候选清单报告（指标/通过项/逻辑解释/提交建议） | report | 自动 |
| 7 | **用户逐条确认** → agent 调提交 API → **回查 `status==ACTIVE`** | brain_client | **人工确认** |
| 8 | 指纹 diff → 经验教训写入 playbook（脱敏）+ 证伪库 + 原始库（私有） | store | 自动 |

### 3.2 优化迭代循环（简化版，符合"简单优化即可"）

```
平台模拟完成 → 分析 is.checks 失败原因
  → 仅对 MARGINAL 候选（接近达标）做 ≤1-2 轮 LLM 轻量调整 → 重模拟
  → 其余直接放弃，失败原因记入 lessons/failures（不浪费模拟配额）
  → 止损式触发：连续 N 轮无新达标 → 停止本轮，提示更换研究方向
```

---

## 4. 模块职责（`qa/` 包）

| 文件 | 职责 | 关键实现 |
|---|---|---|
| `config.py` | 配置 | 阈值（Sharpe/TO/自相关）、region/universe/delay 默认值；**阶段相关变量**（并发/区域/字段/语言由 stage.py 动态注入）。**无 LLM 配置——项目不调用 LLM** |
| `paths.py` | 路径单点定义 | 仓库内私有文件路径集中管理（COOKIE/ACCOUNT_INFO/DB/AUDIT_DIR/REPORTS_DIR/CANDIDATES_DIR）；根目录可注入（测试用 tmp 仓库根） |
| `stage.py` | **账号阶段检测** | 读 cookie → `GET /users/self` → 解析 level/geniusLevel/consultant → 输出阶段配置（并发/区域/字段/语言/配额） |
| `auth.py` | **账号密码登录** ✅ v1.2 | `POST /authentication`（HTTP Basic Auth）→ 提取 Set-Cookie 的 `t=` JWT 写入 cookie 文件；凭据不落盘、不进审计；401 凭据错误/Persona 人机验证（`WWW-Authenticate: persona`）分别抛异常提示；替代/补充浏览器复制 cURL 方式 |
| `brain_client.py` | BRAIN API 封装 | 认证（读 `secrets/worldquant_cookies.txt`）；模拟 POST+轮询+结果（含 is.checks，实测状态值 `COMPLETE`）；`/correlations/self` 相关门；**429 区分处理（常规 Retry-After 退避 vs THROTTLED 抛错）**；分钟限流头读取；401/403 抛 PermissionError 提示重登 |
| `validate.py` | **本地预检层（省配额核心）** | 语法 lint（括号配对/未知算子）+ **字段白名单校验**（对照 TOP_FIELDS.json 295 字段 + 核心字段，防 LLM 幻觉字段名）+ 表达式 SHA-256 哈希去重 + 复杂度控制（算子 ≤30、嵌套 ≤8） |
| `candidates.py` | **候选读入** | 读取 agent 写入的 `data/candidates/YYYY-MM-DD.json`（格式：`[{description, hypothesis, expression, dataset_ids}]`）→ 供 validate/screener 处理。**项目内不生成、不调用 LLM**——生成由对话层 agent 完成 |
| `screener.py` | 门槛过滤 + 去重 | 硬门槛：Fitness≥1.0(D1)/1.3(D0)、Sharpe>1.25(D1)/2.0(D0)、TO 1-70%（本地）；平台 `is.checks` FAIL 直接采信；MARGINAL（距门槛 10% 内）；日收益 Pearson 相关；按 score 降序排序 |
| `store.py` | 持久化 | SQLite（alphas/simulations/submissions/daily_returns/lessons/failures 表）+ JSONL 审计（`append_audit` 返回时间戳关联 simulations.audit_path）；幂等（INSERT OR REPLACE）、中断后重跑跳过已完成项（靠 alphas.ast_hash 去重） |
| `report.py` | 报告 | 候选清单 markdown（指标/说明/建议排序）；每日达标汇总文档（`reports/daily/YYYY-MM-DD.md` 追加 + 去重） |
| `cli.py` | 命令入口 | `qa login` / `qa status` / `qa run` / `qa report`；run 内并发模拟（ThreadPoolExecutor，并发数取 stage 检测值，写库回主线程避免 sqlite 跨线程） |
| `optimizer.py` | 优化循环 | ⏳ **未实现**（第二批规划：仅 MARGINAL 候选轻量调整 ≤2 轮 + 止损式触发） |
| `knowledge.py` | 知识检索 | ⏳ **未实现**（第三批规划：静态库检索 + TF-IDF，RAG 可开关） |

### 4.1 命令清单（agent 工作流接口）

| 命令 | 功能 | 说明 |
|---|---|---|
| `qa login [--username ...] [--password ...]` | **账号密码登录** ✅ | `POST /authentication`（Basic Auth）→ 写 `secrets/worldquant_cookies.txt` 并验证会话；凭据不落盘/不进审计；无参数时交互输入（getpass 不回显）；Persona 验证提示人工处理 |
| `qa status` | **启动首查** ✅ | 阶段检测 + cookie 验证 + 配额/限流状态 |
| `qa run [--candidates-file ...] [--idea ...]` | 完整闭环：读入候选→预检→模拟→筛选→报告 ✅ | **候选由 agent 写入 `data/candidates/` 后项目读入**（默认读当日文件）；并发模拟；结果落库（save_alpha + save_simulation + 审计） |
| `qa report [--daily]` | 查看报告 ✅ | 当日候选清单 / 每日累计汇总 |
| `qa submit <alpha_id>` | 人工确认后提交 | ⏳ 第二批：提交前展示全部检查结果；提交后回查 ACTIVE |
| `qa update-knowledge` | 更新知识库 | ⏳ 第三批：重抓算子/字段/教程；成顾问后 12 区域 40 万字段 |

---

## 5. 组合视角设计（P3 落实细节）

| 层面 | 机制 | 数据来源 |
|---|---|---|
| 生成前 | knowledge 提供现有 alpha 库的字段/信号簇分布 + **字段饱和度（alphaCount）** → LLM 提示"避开已饱和簇"；**信号簇按数据来源/经济逻辑划分（非算子族）** | `store.alphas` 聚合 + 字段元数据 |
| 筛选时 | 平台 `SELF_CORRELATION` 检查（对已提交集相关性）作为硬门槛；**本地用日收益序列算相关（非累计 PnL）** | 平台模拟结果 + `daily_returns` 表 |
| 批次内 | 同批候选 AST 结构去重（相似表达式只留最优） | 本地 AST |
| 提交前 | **免费相关门 `GET /alphas/{id}/correlations/self`**：max<0.7 才允许提交（实测可用，不耗提交预算） | 平台 API |
| 提交排序 | 按"加入组合后的增值"近似排序：与现有组合相关性低 + 指标余量大优先（IQC 等权合并逻辑近似） | 平台相关性 + 指标 |

**平台机制参考（调研实锤）：**
- 提交检查 `SELF_CORRELATION`：对已提交全部 alpha 日收益 max Pearson <0.7
- IQC 合并计分：等权合并 PnL；新 alpha 不加值即降分 → 宁缺毋滥
- Base Payment Quality Factor：低相关得分
- ValueFactor：平台最优组合单想法 alpha → 单 alpha 内不混合多个不相关想法

---

## 6. 本地 vs 平台职责划分（P1 落实）

**本地只做（无需交易数据）：** 表达式规则校验（AST 语法/算子/维度/保留字/字段存在性）、复杂度控制、结构去重、简单结构优化（去冗余算子/调 decay/截断）、配额管理。

**平台 API 做（云端模拟，唯一测试来源）：** 全部性能测试（IS Sharpe/Fitness/TO/自相关/子宇宙/权重/鲁棒性检查）、Train/Test 验证（testPeriod 机制）、反过拟合检查（平台内置：子宇宙/超宇宙/illiquid 50%/rank sharpe）、提交后 OS 跟踪。

**明确不做：** 本地 IC 计算、placebo、半衰期、本地 walk-forward、任何本地回测——本地没有平台数据。

---

## 7. 数据模型（SQLite `data/qa.db`）

| 表 | 字段（核心） | 说明 |
|---|---|---|
| `alphas` | id, expression, description, hypothesis, dataset_ids, ast_hash, metrics_json, status(COMPLETE/DRAFT/SUBMITTED/REJECTED——run 模拟完成写 COMPLETE), grade, created_at | 候选与已提交 alpha 全生命周期 |
| `simulations` | id, alpha_id, request_json, result_json, checks_json, status, started_at, finished_at, audit_path | 每次模拟请求/结果/审计 |
| `submissions` | id, alpha_id, submitted_at, user_confirmed(bool), platform_response, current_status(ACTIVE/OS/降级), **confirmed_active(bool)** | 提交记录与状态跟踪（含 ACTIVE 回查） |
| `daily_returns` | alpha_id, date, pnl | **日收益序列**（供相关性计算；来自平台模拟/alpha 数据，diff 后算相关） |
| `lessons` | id, trigger(指纹diff/失败原因), **hypothesis**, **verdict(评审结论)**, lesson(脱敏), raw_ref, created_at | 经验教训（脱敏写入 playbook；**成功 alpha 的"为什么有效"也记录**） |
| `failures` | id, expression_hash, failure_reason, created_at | **证伪库**（已证伪路径，避免 LLM 重复走死路） |

审计：`data/audit/*.jsonl` 不可变日志（模拟/提交全记录）。

---

## 8. 项目结构（可分享布局）

```
QuantAlpha/
├── AGENTS.md                    # ⭐ 跨 agent 工作流入口（目标/启动流程/九步闭环/命令/合规红线）
├── README.md                    # 人类说明：安装、认证配置（双选）、快速开始、使用者上手指南
├── quantalpha-design.md         # ⭐ 本文件：设计文档（智能体职能说明书）
├── qa/                          # Python 工具库
│   └── (auth, config, stage, brain_client, validate, candidates,
│        screener, report, store, cli, paths).py
│       # ⏳ 规划未实现：optimizer.py、knowledge.py
├── knowledge/                   # ✅ 可分享：静态知识库（由 platform-data 整理）
│   ├── operators.md             # 67 算子参考
│   ├── fields/                  # 字段元数据索引（TOP_FIELDS.json 295 精选）+ 字段饱和度
│   ├── rules.md                 # 平台规则/提交门槛/收入机制/计分规则
│   ├── playbook.md              # ⭐ 脱敏经验沉淀（随仓库分享）
│   ├── failures.md              # 证伪库（已证伪路径）
│   └── pitfalls.md              # 量化陷阱/反过拟合
├── pyrightconfig.json           # LSP 配置（basedpyright：venv 解释器 + basic 检查模式）
├── data/                        # 🔒 gitignored：qa.db + audit/ + candidates/
├── experience/                  # 🔒 gitignored：原始经验（含真实表达式/指标）
├── reports/                     # 🔒 gitignored：个人每日成果（可选分享）
├── secrets/                     # 🔒 gitignored：cookie、account_info.json（凭据绝不落盘为文件）
└── pyproject.toml
```

**gitignore 安全线：** `data/`、`experience/`、`.omo/`、`audit/`、`reports/` 全部忽略——其他使用者克隆只拿到工具+知识，不含任何私有数据。

---

## 9. 错误处理与配额管理

| 场景 | 处理 |
|---|---|
| cookie 过期（~4h JWT 会话） | brain_client 检测 401/403 → 报告"请重新认证"（`qa login` 账号密码，或浏览器复制 Cookie）→ 暂停流程等待 |
| **429 常规限流** | `Retry-After` 按 **float** 解析并 clamp（[1s,120s]）；连续 3 次 → 降级 8/4/1 → 仍失败中止本批 |
| **429 + `THROTTLED`**（平台相关性子系统卡死） | 非普通限流 → 提示"平台故障，稍后重试"，暂停批处理 |
| **分钟限流（实测 30 req/min）** | 读取 `x-ratelimit-remaining-minute` / `x-ratelimit-limit-minute`；remaining 低 → 主动限速；remaining=0 → 等 reset |
| 每日模拟配额 | 本地累计计数 + 平台限制报错为准；接近上限自动停 |
| LLM API 失败/限流 | 重试 2 次 → 跳过该候选，不阻塞整批 |
| 模拟结果异常（NaN/空） | 标记 FAIL_INFRA，不计入失败统计 |
| **模拟超时/poll 失败** | 保留原 `Location` 续查，**不盲目重提**（防重复消费配额） |
| 提交失败（检查未过/重复/SC） | 解析平台错误 → 写入 lessons/failures → 报告用户 |
| 中断恢复 | simulations 表记录每项状态，重跑跳过已完成项 |

---

## 10. 测试策略与 MVP 范围

**测试（已实现，50 个单测全过）：**
- candidates：候选 JSON 读入/容错单测
- validate：语法 lint / 字段白名单 / 哈希去重 单测（LLM 幻觉字段拦截验证）
- screener：门槛逻辑单测（构造数据模拟 PASS/MARGINAL/FAIL）+ 相关性计算单测
- store：SQLite CRUD + 幂等 + 审计
- brain_client：mock HTTP（不真调 API）
- stage：users/self 响应解析单测（BRONZE / 顾问 / cookie 失效三种形态）
- auth：登录成功提取 t= / 200 也接受 / 多 Set-Cookie / 401 凭据错误 / Persona / 缺 cookie
- cli：命令分发 + run 端到端（mock 阶段检测与模拟）
- 真实调用：`qa login` 实测成功（BRONZE 用户；JWT `amr=['pwd']` 证实 API 登录无需验证码）+ 401 错误路径实测

**MVP 状态（v1.2）：**
- ✅ 第一批完成：config + paths + store + stage + auth + validate + candidates + brain_client(模拟) + screener(门槛) + report + cli(login/status/run/report)
- ⏳ 第二批：optimizer + 提交流（`qa submit` 含 ACTIVE 回查）+ playbook/failures 沉淀
- ⏳ 第三批：update-knowledge 命令 + 知识库整理 + 字段饱和度
- 明确不做（现阶段）：向量检索（RAG 开关预留）、Web UI、多用户、定时任务、D0、复杂组合优化、顾问专属功能（PYTHON/ML、12 区域——由阶段检测启用但 MVP 不实现）、**项目内 LLM 调用（生成在 agent 侧）**

---

## 11. 合规红线（系统硬约束）

1. **禁止**无人值守自动提交；提交前必须展示检查结果并等待用户显式确认（P2）
2. **禁止**分享真实 alpha 表达式/账号 ID/盈亏数据（P5）；playbook 必须脱敏
3. **禁止**长期挂机/异常活跃模式（模拟配额内运行，不做 24h 刷量）
4. **允许**：AI 生成初步想法、批量模拟、优化流程、复盘（平台官方 AI 立场）
5. 系统私有部署；表达式仅发往 BRAIN API 与 LLM API

---

## 12. 知识库更新（`qa update-knowledge`）

| 数据 | 来源 | 频率 |
|---|---|---|
| 67 算子文档 | platform-data/OPERATORS_REFERENCE.md | 平台变更时 |
| 8642 字段元数据（USA） | platform-data/field_metadata/ | 平台变更时 |
| 教程/论坛/Help Center | platform-data/ 各目录 | 需要时 |
| **顾问 12 区域 40 万字段** | 成为顾问后 API 抓取（`/data-fields?dataset.id=...&region=...`） | 成顾问后 |
| 用户 alpha 库 | `/users/self/alphas` 拉取 | 每次会话 |

**关键 API 备忘（已实测验证，供后续 agent）：**
- 认证：`POST /authentication`（HTTP Basic Auth，email:password）→ 201 + Set-Cookie `t=` JWT（**会话 ~4h**，`token.expiry ≈ 14222s`；API 登录 JWT `amr=['pwd']` 无验证码——Altcha PoW 仅用于注册 `POST /users`）；`DELETE /authentication` 登出；Persona 人机验证：401 + `WWW-Authenticate: persona` + `{"inquiry": ...}` → `POST /authentication/persona`
- 会话/阶段：`GET /users/self` → `level`/`geniusLevel`/`consultant`（阶段检测）；`GET /users/self/consultant` 403=非顾问
- 数据集枚举：`GET /data-sets?region=USA&universe=TOP3000&delay=1&instrumentType=EQUITY&limit=20`（limit 上限 ~50）
- 字段元数据：`GET /data-fields?dataset.id={id}&region=...&delay=1&universe=TOP3000&limit=50&offset={n}`（**参数名是 `dataset.id` 点号写法**，不是 `dataset`）
- 用户 alpha：`GET /users/self/alphas?limit=100`
- 比赛：`GET /competitions?limit=100&offset={n}`
- **提交前相关门：`GET /alphas/{id}/correlations/self`**（返回 schema+records+min/max；max<0.7 可提交；免费不耗提交预算）
- **限流头（实测）：** `x-ratelimit-limit-minute: 30` / `x-ratelimit-remaining-minute`；`ratelimit-*` 兼容头；`access-control-expose-headers: Location,Retry-After`
- Zendesk 论坛：`support.worldquantbrain.com/api/v2/community/topics/{id}/posts.json`（需 SSO cookie jar）

---

## 附：设计决策记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 系统形态 | 对话式 agent 驱动 | 用户偏好；学习价值最高 |
| 自动化边界 | 模拟自动 + 提交人工确认 | ToS 合规红线 |
| 提交执行 | agent 代提交（逐条确认 + ACTIVE 回查） | API 快 + 自动跟踪状态 |
| LLM | **不使用 LLM API——生成由对话层 agent（harness）完成**，项目内零 LLM 调用 | 用户拍板：agent 读项目文件后直接生成 alpha 写入项目，项目跑后续流程 |
| 技术栈 | Python + opencode agent | CS 背景；可测可复用 |
| 测试位置 | 仅平台模拟（本地零回测） | 本地无真实数据（P1） |
| 知识分享 | 脱敏 playbook + 证伪库随仓库分享 | 用户决定；合规允许方法论分享 |
| 优化循环 | 仅 MARGINAL ≤2 轮轻调 + 止损式触发 | 省配额（用户要求"简单优化"） |
| 检索 | TF-IDF 起步，RAG 可开关 | YAGNI，后期可升 RAG |
| 生成批次 | 10-20 个/轮 | 非顾问每日 1-2 个成功即可；省配额 |
| **LLM 调用** | **项目内不调用 LLM**——生成由对话层 agent 完成（读 knowledge/ 写候选文件） | 用户拍板：agent 读项目文件后直接生成 alpha 写入项目，项目跑后续流程 |
| **账号阶段检测** | 启动时 users/self 判定 → 动态配置 | 非顾问/顾问变量差异大（并发/区域/字段/语言） |
| **认证方式（v1.2）** | 双选：`qa login` 账号密码（推荐，可自动续期）或浏览器复制 cURL（敏感用户） | 账号密码不落盘/不进审计；会话 ~4h，长时间模拟需重登 |
| **并发模拟（v1.2）** | `qa run` 内 ThreadPoolExecutor，并发数取阶段检测值；写库回主线程 | API 允许 3 并发；sqlite 连接跨线程不安全 |
| **validate 前置层** | LLM 生成后、模拟前本地预检 | 拦截幻觉字段/语法错，省无效模拟配额 |
| **相关门** | 提交前 `/correlations/self`（max<0.7）+ 日收益相关 | 避免浪费提交槽位；累计 PnL 相关会误判 |
| **计分策略** | 每日集中提交 1-2 个高质量（美东 3AM 日界） | 官方计分规则：每日 2000 分封顶、相对分 |
