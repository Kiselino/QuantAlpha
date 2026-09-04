# QuantAlpha

WorldQuant BRAIN 平台 AI 辅助量化研究闭环系统。对话式 agent 驱动，自动完成：

**生成候选 alpha → 本地预检 → 平台 API 云端模拟 → 门槛筛选 → 人工确认提交 → 经验沉淀**

> 当前状态：v1.8 · 已实现（`qa login` / `qa status` / `qa run` / `qa report` / `qa submit` / `qa reset` / `qa update-knowledge` / `qa suggest`）。
> v1.8 要点：启动六项环境检查（含教程进度门）/ 学习闭环公开化（教材 `document/courses/` + 协议模板 `document/courses/bootcamp/`，个人档案本地隔离）/ 快速模式两引擎 / 官方学习指南入库。
> 权威设计见 `quantalpha-design.md`；agent 工作流见 `AGENTS.md`。

---

## 这是什么

在 [WorldQuant BRAIN](https://platform.worldquantbrain.com) 平台上做量化研究（alpha 挖掘）的 AI 辅助工具。系统通过对话式 agent 帮你：

1. 根据研究方向**生成候选 alpha 表达式**（用平台的 FASTEXPR 语言和真实字段）
2. **批量云端模拟**（调用 BRAIN API，本地零回测）
3. **门槛筛选**（Sharpe/Fitness/换手/自相关/子宇宙，对齐平台提交检查）
4. 生成**候选清单报告**（指标 + 研究逻辑解释）
5. **你逐条确认后** agent 代提交并跟踪状态
6. **经验沉淀**（脱敏 playbook + 证伪库，随仓库分享）

## 为什么用它

- 冲 **10,000 分拿顾问邀请**
- 平台官方**鼓励 AI 辅助研究**（生成初步想法、批量模拟、优化流程）
- 合规边界：**模拟全自动 + 提交人工确认**（人类保留最终判断权，符合 ToS）

---

## 快速开始（你是主人）

### 前置条件

- Python 3.10+
- 一个 WorldQuant BRAIN 账号（[注册](https://platform.worldquantbrain.com)）
- 一个 AI agent 工具（opencode / claude code / codex 等）——**生成候选由 agent 完成，项目本身不调用任何 LLM API**

### 1. 安装

```bash
git clone git@github.com:Kiselino/QuantAlpha.git
cd QuantAlpha

# 方式 A（推荐）：uv（自动管理 Python 版本）
uv sync

# 方式 B：pip
pip install -e .
```

> 首次运行 `qa run` 会自动创建 `data/`、`reports/` 等私有目录（gitignored）。

### 2. 配置会话认证

BRAIN API 使用会话 JWT 认证（`t=...` cookie，约 4 小时有效，过期后需重新登录）。两种方式任选：

**方式 A：账号密码登录（推荐）** —— 直接把账号交给 agent 或自行运行：

```bash
qa login --username your@email.com --password your_password
# 或交互式（密码不回显）：
qa login
```

- 登录成功后自动写入 `secrets/worldquant_cookies.txt`（gitignored）并验证会话
- **安全约定**：账号密码只用于本次登录请求，**不写入任何文件、不进审计、不进 git**；磁盘上只有登录后生成的 cookie
- 触发平台 Persona 人机验证时会明确提示，需人工完成后再重试

**方式 B：浏览器复制 Cookie（对账号密码敏感的使用者）** —— 无需提供账号密码：

1. 登录 [platform.worldquantbrain.com](https://platform.worldquantbrain.com)
2. 打开浏览器开发者工具（F12）→ Network 面板
3. 刷新页面，找到任意 `api.worldquantbrain.com` 请求
4. 右键该请求 → Copy → **Copy as cURL** → 把整段命令粘贴给 agent（对话里说"更新 cookie"）
5. agent 解析出 Cookie 后写入 `secrets/worldquant_cookies.txt`，随后运行 `qa status` 验证

> 会话约 4 小时，过期后（提示 401/403）用任一方式重新认证即可。长时间批量模拟建议方式 A。

### 3. 首次运行：生成本地知识库（必做）

v1.4 起字段知识**按账户权限生成、仅存本地**（gitignored 不上传）：

```bash
qa update-knowledge      # 按账户阶段抓取字段元数据 → 写入 experience/fields/（约几分钟）
```

- 非顾问账户抓取 USA 区域字段；顾问账户默认 12 区域（可用 `--regions USA,KOR` 限定）
- 生成后 `qa status` 会展示知识库状态；字段白名单（`qa run` 预检）读自本地
- `experience/` 目录已在 `.gitignore` 中，克隆/推送不会包含这些数据

### 4. 开始使用（生成由 agent 完成）

项目不调用 LLM——**候选 alpha 由你的 agent 生成**。工作流：

```bash
qa login                                              # 账号密码登录（写入会话 cookie；也可 --username/--password）
qa status                                             # 启动首查：阶段检测 + 六项环境检查（含教程进度）+ 本地知识库状态
qa update-knowledge [--regions USA,KOR] [--force]     # 首次运行必做：按账户生成本地字段知识库（24h 内已生成默认跳过，--force 强制刷新）
# agent 读 document/（公开）+ experience/（本地字段/playbook/failures）→ 生成候选 → 写入 data/candidates/YYYY-MM-DD.json
qa run [--concurrency N]                              # 读入候选 → 预检 → 模拟 → 筛选 → 报告（默认 3 并发可调；中断后重跑同一候选文件自动续查未完成的模拟；PASS 候选自动暂存待提交）
qa report --daily                                     # 查看每日达标汇总
qa report --pending                                   # 预览待提交暂存清单（含指标；提交仍逐个人工确认）
qa submit <alpha_id> [--yes]                          # 人工确认后提交（展示检查 + 回查 ACTIVE；--yes 供 agent 代提交）
qa suggest                                            # 随机建议研究方向（agent 生成候选时的主题来源之一）
qa reset [--yes]                                      # 清除积累的经验，回到初始状态（保留登录凭证与本地字段知识）
```

> 在 agent 对话中直接说"根据知识库为【研究想法】生成 10 个候选 alpha 写入 data/candidates/"，agent 会完成生成步骤（生成前会询问主题来源：随机 / 网络热门 / 你指定）。

---

## 使用者指南（公开仓库）

这个仓库是公开的：**工具 + 公开知识库（平台文档）** 随仓库分发；你的私有数据（cookie、账号密码、本地字段知识、个人经验、个人成果）已被 gitignore 隔离，其他使用者克隆后不会看到。

知识库拆分（v1.7 文档驱动重构）：

- **公开 `document/`**：分层组织——`document/flows/`（流程控制文档：startup 启动/generation 生成/submission 提交/experience 沉淀/access 权限/update-knowledge 调研/learning 学习）、`document/reference/`（知识参考：operators 算子/rules 规则/pitfalls 陷阱/fields 字段策略/community 外部经验/templates 模版库）——平台公开文档，随仓库分发。agent 按流程走到相关步骤才读对应文档（`AGENTS.md` 导航表）
- **本地 `experience/`**（gitignored）：字段元数据（`qa update-knowledge` 按账户权限生成）、playbook/failures（个人经验沉淀）——**账户专属，不上传**，因为字段可用范围随账户权限变化，且表达式/字段研究属于个人数据

使用者需要：

1. 自己的 BRAIN 账号 + 认证（见上方"配置会话认证"：账号密码登录或复制 Cookie 二选一）
2. 首次运行 `qa update-knowledge` 生成本地字段知识库
3. 自己的 AI agent 工具（生成候选用；项目本身不需要 LLM 配置）

⚠️ **合规提醒**：平台条款禁止分享真实 alpha 表达式/账号 ID/盈亏数据。仓库中的经验教训均已脱敏；请勿把你自己生成的 alpha 表达式提交到任何公开仓库。

---

## 目录结构

```
QuantAlpha/
├── AGENTS.md              # agent 工作流入口 + 流程→文档导航表（agent 打开先读这个）
├── README.md              # 本文件：安装、认证配置、快速开始
├── document/              # ✅ 公开文档（仓库核心）：quantalpha-design.md + flows/ + courses/ + reference/
├── qa/                    # Python 工具库（auth/stage/brain_client/validate/commands/...）
├── pyrightconfig.json     # LSP 配置（basedpyright）
├── experience/            # 🔒 本地账户知识库：fields/ + playbook.md + failures.md（gitignored）
├── data/                  # 🔒 私有：qa.db + audit + candidates（gitignored）
├── reports/               # 🔒 私有：个人成果（gitignored）
├── secrets/               # 🔒 私有：cookie、account_info.json（gitignored）
├── docs/                  # 🔒 skill 产物 + bootcamp 学习状态（gitignored）
```

## 文档

- `document/quantalpha-design.md` — 权威系统设计（模块/数据模型/错误处理/MVP，v1.8）
- `document/flows/` — 流程控制文档：startup（会话启动/模式询问）、generation（生成三模式）、submission（提交检查/人工确认）、experience（经验沉淀/模版总结）、access（用户 vs 顾问权限矩阵）、update-knowledge（知识库更新/平台调研）、learning（人机交互学习）
- `document/courses/` — 官方课程与学习素材：零基础学量化课程笔记（4 节新手课）+ 官方教程/作业提取 + 官方学习指南（备考 bootcamp 教材源）
- `document/courses/bootcamp/` — 学习闭环协议与模板（五步闭环/评分标准/60 考点 mastery 模板/1 周速考与 2 周新人双计划）——新使用者复制到本地 `docs/bootcamp/` 后按协议学习
- `document/reference/` — 知识参考：operators（67 算子）、rules（平台规则/门槛/计分/风控）、pitfalls（量化陷阱）、fields（字段策略）、community（外部经验库）、templates（有效模版库）
- `AGENTS.md` — agent 工作流入口（导航表 + 合规红线 + 命令清单）
- 本地字段/经验见 `experience/`（`qa update-knowledge` 生成）；bootcamp 个人学习档案（mastery/错题本/摸底卷）见本地 `docs/bootcamp/`（gitignored，协议与模板见上方公开目录）

## 免责声明

本项目是个人量化研究辅助工具，不构成投资建议。使用 BRAIN 平台须遵守其用户协议；系统设计已内置合规红线（人工确认提交、私有部署、脱敏分享）。
