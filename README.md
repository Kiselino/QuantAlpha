# QuantAlpha

WorldQuant BRAIN 平台 AI 辅助量化研究闭环系统。对话式 agent 驱动，自动完成：

**生成候选 alpha → 本地预检 → 平台 API 云端模拟 → 门槛筛选 → 人工确认提交 → 经验沉淀**

> 当前状态：设计定稿（v1.1），等待实现 1.0 可跑通版本。
> 权威设计见 `design/quantalpha-design.md`；agent 工作流见 `AGENTS.md`。

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
git clone <repo-url>
cd QuantAlpha
pip install -e .          # 或 uv sync
```

### 2. 配置会话 Cookie

BRAIN API 使用浏览器会话 cookie 认证（JWT，约 4-8 小时有效）：

1. 登录 [platform.worldquantbrain.com](https://platform.worldquantbrain.com)
2. 打开浏览器开发者工具（F12）→ Network 面板
3. 刷新页面，找到任意 `api.worldquantbrain.com` 请求
4. 复制请求头的 `Cookie:` 完整值 → 存入 `secrets/worldquant_cookies.txt`
5. 运行 `qa status` 验证（应显示账号阶段 + 配额状态）

> cookie 过期后（提示 401/403）重复上述步骤即可。

### 3. 开始使用（生成由 agent 完成）

项目不调用 LLM——**候选 alpha 由你的 agent 生成**。工作流：

```bash
qa status                                             # 启动首查：阶段检测 + 配额
# agent 读 knowledge/ 知识库 → 生成候选 → 写入 data/candidates/YYYY-MM-DD.json
qa run                                                # 读入候选 → 预检 → 模拟 → 筛选 → 报告
qa report --daily                                     # 查看每日达标汇总
qa submit <alpha_id>                                  # 确认后提交（第二批；agent 先展示检查结果）
```

> 在 agent 对话中直接说"根据 knowledge/ 里的算子字段知识，为【研究想法】生成 10 个候选 alpha 写入 data/candidates/"，agent 会完成生成步骤。

---

## 朋友使用指南（仓库分享）

这个仓库可以分享给朋友：**工具 + 静态知识库 + 脱敏经验** 随仓库分发；你的私有数据（cookie、原始经验、个人成果）已被 gitignore 隔离，朋友克隆后不会看到。

朋友需要：

1. 自己的 BRAIN 账号 + 自己的会话 cookie（见上方"配置会话 Cookie"）
2. 自己的 AI agent 工具（生成候选用；项目本身不需要 LLM 配置）
3. 可选：为自己的账号运行 `qa update-knowledge` 抓取可用字段

⚠️ **合规提醒**：平台条款禁止分享真实 alpha 表达式/账号 ID/盈亏数据。仓库中的经验教训均已脱敏；请勿把你自己生成的 alpha 表达式提交到任何公开仓库。

---

## 目录结构

```
QuantAlpha/
├── AGENTS.md              # agent 工作流入口（agent 打开先读这个）
├── design/                # 设计文档 + 变更清单
├── qa/                    # Python 工具库
├── knowledge/             # 静态知识库（算子/字段/规则/playbook/证伪库）
├── docs/                  # 教程、FAQ
├── data/                  # 🔒 私有：qa.db + audit（gitignored）
├── experience/            # 🔒 私有：原始经验（gitignored）
├── reports/               # 🔒 私有：个人成果（gitignored）
└── .omo/                  # 🔒 私有：secrets/（gitignored）
```

## 文档

- `design/quantalpha-design.md` — 系统设计（模块/数据模型/错误处理/MVP）
- `AGENTS.md` — agent 工作流入口与关键知识速查
- `knowledge/` — 平台规则、算子参考、字段索引、经验 playbook

## 免责声明

本项目是个人量化研究辅助工具，不构成投资建议。使用 BRAIN 平台须遵守其用户协议；系统设计已内置合规红线（人工确认提交、私有部署、脱敏分享）。
