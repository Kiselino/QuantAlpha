# 字段策略（公开说明）

> **字段数据本身不随仓库分发**（v1.4 起）：字段元数据按账户权限生成，存于
> gitignored 的 `experience/fields/`（`qa update-knowledge` 抓取，数据不上传）。
> 本文件只保留平台机制层面的公开策略要点。

## 字段策略要点（平台机制实证）

- **Dataset Usage Management（数据集过度使用）**：某区域某数据集类别"过度使用"→ 该类别字段**临时禁用**（模拟+提交）+ "Overused" 警告，需向平台申请恢复 → **字段策略必须分散多数据集，不能死磕单一类别**（官方目的 22696572406551：鼓励跨类别分散研究，探索过度使用类别之外的洞察）
- **Vector 字段**（nws/scl 等 VECTOR 类型）：不能直接用于标量表达式，需 `vec_*` 算子转换；原始 turnover 高，须 `ts_rank`/`ts_decay` 降频
- 生成候选时优先基本面数据集（通过率最高），避免使用 `userCount` 过高的饱和字段
- **覆盖率两种口径区分**（官方课 2026-04）：`universe coverage`（字段覆盖宇宙内多少股票）vs `data coverage`（数据时间覆盖）；平台上显示的 coverage 多为**均值**——只有一两天有值的字段平均下来会显得很低，long count 少 ≠ 数据质量差（用窗口拉长/定量探测确认，见 bootcamp 教材定量探测法）

## 数据集分布（官方 API 核对，2026-09-01）

`GET /data-sets` 全量 **204 个数据集（区域 USA）**，类别分布：

| 类别 | 数量 | 说明 |
|---|---|---|
| Price Volume | 36 | 价格/成交量（技术信号载体） |
| Fundamental | 30 | 基本面（价值/质量/成长，通过率最高） |
| Model | 30 | 模型输出 |
| Option | 30 | 期权（IV 情绪信号） |
| News | 24 | 新闻 |
| Social Media | 24 | 社交媒体 |
| Analyst | 12 | 分析师预期 |
| Earnings | 12 | 盈利 |
| Sentiment | 6 | 情绪 |

> 账户可见范围远小于全量：本地 `experience/fields/meta.json` 记录（如 21 数据集 / 8642 字段）。
> 顾问阶段 12 区域的数据集范围按账户抓取自动扩大（`qa update-knowledge --force` 刷新）。
> 数据集 API 分页注意：`limit` 上限约 20（>20 返回 400 "pagination limit too high"）。

## 本地字段知识（账户专属，不上传）

| 文件 | 内容 | 用途 |
|---|---|---|
| `experience/fields/fields.json` | 账户可用区域全量字段 `{id, description, dataset, type, coverage, userCount}` | `qa run` 字段白名单（validate 防幻觉字段） |
| `experience/fields/top_fields.json` | 每数据集 userCount top 15 | agent 生成候选时选字段参考 |
| `experience/fields/meta.json` | 生成时间/阶段/区域/数量 | `qa status` 展示 |

生成方式：`qa update-knowledge`（首次运行必做；按账户阶段抓取：用户=USA，
顾问=12 区域；可用 `--regions USA,KOR` 限定）。抓取走 BRAIN API 元数据端点
（`/data-sets` + `/data-fields`，限流节流约 2 秒/请求）。
