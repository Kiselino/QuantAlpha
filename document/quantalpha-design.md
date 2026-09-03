# QuantAlpha — 系统设计文档（项目职能说明书）

**版本:** v1.8 · **日期:** 2026-09-03 · **状态:** v1.7 基础上落地教程学习体系（六项检查 + bootcamp + courses/）与快速模式调整；代码行为不变

> 本文档是 QuantAlpha 系统的唯一权威设计来源。实现、修改、扩展均以本文为准。
> 本仓库公开分发：工具 + 公开知识库（平台文档）；私有数据（cookie、账号密码、本地字段知识、个人经验、个人成果）gitignore 隔离。
>
> **v1.8 更新（教程学习体系批次，决议来源 docs/superpowers/specs/2026-09-03-bootcamp-design.md）：** ① **新形势定位**：平台收紧顾问审核（笔试+面试考察基本知识，打击批量化薅羊毛）——系统目标从"自动产出"升级为"产出 + 知识掌握"双轮（知识不足通不过面试则系统无后续价值）；教程未通过者在生成前先完成当日学习段（startup.md §4）② **启动检查 5→6 项**：新增"教程进度"（读本地 `docs/bootcamp/mastery.json` 掌握度 ≥80% 或用户声明跳过；agent 层检查，qa status 代码不查）③ **快速模式三引擎→两引擎**：删"失败优化"（已并入常规迭代 generation.md §4），保留主题深挖 + 模版生成 ④ **公开教材 `document/courses/`**：官方公开课《零基础学量化》四节新手课笔记 + 官方 /learn 教程 13 页提取 + 官方作业题 3 份（全部官方公开材料，答疑内容不单独保留、增量归并入 reference/ 既有文档）⑤ **本地学习闭环 `docs/bootcamp/`**（gitignored）：RLHF 式闭环协议 + 60 考点 mastery 档案 + 1 周速考/2 周新人双计划 + 摸底诊断/模拟笔试面试（个人学习状态，不进提交）⑥ 旧路径清理：正文遗留 knowledge/ 引用修正为 document/。
> **v1.7 更新（文档驱动重构批次，决议来源 docs/superpowers/specs/2026-09-01-document-restructure-design.md）：** ① **文档体系重组**：`knowledge/` 迁入 `document/` 并按"agent 读取时机"分层——`document/flows/`（流程控制，7 份：startup/generation/submission/experience/access/update-knowledge/learning）+ `document/reference/`（知识参考，6 份：operators/rules/pitfalls/fields/community/templates）+ 本文档置于 `document/` 根；`AGENTS.md` 瘦身为"流程→文档导航表" ② **三模式体系**：教学模式（人机交互学习核心）/随机模式（随机主题+穿插教学）/快速模式（历史高价值复用三引擎：主题深挖/失败优化/模版生成——**v1.8 起失败优化并入常规迭代，快速模式为两引擎**）取代原详细/简易二选一 ③ **人机交互学习定位**：新增 `document/flows/learning.md`——以帮助人掌握相关知识为主，四大学习方向对齐官方学习指南；素材仅限官方公开材料 + 仓库脱敏经验，严禁收集/传播面试材料 ④ **模版机制**：`document/reference/templates.md` 模版库（脱敏结构模式），经验沉淀时总结、调研时收集网络模版，快速模式引擎 c 直接读取 ⑤ **权限差距文档**：`document/flows/access.md` 能力矩阵（用户 vs 顾问），顾问路径按官方帖子更新（10K→排行榜→笔试→面谈→Workday→背调→合同→银行卡）⑥ **todo-design 终结合并**：全部已实现决议归档本附录，未实现项入 Backlog，临时文档删除。
>
> **v1.6 更新（流程深化批次，决议来源 data/todo-design.md）：** ① **登录/status 增强**：`qa status` 升级为会话级环境检查（五项输出：新用户判定/知识库就绪/cookie 有效/账号阶段/待提交暂存）；入口双轨检查（run/submit/update-knowledge 各验一次 + 批处理 401 中断，幂等重跑）② **结构拆分**：cli.py 瘦身为 argparse 分发，命令迁入 `qa/commands/` 子包（login/status/run/submit/reset/update_knowledge/suggest/report_cmd/_common）③ **生成环节**：新增 `knowledge/generation-guide.md` 生成指南（六环节）+ 学习机制（候选报告展示设计逻辑、submit 展示 hypothesis、今日学习要点、playbook 双读者化）④ **语言阶段感知**：候选 JSON 增加可选 `language` 字段（默认 FASTEXPR），validate 对非 FASTEXPR fail-closed 拒绝 ⑤ **删本地每日预算与每日配额检查**：status 不展示配额、run 不做每日截断——模拟时平台 429/THROTTLED 提示后处理（429 退避、THROTTLED 暂停），分钟限流批间等待保留，本地 2000 兜底删除 ⑥ **并发参数化**：固定 3 + `--concurrency` ⑦ **中断恢复**：simulations 表落库平台 sim_id，重跑有 sim_id 续查 / 404 回退重提 ⑧ **失败→优化**：优化并入下一个生成批次（agent 自主决策 + 止损报告），failures 按 failure_reason 归因统计（模拟/提交归因分离）⑨ **外部经验通道**：新增 `knowledge/community.md`，update-knowledge 时询问用户是否同步更新 ⑩ **提交边界**：相关门被拒即弃不重试、`qa report --pending` 批量预览、run 报告补 corr 展示。**每周复盘取消**（并入学习要点）。
>
> **v1.5 更新（设计审查 + 实测优化，省配额/提质量）：** ① **候选级模拟参数**：`candidates.json` 每条候选支持可选 `settings`（decay/neutralization/truncation，`validate_settings` 值域校验）——playbook 的 decay 经验值（基本面 0/分析师 0-4/技术 10-30）直接落地 ② **同字段集簇去重**：批次内同字段集候选只模拟最简者（`screener.dedupe_by_fields`，防同主题变体白耗配额）③ **组合视角落地（P3）**：PASS 候选调免费相关门 `/correlations/self` 参与提交排序（corr 低者优先），替代原单指标 score 排序 ④ **待提交自动暂存**：run 的 PASS 候选自动写入 `secrets/pending_submits.json`（幂等），补上跨会话接力缺口 ⑤ **每日模拟配额预算**：本地兜底 2000/天（社区实测 ~800/晚、上界 ~5000）+ **平台每日配额头动态截断**（`GET /users/self` 响应 `x-ratelimit-remaining`，耗尽即停不硬撞 429）⑥ **fail-closed 修复**：`correlations_self` 异常不再返回 0.0 放行提交 ⑦ `qa update-knowledge --force`：24h 内已生成默认跳过（顾问 12 区域重抓很贵）⑧ **死代码清理**：删除 `write_candidates`/`load_field_ids`/`list_failures`/`compute_correlation`/`rank_candidates`/`daily_returns` 表/`ACCOUNT_INFO`/`sub_universe_factor` ⑨ **重复抽取**：cli 经验沉淀 6 处 → `_sediment_lesson/_sediment_failure`；brain_client 429 退避 → `_sleep_on_429`；store JSON 解析 → `_jload` ⑩ 全量测试 85 → 106。**明确未实现（后续批次）：** `optimizer.py`、`--smoke`/`--batch` 参数、RAG 向量检索。
>
> **v1.1-v1.4.1 历次迭代**（认证/阶段检测/知识库本地化/字段类型预检/主动限速等）详见 git log 与下方正文，不再逐条堆叠。

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
- **顾问阶段：每日提交 3 个或以上**当天奖励即封顶（计分口径；Base 计入口径为前 4 个）。
- 学习价值伴随：每个候选附研究逻辑解释。

---

## 2. 核心设计原则（不可违背）

| # | 原则 | 说明 |
|---|---|---|
| P1 | **测试只在平台** | 本地零回测。所有性能测试 = BRAIN API 云端模拟（`POST /simulations` 返回 `is.checks`）。本地仅做表达式规则校验 + 结构简单优化 |
| P2 | **模拟全自动，提交人工确认** | 生成/模拟/筛选/报告全自动；提交必须逐条展示检查结果 + 研究逻辑，等待用户显式确认后 agent 代提交。**禁止无人值守自动提交**（ToS 红线） |
| P3 | **组合视角（alpha 非独立）** | 平台按全部 alpha 的整体表现评判：SELF_CORRELATION 检查（对已提交集 max corr <0.7）、IQC 合并计分（新 alpha 不加值即降分）、Base Quality Factor（低相关得分）。生成与筛选必须考虑与现有组合的关系，不能只盯单 alpha 指标 |
| P4 | **单数据集优先（ATOM）** | 优先生成单数据集表达（ATOM 原则放宽提交标准：只看 2Y Sharpe D1>1）；多数据集需显式标记 |
| P5 | **可分享** | 工具 + 公开知识库（平台文档）随仓库分发；私有数据（cookie/本地字段知识/个人经验/个人成果）gitignore 隔离。**严禁在分享内容中包含真实 alpha 表达式/账号 ID/盈亏数据**；字段元数据按账户权限生成存本地（v1.4） |
| P6 | **YAGNI** | 不做：本地回测、Web UI、多用户、定时任务、D0 支持（需 5000 分解锁）、顾问专属功能（PYTHON/ML、12 区域——由阶段检测启用但 MVP 不实现）。向量检索初期 TF-IDF，**RAG 做成可开关**（FAFM 领域无定论，保留零样本基线 A/B） |

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│  对话层：opencode / claude code / codex 等 agent          │
│  （用户 ↔ agent 自然语言；agent 读 AGENTS.md 后执行）     │
│  （**agent 自身 = 生成引擎**：读 document/ → 生成候选） │
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
│  │ validate  │ │  report   │ │  config   │              │
│  │ (本地预检)│ │ (清单+解释)│ │ (阈值/默认)│              │
│  └───────────┘ └───────────┘ └───────────┘              │
│  ┌───────────┐                                            │
│  │ paths     │                                            │
│  │ (路径单点)│                                            │
│  └───────────┘                                            │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS（仅 BRAIN API 一种外部调用）
┌──────────────────────▼──────────────────────────────────┐
│  BRAIN API（认证/模拟/状态）                              │
└─────────────────────────────────────────────────────────┘
```

### 3.0 启动流程（agent 每次会话的第一步）

```
agent 启动 → `qa status`（会话级环境检查，六项输出：
  新用户判定 / 知识库就绪 / cookie 有效 / 账号阶段 / 待提交暂存 / 教程进度，
  每项给引导动作；只提示不代做登录——输出"请运行 qa login 或提供 Copy as cURL"）
  ├─ 读 cookie（secrets/worldquant_cookies.txt）
  ├─ cookie 缺失/过期 → 认证双选：
  │    ① `qa login --username ... --password ...`（账号密码，凭据不落盘）
  │    ② 用户提供 Copy as cURL → agent 解析写入（对账号密码敏感者）
  ├─ GET /users/self：
  │    401/403 → 会话失效 → 重新认证（上述任一方式）
  │    200 → 解析阶段字段：
  │      level       = BRONZE/SILVER/GOLD（Challenge 等级，分数段位）
  │      geniusLevel = 顾问 Genius 等级（null = 非顾问）
  │      consultant  = 顾问信息（null = 非顾问）
  ├─ 本地知识库检查（experience/fields/meta.json）：
  │    缺失 → 提示"首次运行需先 `qa update-knowledge`"（账户专属字段知识，不上传）
  ├─ 检查待提交暂存 secrets/pending_submits.json（跨会话接力）：
  │    有内容 → 告知用户"有 N 个达标 alpha 暂存待提交"，用户确认后逐个
  │    `qa submit <local_id> --yes`，提交成功从文件删除对应条目
  ├─ 教程进度检查（v1.8，agent 层执行）：读 docs/bootcamp/mastery.json：
  │    未建/达标率 <80% 且用户未声明跳过 → 进入生成前先完成当日学习段
  │    （教材 document/courses/，闭环协议 docs/bootcamp/protocol.md——本地 gitignored）
  └─ 阶段判定 → 动态配置系统变量（见 §4 stage.py）

入口双轨检查（v1.6）：run / submit / update-knowledge 入口各验一次
（GET /users/self，1 请求）；report / suggest / reset 纯本地不验；
run 批处理中途 401 → 中断并提示"会话已过期，剩余 N 个候选未模拟，
已模拟结果已保存（重跑自动跳过）"——幂等设计保证重跑不重复耗配额。
```

### 3.1 每日闭环数据流（九步）

| 步骤 | 动作 | 组件 | 自动化 |
|---|---|---|---|
| 0 | **启动：阶段检测 + cookie 验证 + 本地知识库检查** | stage / brain_client / knowledge | 自动 |
| 1 | **生成前询问主题来源三选一**：① `qa suggest`/agent 随机抽取 ② agent 网络调研热门主题 ③ 用户指定方向 | 对话 | 人工 |
| 2 | **agent（对话层自身）读 `document/flows/generation.md`（生成指南 v1.6，三模式体系见 §三）→ 按六环节执行（固化输入 → 加载知识 → 字段/表达式 → 设置三层决策 → 输出候选 → 质量自检）→ 生成 10-20 个候选 → 写入 `data/candidates/YYYY-MM-DD.json`**（项目不调 LLM；候选格式含可选 `language`，设计逻辑三件套写进 hypothesis，见指南） | 对话层 + candidates | 自动 |
| 3 | **validate 前置预检**（AST 语法 lint + 字段白名单（读本地 experience/fields/）+ 哈希去重 + 复杂度控制 + settings/language 校验） | validate | 自动 |
| 4 | 批量云端模拟（默认 3 并发 / `--concurrency` 可调 / 分钟限流管理 / 429 区分处理 / JSONL 审计 / 中断恢复续查） | brain_client | 自动 |
| 5 | 门槛过滤（用平台 `is.checks` 结果）+ PASS 免费相关门排序（corr 低者优先）+ PASS 自动暂存待提交 + run 报告补 corr 排序值展示 | screener | 自动 |
| 6 | 生成候选清单报告（指标/通过项/逻辑解释/提交建议） | report | 自动 |
| 7 | **用户逐条确认** → agent 调提交 API → **回查 `status==ACTIVE`** | brain_client | **人工确认** |
| 8 | **经验自动沉淀（v1.4 接线）**：模拟 PASS→lessons、FAIL→failures 写入 SQLite + `experience/playbook.md`/`failures.md` 自动追加（幂等去重）；submit 相关门饱和/失败/ACTIVE 同样沉淀 | store + knowledge | 自动 |

### 3.2 失败 → 优化迭代（v1.6：并入下一个生成批次）

```
平台模拟完成 → 分析失败原因（failures 归因：模拟 f_* / 提交 sub_* / 相关门 corr_*）
  → agent 自主决策循环：读本批失败 → 归因分类（方向性 / 参数可修 / 相关门饱和）
    → 决策（调参 / 变体 / 换方向 / 止损）→ 执行（写 YYYY-MM-DD-opt.json，不覆盖原批）→ 输出决策理由
  → 止损纪律：连续 2 批无 PASS → 主动报告建议换方向，由用户拍板，不自动停
  → 合规红线：优化后 PASS 仍走暂存 + 人工确认
（原独立 optimizer.py 规划取消；操作细节见 `document/flows/generation.md` §4）
```

---

## 4. 模块职责（`qa/` 包）

| 文件 | 职责 | 关键实现 |
|---|---|---|
| `config.py` | 配置 | 阈值（Sharpe/TO/自相关）、region/universe/delay 默认值；**阶段相关变量**（并发/区域/字段/语言由 stage.py 动态注入）。**无 LLM 配置——项目不调用 LLM**。v1.6：本地每日预算 `daily_sim_budget` 已删；配额不主动查询（平台 429/THROTTLED 提示后处理） |
| `paths.py` | 路径单点定义 | 仓库内私有文件路径集中管理（COOKIE/ACCOUNT_INFO/DB/AUDIT_DIR/REPORTS_DIR/CANDIDATES_DIR + experience/ 本地知识库路径：KNOWLEDGE_FIELDS_DIR/PLAYBOOK/FAILURES 等）；根目录可注入（测试用 tmp 仓库根） |
| `stage.py` | **账号阶段检测** | 读 cookie → `GET /users/self` → 解析 level/geniusLevel/consultant → 输出阶段配置（并发/区域/字段/语言）。**v1.6：`fetch_self` 401/403 → PermissionError 转换（与 brain_client 约定统一）；status 环境检查 `_env_checks`/`_env_verdict`（返回 new_user/partial/reset/ready）；`StageInfo` 注释 level（分数段位）与 is_consultant（资格）正交** |
| `auth.py` | **账号密码登录** ✅ v1.2 | `POST /authentication`（HTTP Basic Auth）→ 提取 Set-Cookie 的 `t=` JWT 写入 cookie 文件；凭据不落盘、不进审计；401 凭据错误/Persona 人机验证（`WWW-Authenticate: persona`）分别抛异常提示；替代/补充浏览器复制 cURL 方式。v1.6：登录成功写阶段摘要（level/资格/区域/时间，不含密码与分数明细）到 `secrets/account_info.json` |
| `brain_client.py` | BRAIN API 封装 | 认证（读 `secrets/worldquant_cookies.txt`）；模拟 POST+轮询+结果（含 is.checks，实测状态值 `COMPLETE`）；`/correlations/self` 相关门；提交 `submit()` + 回查 `get_alpha()`；**429 区分处理（常规 Retry-After 退避 vs THROTTLED 抛错）**；**空响应/非 JSON body 重试防御**（实测偶发）；分钟限流头读取；`get_json()` 批量读端点（知识库抓取用）；401/403 抛 PermissionError 提示重登 |
| `validate.py` | **本地预检层（省配额核心）** | 语法 lint（括号配对/未知算子）+ **字段白名单校验（读本地 `experience/fields/fields.json`，v1.4；缺失抛 KnowledgeMissingError 引导 `qa update-knowledge`）+ 字段类型检查（v1.4.1：VECTOR 需 vec_* 算子包裹、GROUP 仅限 group_* 的 group_by、UNIVERSE/SYMBOL 禁用）** + **候选级 settings 值域校验（v1.5：decay 0-63/neutralization 枚举/truncation 0-1/未知键拦截）** + **language 校验（v1.6：非 FASTEXPR 直接拒绝并提示"PYTHON 暂不支持本地预检"）** + `expression_fields` 字段提取（v1.5，供簇去重）+ 表达式 SHA-256 哈希去重 + 复杂度控制（算子 ≤30、嵌套 ≤8） |
| `candidates.py` | **候选读入** | 读取 agent 写入的 `data/candidates/YYYY-MM-DD.json`（格式：`[{description, hypothesis, expression, dataset_ids, settings?, language?}]`，v1.5 支持可选 settings 覆盖模拟参数；**v1.6：可选 language 默认 `"FASTEXPR"` + hypothesis 非空校验**）→ 供 validate/screener 处理。**项目内不生成、不调用 LLM**——生成由对话层 agent 完成 |
| `screener.py` | 门槛过滤 + 去重 | 硬门槛：Fitness≥1.0(D1)/1.3(D0)、Sharpe>1.25(D1)/2.0(D0)、TO 1-70%（本地兜底）；平台 `is.checks` 为权威（P1）：FAIL 直接采信、全 PASS 不降级；MARGINAL（距门槛 10% 内）仅当平台 checks 缺失时使用；**同字段集簇去重（v1.5：`dedupe_by_fields`，同信号簇只模拟最简者，省配额）** |
| `store.py` | 持久化 | SQLite（alphas/simulations/submissions/lessons/failures 表）+ JSONL 审计（`append_audit` 返回时间戳关联 simulations.audit_path）；幂等（INSERT OR REPLACE）、中断后重跑跳过已完成项（靠 alphas.ast_hash 去重）。**v1.6：simulations 落库平台 sim_id（模拟成功立即写 PENDING 行，poll 完成 UPDATE 同一条，供中断续查）；`failure_stats` 按 failure_reason 归因聚合（模拟/提交归因分离）；`daily_sim_count` 删除** |
| `report.py` | 报告 | 候选清单 markdown（指标/说明/建议排序 + **v1.6 加设计逻辑 hypothesis 展示 + corr 排序值展示（标注"提交前需复查"）**）；每日达标汇总文档（`reports/daily/YYYY-MM-DD.md` 追加 + 去重） |
| `commands/`（v1.6 新增子包） | **命令实现拆分** | cli.py 仅保留 argparse 分发（~80 行）与 `qa.cli:main` 入口；命令迁入子包，统一签名 `main(paths, cfg, args) -> int`；pyproject 零改动（`include=["qa*"]` 通配覆盖） |
| `commands/_common.py` | run/submit 共用工具 | `_sediment_lesson` / `_sediment_failure` / `_append_pending` / `_remove_pending` |
| `commands/login.py` | 登录命令 | `_cmd_login`（账号密码 → cookie + 阶段摘要写入 account_info.json） |
| `commands/status.py` | 状态命令 | `cmd_status` 增强版（五项环境检查输出，每项带引导动作） |
| `commands/run.py` | 闭环命令 | `cmd_run` + `_simulate`/`_settings`/`_score`/`_load_operators`/`_load_fields`；`--concurrency` 参数化、批处理 401 中断、中断恢复续查 |
| `commands/submit.py` | 提交命令 | `_cmd_submit` + `_wait_for_active`；展示 hypothesis（知情确认）；相关门被拒即弃不重试 |
| `commands/reset.py` | 重置命令 | `_cmd_reset` |
| `commands/update_knowledge.py` | 知识库命令 | 命名避让 `qa/knowledge.py`；外部经验更新由 agent 会话询问（CLI 本身不弹交互） |
| `commands/suggest.py` | 建议命令 | `cmd_suggest` + `_signal_fields`/`_theme_for_dataset`/`_THEMES_BY_CATEGORY` |
| `commands/report_cmd.py` | 报告命令 | 命名避让 `qa/report.py`；`--daily` / `--pending`（批量预览待提交清单） |
| `cli.py` | 命令入口（v1.6 瘦身） | 仅 argparse 分发；历史能力：`qa login`/`qa status`/`qa run`/`qa report`/`qa submit`/`qa reset`/`qa update-knowledge`/`qa suggest` 命令本体已迁至 `qa/commands/`。run 历史实现含并发模拟（ThreadPoolExecutor 分批，写库回主线程避免 sqlite 跨线程）+ 批间主动限速 + 候选级 settings 合并 + 字段集簇去重 + PASS 免费相关门排序 + 待提交自动暂存 + 经验沉淀（`_sediment_lesson/_sediment_failure`） |
| `optimizer.py` | 优化循环 | **已取消（v1.6）**——优化并入下一个生成批次循环（agent 自主决策 + 止损报告，见 `document/flows/generation.md` §4），无独立代码优化器 |
| `knowledge.py` | **本地知识库管理（v1.4 实现）** | 按账户阶段抓取字段（`/data-sets` + `/data-fields`，分页 + 限流节流 ~2s/请求）→ 写 `experience/fields/{fields,top_fields,meta}.json`（全量白名单/top 参考/状态 meta）；读取接口 `load_field_ids`/`load_top_fields`/`knowledge_status`；经验沉淀 `append_experience`（playbook/failures 自动追加，按 entry_id 幂等去重；v1.6 失败条目按失败名补一句修复建议——查 rules.md 失败→修复映射表）/`restore_experience_templates`（reset 用） |

### 4.1 命令清单（agent 工作流接口）

| 命令 | 功能 | 说明 |
|---|---|---|
| `qa login [--username ...] [--password ...]` | **账号密码登录** ✅ | `POST /authentication`（Basic Auth）→ 写 `secrets/worldquant_cookies.txt` 并验证会话；凭据不落盘/不进审计；无参数时交互输入（getpass 不回显）；Persona 验证提示人工处理。v1.6：成功写入阶段摘要到 `secrets/account_info.json` |
| `qa status` | **会话级环境检查** ✅ v1.6 增强 | **五项输出：新用户判定 / 知识库就绪 / cookie 有效 / 账号阶段 / 待提交暂存**，每项给引导动作；只提示不代做登录；阶段检测（配额不展示——模拟时平台 429/THROTTLED 提示后处理） |
| `qa run [--candidates-file ...] [--concurrency N]` | 完整闭环：读入候选→预检→模拟→筛选→报告 ✅ | **候选由 agent 写入 `data/candidates/` 后项目读入**（默认读当日文件）；字段白名单读本地知识库（缺失报错引导首跑）；并发模拟（默认 3，v1.6 `--concurrency` 可调）；结果落库（save_alpha + save_simulation + 审计）；经验自动沉淀；入口快验 + 批处理 401 中断 + 中断恢复续查（v1.6） |
| `qa report [--daily] [--pending]` | 查看报告 ✅ | 当日候选清单 / 每日累计汇总；**v1.6 `--pending` 批量展示待提交暂存清单（含指标 + 相关门排序，提交仍逐个人工确认）**；候选清单含设计逻辑 hypothesis 与 corr 排序值展示 |
| `qa submit <alpha_id> [--yes]` | 人工确认后提交 ✅ | 展示全部检查 + **hypothesis（v1.6 知情确认）** + 免费相关门 → 交互确认（或 --yes agent 代提交）→ `POST /alphas/{id}/submit` → **轮询回查 ACTIVE**（平台状态更新有延迟）；**相关门被拒即弃不重试（v1.6）**；写 submissions 表 + 审计；相关门饱和/失败/ACTIVE 沉淀经验 |
| `qa reset [--yes]` | **清除经验，回到初始状态** ✅ | 删除 qa.db/audit/candidates/reports/daily/ + secrets/pending_submits.json + experience/playbook/failures 恢复模板；**保留** secrets/ 凭证、document/ 公开库与 experience/fields/ 字段知识；执行前展示清单 + 确认（合规） |
| `qa update-knowledge [--regions ...] [--force]` | **按账户抓取字段知识 → 写本地 experience/fields/** ✅ v1.4（v1.5 加 --force） | 首次运行必做；按账户阶段抓区域（用户=USA / 顾问=12 区域）；`--regions USA,KOR` 限定；限流节流 ~2s/请求；**24h 内已生成默认跳过，`--force` 强制刷新（v1.5）**；数据 gitignored 不上传；**v1.6：agent 在会话中询问"是否同时更新外部经验"（CLI 不弹交互）** |
| `qa suggest` | 随机建议研究方向 ✅ v1.4 | 本地知识库随机数据集+top 字段+主题模板，供 agent 生成候选时作主题来源 |

---

## 5. 组合视角设计（P3 落实细节）

| 层面 | 机制 | 数据来源 |
|---|---|---|
| 生成前 | knowledge 提供现有 alpha 库的字段/信号簇分布 + **字段饱和度（alphaCount）** → LLM 提示"避开已饱和簇"；**信号簇按数据来源/经济逻辑划分（非算子族）** | `store.alphas` 聚合 + 字段元数据 |
| 筛选时 | 平台 `SELF_CORRELATION` 检查（对已提交集相关性）作为硬门槛 | 平台模拟结果 |
| 批次内 | 同批候选 **同字段集簇去重**（v1.5：同信号簇只保留最简者模拟；相似表达式只留最优） | 本地字段集（`expression_fields`） |
| 提交前 | **免费相关门 `GET /alphas/{id}/correlations/self`**：max<0.7 才允许提交（实测可用，不耗提交预算；v1.5 fail-closed：响应异常抛错不放行） | 平台 API |
| 提交排序 | PASS 候选逐个调免费相关门，**max_corr 低者优先**（v1.5 落地，替代原单指标 score 排序；IQC 等权合并逻辑近似） | 平台相关性 + 指标 |

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
| `simulations` | id, alpha_id, request_json, result_json, checks_json, status, started_at, finished_at, audit_path | 每次模拟请求/结果/审计。**v1.6：id 落库平台 sim_id**——模拟成功立即写 PENDING 行，poll 完成 UPDATE 同一条；中断续查：有 sim_id 续查 / 404 回退重提 |
| `submissions` | id, alpha_id, submitted_at, user_confirmed(bool), platform_response, current_status(ACTIVE/OS/降级), **confirmed_active(bool)** | 提交记录与状态跟踪（含 ACTIVE 回查） |
| `lessons` | id, trigger(指纹diff/失败原因), **hypothesis**, **verdict(评审结论)**, lesson(脱敏), raw_ref, created_at | 经验教训（脱敏写入 playbook；**成功 alpha 的"为什么有效"也记录**） |
| `failures` | id, expression_hash, failure_reason, created_at | **证伪库**（已证伪路径，避免 LLM 重复走死路）。**v1.6：按 failure_reason 归因统计（`failure_stats`）；前缀区分模拟 f_* / 提交 sub_* / 相关门 corr_*** |

审计：`data/audit/*.jsonl` 不可变日志（模拟/提交全记录）。

**candidates.json 条目格式（v1.6）：** `{description, hypothesis, expression, dataset_ids, settings?, language?}`——
`language` 默认 `"FASTEXPR"`（validate 对非 FASTEXPR fail-closed 拒绝）；`hypothesis` 必填非空
（设计逻辑三件套：假设 / 预期信号来源 / 可能失败点）。

---

## 8. 项目结构（可分享布局）

```
QuantAlpha/
├── AGENTS.md                    # ⭐ 跨 agent 工作流入口（目标/启动流程/命令/合规红线）
├── README.md                    # 人类说明：安装、认证配置（双选）、快速开始、使用者上手指南
├── quantalpha-design.md         # ⭐ 本文件：设计文档（智能体职能说明书）
├── qa/                          # Python 工具库
│   ├── (auth, config, stage, brain_client, validate, candidates,
│   │    screener, report, store, paths, knowledge).py
│   └── commands/                # v1.6 命令子包（login/status/run/submit/reset/
│                                #      update_knowledge/suggest/report_cmd/_common）
├── document/                    # ✅ 公开文档（仓库核心，随仓库分发）
│   ├── quantalpha-design.md     # 本文档（权威设计）
│   ├── flows/                   # 流程控制（startup/generation/submission/experience/access/update-knowledge/learning）
│   ├── courses/                 # 教程教材（v1.8）：四节新手课笔记 + 官方教程提取 + 官方作业题
│   └── reference/               # 知识参考（operators/rules/pitfalls/fields/community/templates）
├── docs/                        # 🔒 gitignored：skill 产物（spec/plan 存档）+ bootcamp 个人学习状态
│   └── bootcamp/                #   RLHF 闭环协议/mastery 档案/双计划/摸底与答题记录
├── experience/                  # 🔒 gitignored：本地账户知识库（字段元数据 + playbook + failures）
│   ├── fields/                  #   qa update-knowledge 生成：fields.json/top_fields.json/meta.json
│   ├── playbook.md              #   经验沉淀（自动追加）
│   └── failures.md              #   证伪库（自动追加）
├── pyrightconfig.json           # LSP 配置（basedpyright：venv 解释器 + basic 检查模式）
├── data/                        # 🔒 gitignored：qa.db + audit/ + candidates/
├── reports/                     # 🔒 gitignored：个人每日成果（可选分享）
├── secrets/                     # 🔒 gitignored：cookie、account_info.json、pending_submits.json（账号密码绝不落盘为文件）
└── pyproject.toml
```

**gitignore 安全线：** `data/`、`reports/`、`secrets/`、`experience/`、`audit/`（预留）全部忽略——其他使用者克隆只拿到工具+公开知识库，不含任何私有数据（字段知识/经验/凭证）。待提交暂存 `secrets/pending_submits.json` 位于 secrets/ 下自动覆盖。

---

## 9. 错误处理与配额管理

| 场景 | 处理 |
|---|---|
| cookie 过期（~4h JWT 会话） | brain_client/stage 检测 401/403 → PermissionError → 报告"请重新认证"（`qa login` 账号密码，或浏览器复制 Cookie）→ 暂停流程等待。**v1.6 分支输出**：cookie 不存在 → "请运行 qa login 或提供 Copy as cURL"；PermissionError → "cookie 已过期：请运行 qa login"；网络异常 → "cookie 有效性未验证" |
| **批处理中途 401**（v1.6） | `_simulate` 单独捕获 PermissionError → 中断标志 → chunk 循环 break → 提示"会话已过期，剩余 N 个候选未模拟。已模拟结果已保存（重跑自动跳过），请 qa login 后重试"；幂等保证重跑不重复耗配额。submit/update-knowledge 报错修正为"登录失效：请 qa login" |
| **429 常规限流** | GET/POST 均按 `Retry-After`（float，clamp [1s,120s]）退避重试 3 次；仍失败抛 TimeoutError 中止该候选 |
| **429 + `THROTTLED`**（平台相关性子系统卡死） | 非普通限流 → 提示"平台故障，稍后重试"，暂停批处理 |
| **分钟限流（实测 30 req/min）** | `rate_limits()` 读取 `x-ratelimit-remaining-minute`；**批处理主动限速已接入（v1.4.1：run 批间剩余 ≤3 时等待窗口重置；v1.5：无 reset 头时按窗口消耗比例估算等待；update-knowledge 固定节流 ~2s/请求）** |
| **每日模拟配额** | **不主动查询**：status 不展示、run 不做每日截断；模拟时平台 `DAILY_SIMULATION_LIMIT_EXCEEDED` 错误码 / 429 退避 / THROTTLED 暂停兜底（本地预算与每日截断均已删） |
| LLM API 失败/限流 | 重试 2 次 → 跳过该候选，不阻塞整批 |
| 模拟结果异常（NaN/空） | 标记 FAIL_INFRA，不计入失败统计 |
| **模拟超时/poll 失败** | 保留原 `Location` 续查，**不盲目重提**（防重复消费配额） |
| 提交失败（检查未过/重复/SC） | 解析平台错误 → 写入 lessons/failures → 报告用户；**相关门被拒即弃不重试（v1.6）** |
| 中断恢复（v1.6） | simulations 表记录平台 sim_id 与状态：**有 sim_id → 续查 poll；无 sim_id 或 404 → 重提**；重跑跳过已完成项（幂等） |

---

## 10. 测试策略与 MVP 范围

**测试（随版本持续扩展，`pytest qa/tests/` 全过）：**
- candidates：候选 JSON 读入/容错单测
- validate：语法 lint / 字段白名单 / 哈希去重 单测（LLM 幻觉字段拦截验证）
- screener：门槛逻辑单测（构造数据模拟 PASS/MARGINAL/FAIL）+ 相关性计算单测 + 平台 checks 全 PASS 不降级
- store：SQLite CRUD + 幂等 + 审计
- brain_client：mock HTTP（不真调 API）+ 429 退避 + 空响应重试防御 + submit/get_alpha
- stage：users/self 响应解析单测（BRONZE / 顾问 / cookie 失效三种形态）
- auth：登录成功提取 t= / 200 也接受 / 多 Set-Cookie / 401 凭据错误 / Persona / 缺 cookie
- cli：命令分发 + run 端到端 + submit 端到端 + reset 清除 + status 知识库提示 + update-knowledge 端到端 + suggest + run 自动沉淀（mock 阶段检测与模拟）
- knowledge（v1.4）：构建写文件/分页/防御解析/top 字段/读取/经验追加去重/模板恢复
- 真实调用：`qa login` 实测成功（用户阶段；JWT `amr=['pwd']` 证实 API 登录无需验证码）+ 401 错误路径实测 + 提交 ACTIVE 实测

**MVP 状态（v1.6）：**
- ✅ 第一批完成：config + paths + store + stage + auth + validate + candidates + brain_client(模拟/提交) + screener(门槛) + report + cli(login/status/run/report/submit/reset)
- ✅ v1.4 完成：update-knowledge（按账户抓字段→本地）+ suggest（随机主题）+ 经验自动沉淀接线（run/submit → SQLite + experience/playbook/failures）+ 知识库本地化拆分
- ✅ v1.4.1 完成：validate 字段类型检查 + suggest 过滤无效类型字段/主题按类别匹配 + run 批间主动限速 + 设计备忘补 instrumentType
- ✅ v1.5 完成：候选级 settings + 字段集簇去重 + 相关门排序 + 待提交自动暂存 + 每日配额预算（2000+平台头动态截断）+ fail-closed 修复 + update-knowledge --force + 死代码清理与重复抽取（85→106 测试）
- ✅ v1.6 完成（流程深化批次）：status 五项环境检查 + 入口双轨检查 + 批处理 401 中断；commands/ 子包拆分；generation-guide.md / community.md 新建；language 字段 + fail-closed；删本地每日预算；--concurrency；sim_id 中断恢复；失败归因统计（模拟/提交分离）；提交边界（相关门被拒即弃、report --pending、corr 展示）
- ⏳ 顾问冲刺前可选：qa teach 学习模式（每周复盘已取消）
- 明确不做（现阶段）：向量检索（RAG 开关预留）、Web UI、多用户、定时任务、D0、复杂组合优化、独立 optimizer（并入生成循环）、顾问专属功能（PYTHON/ML、12 区域——由阶段检测启用但 MVP 不实现）、**项目内 LLM 调用（生成在 agent 侧）**

---

## 11. 合规红线（系统硬约束）

1. **禁止**无人值守自动提交；提交前必须展示检查结果并等待用户显式确认（P2）
2. **禁止**分享真实 alpha 表达式/账号 ID/盈亏数据（P5）；playbook 必须脱敏
3. **禁止**长期挂机/异常活跃模式（模拟配额内运行，不做 24h 刷量）
4. **允许**：AI 生成初步想法、批量模拟、优化流程、复盘（平台官方 AI 立场）
5. 系统私有部署；表达式仅发往 BRAIN API 与 LLM API

---

## 12. 知识库分层（v1.4 落地，v1.8 增教程层）

**公开 `document/`（随仓库分发）分三类：**
- `document/flows/` —— 流程控制（7 份：startup/generation/submission/experience/access/update-knowledge/learning）
- `document/courses/`（v1.8 新增）—— **教程教材**：官方公开课《零基础学量化》四节新手课笔记（官方公开课转录清洗，来源标注）+ 官方 /learn 教程 13 页提取 + 官方课程作业题 3 份；答疑内容不单独保留，知识增量归并入 reference/（去重后补充，见 courses/README"答疑内容去向"）
- `document/reference/` —— 知识参考（operators/rules/pitfalls/fields/community/templates，平台公开文档 + 脱敏方法论）

**本地（gitignored）：**
- `experience/` —— 账户专属：字段元数据（qa update-knowledge 生成）+ playbook/failures（个人经验）
- `docs/bootcamp/`（v1.8）—— 个人学习状态：mastery 档案/计划/摸底与答题记录/模拟卷（RLHF 闭环协议，见 `document/flows/startup.md` §4 与 `docs/bootcamp/protocol.md`）

**学习与产出的配合**：教程未通过者（六项检查第 6 项）→ 生成前先完成当日学习段；教学模式 = 学习与生成自然融合；参考官方示例作候选灵感合规（官方公开材料）。

**`qa update-knowledge` 已实现：** 按账户阶段（用户=USA / 顾问=12 区域）抓取字段元数据 → 写：

| 文件 | 内容 | 用途 |
|---|---|---|
| `experience/fields/fields.json` | 全量字段 `{id, description, dataset, type, coverage, userCount}` | `qa run` 字段白名单（validate） |
| `experience/fields/top_fields.json` | 每数据集 userCount top 15 | agent 生成候选选字段 + `qa suggest` |
| `experience/fields/meta.json` | 生成时间/阶段/区域/数量 | `qa status` 展示 |

- 抓取：`GET /data-sets` → 每数据集 `GET /data-fields?dataset.id=...`（分页 limit=50，offset 翻页；防御解析 `{results:[]}` 与裸数组两种形态）
- 限流节流：~2s/请求（30 req/min 分钟配额内安全）；429 由 brain_client 退避兜底
- 首次运行必做：`qa status` 检测缺失提示；`qa run` 缺失即报错引导

**关键 API 备忘（已实测验证，供后续 agent）：**
- 认证：`POST /authentication`（HTTP Basic Auth，email:password）→ 201 + Set-Cookie `t=` JWT（**会话 ~4h**，`token.expiry ≈ 14222s`；API 登录 JWT `amr=['pwd']` 无验证码——Altcha PoW 仅用于注册 `POST /users`）；`DELETE /authentication` 登出；Persona 人机验证：401 + `WWW-Authenticate: persona` + `{"inquiry": ...}` → `POST /authentication/persona`
- 会话/阶段：`GET /users/self` → `level`/`geniusLevel`/`consultant`（阶段检测）；`GET /users/self/consultant` 403=非顾问
- 数据集枚举：`GET /data-sets?region=USA&universe=TOP3000&delay=1&instrumentType=EQUITY&limit=20`（limit 上限 ~50）
- 字段元数据：`GET /data-fields?dataset.id={id}&region=...&delay=1&universe=TOP3000&instrumentType=EQUITY&limit=50&offset={n}`（**参数名是 `dataset.id` 点号写法**，不是 `dataset`；**`instrumentType=EQUITY` 必带**，缺失返回 400 `["Invalid query"]`——v1.4.1 实测）
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
| 知识分享 | 公开平台文档随仓库分发；**字段元数据/playbook/failures 本地化不上传（v1.4 用户拍板）** | 字段可用范围随账户权限变化；表达式/字段研究属个人数据，分享价值低且敏感 |
| 优化循环 | 仅 MARGINAL ≤2 轮轻调 + 止损式触发 | 省配额（用户要求"简单优化"） |
| **优化循环（v1.6）** | 取消独立代码优化器——优化 = 下一个生成批次（agent 自主决策循环 + 止损报告，见 `document/flows/generation.md` §4） | 调参重试是下一批候选的自然组成，无独立代码路径 |
| **配额管理（v1.6）** | 删本地每日预算，以平台每日配额头（x-ratelimit-remaining）为准 | 平台保护链完整；本地保守值反而浪费可用配额 |
| **外部经验通道（v1.6）** | 新建 knowledge/community.md，update-knowledge 时询问用户是否同步更新 | L4 传闻层入库需用户确认，防掺私有数据 |
| 检索 | TF-IDF 起步，RAG 可开关 | YAGNI，后期可升 RAG |
| 生成批次 | 10-20 个/轮 | 非顾问每日 1-2 个成功即可；省配额 |
| **LLM 调用** | **项目内不调用 LLM**——生成由对话层 agent 完成（读 document/ 写候选文件） | 用户拍板：agent 读项目文件后直接生成 alpha 写入项目，项目跑后续流程 |
| **账号阶段检测** | 启动时 users/self 判定 → 动态配置 | 非顾问/顾问变量差异大（并发/区域/字段/语言） |
| **认证方式（v1.2）** | 双选：`qa login` 账号密码（推荐，可自动续期）或浏览器复制 cURL（敏感用户） | 账号密码不落盘/不进审计；会话 ~4h，长时间模拟需重登 |
| **并发模拟（v1.2）** | `qa run` 内 ThreadPoolExecutor，并发数取阶段检测值；写库回主线程 | API 允许 3 并发；sqlite 连接跨线程不安全 |
| **validate 前置层** | LLM 生成后、模拟前本地预检 | 拦截幻觉字段/语法错，省无效模拟配额 |
| **相关门** | 提交前 `/correlations/self`（max<0.7）+ 日收益相关 | 避免浪费提交槽位；累计 PnL 相关会误判 |
| **计分策略** | 每日集中提交 1-2 个高质量（美东 3AM 日界） | 官方计分规则：每日 2000 分封顶、相对分 |
| **知识库本地化（v1.4）** | 字段/经验本地生成，公开仓库只留平台文档 | 用户拍板：账户权限差异 + 敏感数据不上传；首次运行 `qa update-knowledge` 生成 |
| **经验自动沉淀（v1.4）** | run/submit 后 PASS→lessons、FAIL→failures 自动写 SQLite + experience/ markdown（幂等去重） | 沉淀闭环指导后续生成；省人工整理 |
| **学习定位（v1.8）** | 产出 + 知识掌握双轮：教程未通过（六项检查第 6 项）→ 生成前先完成当日学习段；教学模式 = 学习与生成融合 | 平台收紧审核（笔试+面试考察基本知识）；知识不足则无法通过面试，系统无后续价值 |
| **快速模式引擎（v1.8）** | 三引擎 → 两引擎（删失败优化——已并入常规迭代 §4，避免重复路径） | 失败优化 = 下一个生成批次的自然组成，无独立引擎必要 |
| **教材分层（v1.8）** | 通用教材 `document/courses/`（官方公开材料，随仓库分发）；个人学习状态 `docs/bootcamp/`（mastery/摸底/答题记录，gitignored） | 公开知识可分享（符合 P5）；个性化安排属个人数据（账号/进度），隔离在本地上传之外 |

---

## 附：todo-design 终结合并记录（v1.7）

> `data/todo-design.md` 临时决议文档已终结（2026-09-01）。已实现决议全部落库（git log 与正文可查），
> 未实现项整理为下方 Backlog；身份差异备忘已并入 `document/flows/access.md`。
>
> **v1.8 追加**：教程学习体系（bootcamp）决议见 `docs/superpowers/specs/2026-09-03-bootcamp-design.md`；
> 通用教材已入 `document/courses/`（公开），个人学习状态在 `docs/bootcamp/`（gitignored）。

### Backlog（未实现，按优先级）

| 优先级 | 事项 | 说明 |
|---|---|---|
| ~~P1~~ | ~~算子白名单不一致~~ | ✅ **已解决（2026-09-01 核对）**：`qa/commands/run.py:_load_operators` 67/67 与官方 API 完全一致（trade_when/bucket/ts_regression/vector_neut 等 14 个已补） |
| P1 | D0 路径未走通 | config 已定义 D0 阈值从未使用；screener 只走 D1；delay 固定 1、候选 settings 无法指定 delay=0；ATOM 规则无代码（对话层） |
| P2 | 已提交簇聚合查询 | 组合视角"生成前避开饱和簇"无 store 查询接口，`qa suggest` 不带已提交信号簇信息 |
| P2 | 顾问阶段并发上限 | 未确认平台分钟限流是否随顾问提高；--concurrency 已参数化，成为顾问后实测 x-ratelimit-limit-minute 再决定 |
| P3 | 生成侧代码未强制规则 | dataset_ids 与表达式字段归属一致性、保留字冲突、规模乘子禁忌（rank(-assets)） |
| P3 | PYTHON/ML 语法 | stage 已检测但 validate 不支持；language 字段 + fail-closed 已落地，完整校验留待顾问阶段 |
| P3 | 学习模式 qa teach | 顾问冲刺前可选；bootcamp 学习闭环（docs/bootcamp/，v1.8 已落地于对话层）验证后，如需代码化（CLI 管理 mastery/摸底卷）届时设计 |
| P3 | 教程进度代码化 | 六项检查第 6 项目前由 agent 读 `docs/bootcamp/mastery.json` 执行；若需 `qa status` 直接输出（含教程进度），代码化后并入 status |

### 身份差异事实备忘（已核实，已并入 access.md）

- `is_consultant = consultant is not None or geniusLevel is not None`——与 level 正交
- level（BRONZE/SILVER/GOLD）= 分数段位（>1000/>5000/>10000）；顾问 = 10000 分 + Gold + 完整流程——GOLD 用户还不是顾问
- D0 解锁：`d0_available = is_consultant or level in ("SILVER","GOLD")`（5000 分解锁）
- 顾问后变化清单：区域 USA→12、字段库扩大、语言 +PYTHON/ML、D0 可用、门槛 D1→D0、模拟 delay 1→0、计分规则（提交 3+ 封顶）
