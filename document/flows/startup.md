# 会话启动（startup）

> 读取时机：**每次会话第一步**。本文件定义启动流程的完整细节。
> 导航入口：`AGENTS.md` → 流程 → 文档导航表。

## 1. 启动六项检查（`qa status`）

| # | 检查项 | 正常 | 异常引导动作 |
|---|---|---|---|
| 1 | 新用户判定 | 非新用户 | 首次运行引导：login → update-knowledge → 教程学习 → run |
| 2 | 知识库就绪（`experience/fields/`） | fields 已生成 | 缺失 → 提示"首次运行需先 `qa update-knowledge` 生成账户专属字段知识库" |
| 3 | cookie 有效 | 有效 | 不存在/过期 → `qa login` 或提供 Copy as cURL；网络异常 → 提示网络不可达 |
| 4 | 账号阶段（level/资格/区域/语言） | 输出阶段配置 | 知识库与资格不一致 → 建议 `qa update-knowledge --force` |
| 5 | 待提交暂存（`secrets/pending_submits.json`） | 无 | 有 PASS 暂存 → **先报告等确认提交，不叠加新循环** |
| 6 | **教程进度**（本地 `docs/bootcamp/mastery.json` 掌握度） | 已通过（达标率 ≥80% 或用户明确声明跳过） | 未建/未达标 → 进入生成环节前先完成当日 bootcamp 学习段（教材 `document/courses/`，闭环协议 `document/courses/bootcamp/protocol.md`——个人执行副本与档案在本地 gitignored `docs/bootcamp/`） |

> 检查 6 说明：mastery.json 为本地个人学习档案（gitignored）。达标判定 = 达标+熟练考点数 / 总数 ≥ 80%；用户声明"不考顾问/跳过学习"可视为通过（对话层确认即可）。`qa status` 代码不检查该项——由 agent 按本表执行。

启动后获得动态配置：并发数、可用区域、字段范围、表达式语言（详细决策见 `document/flows/access.md`）。

## 2. cookie 无效时的处理

- `qa login --username ... --password ...`（账号密码方式，凭据不落盘）
- 或让用户提供 Copy as cURL（敏感用户可选用）

## 3. 调研访问规则

BRAIN 平台匿名访问是登录墙（返回 JS 空壳页面）。agent 做官网/API 调研（算子文档、字段、模拟示例等）前，**先确认 cookie 有效**（`qa status` 验证 / 失效则 `qa login` 刷新）。
**区分两类访问**：API 场景 `qa login`（账号密码）即可；**网页/论坛场景（help center/社区）需用户浏览器 Copy as cURL 提供完整会话凭据**——只有账号密码时不要死磕网页墙，直接请用户 Copy as cURL 或改用 API 源。遇到官网墙异常时优先怀疑 cookie 过期（API 场景）。完整规则见 `document/flows/update-knowledge.md` §2。

## 4. 教程状态对流程的影响（检查 6 的后续动作）

**教程未通过时**（新用户或学习未达标）：

1. **进入生成环节前**先完成当日学习段（bootcamp 闭环：诊断 → 精学 → 自测 → 反馈 → 档案更新），每日 1-2 个学习段不叠加生成任务
2. 用户选择生成模式后：
   - **教学模式** = 学习闭环与生成自然融合（讲解当下思路 + 补知识），可跳过单独学习段
   - **随机/快速模式** = 批次之间插入当日学习段（先学后跑或跑后学，以用户节奏为准）
3. 生成候选时可参考 `document/courses/` 教材中的官方示例与作业题作为灵感（合规：官方公开材料）
4. 教程通过后恢复正常流程（学习段不再自动插入，用户主动深问转 `document/flows/learning.md`）

## 5. 询问运行模式（每次会话启动问一次，三选一）

| 模式 | 定位 | 适用场景 | 详情 |
|---|---|---|---|
| ① 教学模式 | 人机交互学习核心 | 想边做边学，理解每一步为什么 | `document/flows/generation.md` §1.1 |
| ② 随机模式 | 快速探索 + 顺带教学 | 想看看随机方向能出什么，顺便学点 | `document/flows/generation.md` §1.2 |
| ③ 快速模式 | 高价值复用 | 有正事，让 agent 后台跑（历史主题深挖/模版生成） | `document/flows/generation.md` §1.3 |

用户也可在会话中随时口头切换模式。

## 6. 主题来源三选一（教学模式/随机模式进入生成前询问）

1. **随机抽取**：agent 跑 `qa suggest` 或自行随机
2. **网络热门**：agent 用 web 搜索 BRAIN 社区/论坛/教程的热门研究方向（调研规则见 update-knowledge.md）
3. **用户指定**：用户直接给方向/点子

用户选择后再进入生成（不擅自替用户选主题）。快速模式不需要询问主题来源（主题来自历史数据）。
