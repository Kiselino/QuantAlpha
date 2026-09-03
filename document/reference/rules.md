# 平台规则速查（BRAIN）

> 供 agent 生成候选与筛选时参考。权威来源：官方 help center 文章 + 官方社区帖子 + quantalpha-design.md。
> **核对日期：2026-09-01**（Fitness/门槛/计分/子宇宙/D0 解锁/顾问条件逐项与官方文章核对一致）。

## 提交门槛（硬性）

| 指标 | 要求 |
|---|---|
| Fitness | ≥1.0（D1）/ ≥1.3（D0） |
| Sharpe | >1.25（D1）/ >2.0（D0） |
| Turnover | 1% ~ 70%（理想 <40%） |
| 自相关 | <0.7（Sharpe≥1.375 可豁免） |
| 子宇宙 | `subuniverse_sharpe ≥ 0.75·√(sub/alpha)·alpha_sharpe` |
| 单股权重 | <30%（目标 ≤10%） |

> 数值以 quantalpha-design.md 提交门槛章节为准（本表为速查）。
> 官方口径：Sharpe 最低 2.0（D0）/ ~1.25（D1）才够格进入 Out-of-Sample 测试；
> Turnover "try to keep below 40%, definitely below 70%"（官方文章 5969494957079）。

**Fitness 公式（官方）：** `Fitness = Sharpe · √(|Returns| / max(Turnover, 0.125))`——高 Return、高 Sharpe、低 TO（<40% 更佳）三管齐下（官方文章 20251386376471）。

**ATOM 原则：** 单数据集表达（只用 1 个数据集的字段，**排除 country/sector 等分组字段**）放宽提交标准——只看最近 2Y Sharpe（USA D1>1.0），不做完整 IS Ladder 测试。**生成候选应优先单数据集**。

**Test Period 机制：** IS 内划分 Train/Test（橙色 = test 段），统计默认看训练段；提交前必须显示 Test Period（walk-forward 反过拟合）。相关设置项：testPeriod 范围 P0-P6Y、lookback 0-1024、selectionLimit 10-1000、selectionHandling POSITIVE。

## 提交检查管线（平台全套 check，提交前 agent 应自检同维度）

- 相关性：`SELF_CORRELATION`（对已提交集日收益 max Pearson <0.7）、`PROD_CORRELATION`
- 收益类：`SHARPE` / `SUB_UNIVERSE_SHARPE` / `SUPER_UNIVERSE_SHARPE` / `RANK_SHARPE` / `PRE_CLOSE_SHARPE` / `Y_SHARPE` / `IS_LADDER_SHARPE` / `CLUSTER_TEST`
- 换手类：`HIGH_TURNOVER` / `AFTER_COST_SHARPE` / `HIGH_TURNOVER_RETURNS_RATIO` / `INVESTABLE_MAX_POSITION_*` / `ORTHOGONAL_RAM_NEUTRALIZATION` / `PNL_REALIZATION_HORIZON` / `TURNOVER`
- 结构类：`IMBALANCE` / `CONCENTRATED_WEIGHT` / `WEIGHT` / `DRAWDOWN` / `BIAS` / `WITH_RATIO` / `WITH_VALUES` / `REVERSION_COMPONENT`
- 编译/资格：`COMPILE_ERROR` / `INVALID_CODE` / `INVALID_UNIVERSE` / `AVAILABLE_SETTING` / `USER_DEFINED_FIELDS` / `DUPLICATE_ALPHA` / `ALREADY_SUBMITTED` / `DATA_DIVERSITY` / `DATA_SET_AUTHORIZATION` / `REGION_AUTHORIZATION`
- 配额类：`REGULAR_SUBMISSION` / `RESEARCHER_REGULAR_SUBMISSION` / `SUPER_SUBMISSION` / `POWER_POOL_*` / `REGULAR_SUBMISSION_REACHED` / `D0*`

## 模拟默认设置（对齐平台）

delay=1、universe=TOP3000、truncation=0.08、decay=0、neutralization=INDUSTRY、pasteurization=ON、nanHandling=OFF、testPeriod=P1Y。

## 字段优先级（通过率实证）

**基本面 40% > 混合 12.7% > 纯技术 5.3% > 其他 0%**

- 黄金组合：`group_rank(ts_rank(x, N), subindustry)`
- decay 经验值：基本面 0 / 分析师 0-4 / 技术 10-30；truncation 0.05-0.1
- 失败主因：LOW_SHARPE 90.7% / LOW_FITNESS 66.2% / LOW_SUB_UNIVERSE_SHARPE 51.0%

## 计分规则

- 每日最高 2000 分（通常 1-2 个高质量 alpha 即达）；相对分（看当天其他用户）
- 得分 = Quantity Factor × Quality Factor（按当日提交用户归一化）；Quality Factor 依赖：Universe（**越小分越高**）、SelfCorrelation（越低越好）、Fitness、Delay（**D1 比 D0 贡献更多**）
- 等级：Bronze>1000 / Silver>5000 / Gold>10000；**10000 分 → 顾问邀请资格**
- 小宇宙（TOP500/200）+ D1 比大宇宙/D0 得分更高
- 美东 3AM 结算（"日"边界按美东，非本地）；T+1 记账（约北京 14-15 点）
- IQC：最终分 = 25% IS + 75% OS；IS Score = D1 Score + D0/3；评分指标 = 合并序列 Sharpe / Returns-Drawdown / Turnover（<12.5% 不再加分）
- **IQC 组合观**（官方课口径 2026-04）：比赛考察**一段时间内 Alpha 组合的质量**而非单纯数量；组队时队友提交的差 alpha 会拉低整体分数——提交前可用平台 **Performance Comparison** 功能预览分数增减（新人课推荐流程：提交前先预览再交）
- **质量分机制（官方课口径）**：顾问质量分 = 排名分（默认 0.5；**只有拿过钱的 alpha 才计入**；约 3 个月不提交 alpha 质量分会被重置）；质量分 0.3 → 提交最强的 alpha 日收入也仅 ~1 USD，0.9 → 十几 USD；组合泥潭效应：已有差 alpha 时交 1 个差的约需 10 个好的才能扭转 → **宁缺毋滥，维护质量分优先于数量**
- D0 访问权限：需 5,000 Individual Qualifier Score

## 收入机制（顾问阶段）

| 组成 | 金额 | 核心变量 |
|---|---|---|
| Base Payment | 1-60 USD/天 | 每日前 4 个 alpha + 每月前 5 个 D0 计入；Value Factor + Quantity + Self Growth（注：顾问阶段"提交 3+ 个当天奖励封顶"为计分口径，Base 计入口径为前 4 个） |
| Quarterly Payment | 100-25000 USD/季 | Weight Factor + Value Factor；当季 ≥20 提交天门槛；IQC 期间顾问 Net Weight≈0 |
| Competition | 奖池（ATOM/IQC 等） | 名次（IQC 2026 奖池 $100k，较 2024 $400k 缩减中） |
| Referral Bonus | 100-200 USD/人 上不封顶 | 官方页 $100/人（被荐者提交 10 天+顾问满 1 月）；中文论坛经验 $200/人（被荐者成顾问且提交 >10 天） |

- **1.5USD 大法**：当日只交 1 个 alpha，Base ≥1.5 → 质量不错；只有 1.2 需警惕
- 前 3 个月是"试用期"，核心目标是**积累 Value Factor**，之后收入数倍提升
- **Super Alpha**：累计提交 100 个 alpha 后解锁，可组合已有 alpha（每日 1 个上限，收入常更高）；社区门槛经验：fit>5 + prod corr<0.7
- **ACTIVE 计重**（官方 19218586723991）：**仅顾问**的 ACTIVE alpha 可累积 weight；用户阶段 ACTIVE 不产生 weight
- **DECOMMISSIONED 状态**（官方 19218490444823）：数据集下架（无法再模拟）/ OS 期长期表现不佳 / 平台裁定——提交后 alpha 可能被停用
- **研究小组**：提交 30 个 alpha 后可申请，双周评比有额外奖金
- 评级（Spectacular/Excellent）≠ 高 Quality Factor / 高 base
- 税务：劳务报酬代扣代缴（800 以下免税、以上 20%）；平台依法自动代扣，勿因税费误解恶意举报税务机关（可能影响账号）；Base 每两月发放 + Quarterly 每季（1/3/5/6/7/9/11/12 月发薪日）

## 顾问路径（中国区官方流程）

10,000 分 + Gold → 进入 Challenge - Mainland China 排行榜（近 60 天有提交的 Gold 用户综合排名：IS Score + Uniqueness + 提交天数）→ 研究能力测试笔试 → 5 分钟面谈（身份核实 + 平台基础知识）→ Workday 顾问申请表 → 背调（授权书+身份证+问卷）→ 签约 → 填银行卡 → **Full Consultant**。顾问每月须保住 ≥1 个合格 alpha，否则 Tier-2 归零。

**考核与工作性质（官方课口径 2026-04，与官方帖 2026-06 核实互补）：**
- **Knowledge Quiz（知识问答）**：成为顾问前的硬性审核（即使不参加培训也要过）；**两次机会**，都不过则无法成为顾问；非选拔性考试，只排除对基础概念一无所知者（问"什么是 alpha"级别）；**必须真理解而非背答案**——官方明示"纯靠 AI 过不了"
- 研究能力测试为**邮件问卷形式（一般中文）**，按邮件要求作答
- 顾问工作**无强制 KPI / 无每日最低提交量**，时间投入自定（官方：每天 1-2 小时也可能收入可观）
- 满 1 万分系统自动触发申请邀请（积分无时效；每日提交上限 2000 分 → 最快 5 天）
- 活跃顾问约 4000 人（上限 1 万人），中国区约 1000+，其中月质量分 >0.8 者 300+
- **背调会联系 HR/雇主核实**；无学历硬性要求，一般不索无犯罪证明；个人炒股属个人爱好，不算"金融从业"

**IQC 与顾问身份（官方课口径）：**
- **IQC = 新手专属，一人一次**：成为普通顾问后不能再参加；比赛结束自动转普通顾问
- IQC 顾问有顾问权益（base/季度奖）但高级功能受限（更多算子/字段）——比赛公平
- IQC 获奖会**查验学校/身份**；组队须同校/校友（不符取消资格）；组队后分数合并计算可能不增反降

## 组合视角（alpha 非独立）

- 提交检查 `SELF_CORRELATION`：与已提交全部 alpha 日收益 max Pearson <0.7
- **Sharpe 相关豁免通道**（官方教程 alpha-submission）：若新 alpha 的 Sharpe 比**与其相关度高于 cutoff 的所有已提交 alpha** 的 Sharpe 高 ≥10%，仍可提交——例：已提交 X Sharpe 3.18，高度相关的 Y 需 Sharpe ≥3.5。这是**改进已有 alpha 的合法通道**（对比基准值在模拟结果的 correlation summary 表中可见）
- **相关窗口**（官方教程）：Self correlation 用 **4 年窗口**；inner correlation 用两个 alpha PnL 时间段的交集
- **相关门范围随阶段变化**（官方 5973662104599）：**用户阶段只与自己已提交的 alpha 比相关**；
  成为顾问后改用整个 BRAIN alpha 池度量相关 → 顾问阶段相关门显著更严，生成时必须更强调
  信号独特性（低相关要靠**不同数据来源/经济逻辑**，不是调参）
- **雷同提交触发风控**（官方课口径 2026-04）：频繁提交与他人完全相同的表达式（含 AI 生成趋同）会触发风控审查——原样照抄社区常见模板有风险，需有自己的改动/逻辑
- 提交前可调 `/correlations/self` 免费查相关门

## 多空平衡要求

- **提交的 alpha 必须多空平衡**（官方 13306223024151）：`Neutralization = None` 仅用于分析
  数据集；若最后层不加 `group_neutralize`/`group_normalize`，可能长空数量失衡 → 引入市场风险
- 多空失衡后果：WQChallenge 分数次优、IS/OS 合并表现次优、可能被拒
- 生成/预检时的自查点：非 INDUSTRY/SUBINDUSTRY 中性化的候选，检查表达式是否含分组中性化收尾

## 平台 API 备忘

- 会话：JWT cookie（`t=...`，实测约 4h，`token.expiry ≈ 14222s`）；401/403 = 过期需更新（`qa login` 或复制 cURL）；登录端点 `POST /authentication`（Basic Auth，API 登录无需验证码）
- 数据集枚举：`GET /data-sets?region=USA&universe=TOP3000&delay=1&instrumentType=EQUITY&limit=20`
- 字段元数据：`GET /data-fields?dataset.id={id}&region=...&delay=1&universe=TOP3000&limit=50&offset={n}`（**参数名 `dataset.id` 点号写法**）
- 用户 alpha：`GET /users/self/alphas?limit=100`
- 阶段检测：`GET /users/self`（level/geniusLevel/consultant）
- 限流头：`x-ratelimit-limit-minute`（30/分）；429 区分 `THROTTLED`
- 模拟状态值：`COMPLETE`（非 COMPLETED）；is 数据在 alpha 详情
- 每日模拟限额：`DAILY_SIMULATION_LIMIT_EXCEEDED`（美东时间重置）；约 ~800 模拟/晚；提交配额官方 unlimited
- 并发：API 3 并发；SSO：BRAIN 会话 → `/authentication/support` → Zendesk JWT → 论坛 API（机制已验证可复用）
- 其他端点：`/operators`（算子参考）、`/suggest/fields`、`/suggest/examples`（字段/示例建议）、`/data-categories`、`/tutorials`、`/competitions`（分页 limit=100）
- 外部参考 SDK：`wqb`（PyPI, rocky-d/wqb）——含 search_operators/search_datasets/search_fields/check/submit 与限流常量，可对照参考
- 已证伪：无 "FastSim"、无 delay-2、无 equal/volume weighting 开关、无官方公共 SDK（顾问专属）

## 合规红线

1. **禁止无人值守自动提交**——提交必须展示检查 + 用户显式确认
2. 禁止分享真实表达式/账号 ID/盈亏数据（playbook 必须脱敏）
3. 允许 AI 生成初步想法、批量模拟、优化流程、复盘
4. 模拟配额内运行，不做 24h 刷量

## 行为准则与风控（官方帖子 2026-09 核实）

**平台明确禁止的行为**（违规直接取消资格/封号）：
- 代打代练、出租账号、代做研究、出售因子
- **收费教学/有偿代服务**（平台全程免费；任何收费行为可举报，举报有奖励）
- 冒用他人身份信息注册/参与、替他人面试或研究
- **传播、分享、整理、出售或交换笔试和面试题目、答案、记录、题库、面经及相关材料**（零容忍）
- 黑灰产组织注册大量账户、AI 换脸等蒙混面试手段
- **高频批量请求/异常回测模式**（官方课口径 2026-04）：请求频率过高、回测产出比异常（如海量回测近乎零产出）也属于风控关注对象——API 请求须合规限速、配额内运行（与合规红线"不做 24h 刷量"一致）

**Consultant 项目定位与行为边界**（官方帖 40373406402455）：
- Consultant 是**围绕 BRAIN 平台开展研究和成果提交的兼职工作**（用平台数据/工具/回测框架做 alpha research），**不是投资课程、不是投资培训、不是投资建议服务**
- 期望的是愿意长期学习、持续研究、独立思考、对结果负责的人
- 违规后果分级：风控面试 → 账户限制 → 账户冻结 → 顾问合同中止；冒用身份/盗用信息还可能承担法律后果

**面试与风控机制**：
- 面试目的：确认本人实际参与、了解真实研究能力、识别投机取巧——平台重视"真实、独立、可持续的研究能力"
- 面试流程：邀请邮件 → 截止日前预约 → 按时参加 → 预约截止后一周内通知结果
- **两次面试机会**：预约后未参加 与 面试未通过 各算一次失败
- 未通过/未预约/未参加 → 账户可能被临时锁定；锁定后可通过再次面试申请解锁
- 账户锁定但没收到邮件：发邮件至 `mainlandchina@worldquantbrain.com`，标题"【账户解锁】- 请求面试链接"
- 面试准备：身份证件；Zoom 会议填写"预约时间 + 本人姓名"；先在等候室等待

**举报机制**：发现违规行为（传播面试材料/出售因子/代做等）可向平台举报（提供证据与账号信息），平台核查后封号。

> 学习定位：平台鼓励持续学习 alpha research、理解平台数据/算子/研究方法——本仓库学习环节见
> `document/flows/learning.md`（素材仅限官方公开材料，与上述禁令一致）。
