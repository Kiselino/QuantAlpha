# 知识库更新与平台调研（update-knowledge）

> 读取时机：**更新知识或调研前**。本文件定义知识库更新时机、调研访问规则、
> 外部经验通道与**网络模版收集**（v1.7 新增）。

## 1. 知识库更新时机

| 场景 | 动作 |
|---|---|
| 首次运行 | **必做**：`qa update-knowledge` 生成账户专属字段知识库（`experience/fields/`） |
| 24h 内重复 | 默认跳过（顾问 12 区域重抓很贵），`--force` 强制刷新 |
| 顾问资格变化 | `qa update-knowledge --force`（字段范围/区域随资格扩大） |
| 知识库与资格不一致 | `qa status` 提示 → `--force` 刷新 |

命令：`qa update-knowledge [--regions ...] [--force]`——按账户抓取字段知识
→ 写本地 `experience/fields/`（gitignored 不上传）。

## 2. 平台调研访问规则（实测教训）

1. **先确认 cookie 有效**：`qa status` 验证；失效则 `qa login` 刷新
2. BRAIN 平台匿名访问是登录墙（返回 JS 空壳页面）——**必须携带 cookie**
   （`secrets/worldquant_cookies.txt`，`t=<JWT>`）访问
3. 遇到官网墙返回异常时**优先怀疑 cookie 过期**——更新登录状态后重试，
   不要盲目换信息来源
4. 优质官方参考源：
   - `GET /operators`（API，带 cookie）——官方算子清单；`/operators/{name}` 详情页
     含官方 SIMULATION_EXAMPLE（完整 settings 含 language）
   - `GET /data-sets`（API，带 cookie）——官方数据集清单（区域/字段数/delay/universe）
   - support 站点（support.worldquantbrain.com）：**curl 直连被 Cloudflare 挡**，
     走 Zendesk API（`/api/v2/community/posts/{id}.json`）需浏览器会话 cookie
     （`_help_center_session`/`_zendesk_session`/`_zendesk_shared_session`）；
     可让用户浏览器 Copy as cURL 提供完整凭据
5. **合规边界**：调研仅限官方公开材料 + 方法论；**严禁收集/整理/传播面试真题、答案、题库、面经**

## 3. 外部经验通道（community.md 写入流程）

`qa update-knowledge` 运行时，agent 询问用户"是否同时更新外部经验？"→ 用户同意后：

1. 网络调研（官方论坛 / BRAIN 社区 / 教程；先确认 cookie 有效，见 §2）
2. 总结为新条目：方向 + 结论 + 来源 URL + 日期 + 可信度（格式见
   `document/reference/community.md`）
3. **展示给用户确认** → 追加写入 `document/reference/community.md`
4. **禁止掺入个人私有表达式 / 账号信息**（分享红线）

> 机械抓取（字段）与判断性内容（外部经验）分离：CLI 命令本身不弹交互，
> 询问由 agent 在会话中执行。

## 4. 网络模版收集（v1.7 新增）

调研 BRAIN 社区/教程时，**顺手收集方法论级模版**：

1. 来源：官方文档 / 社区帖子 / 教程（可信度分级：官方 > 高赞社区 > 普通帖）
2. 提取内容：结构模式（算子组合骨架 + 适用场景 + 参数经验），**过滤真实表达式**
3. 标注来源：`网络-<URL>`，写入 `document/reference/templates.md`（格式见该文档）
4. 入库前展示给用户确认（与外部经验同纪律）
5. **禁止收集面试内容**（与 §2 合规边界一致）

## 5. 调研 → 文档更新映射

| 调研对象 | 更新文档 |
|---|---|
| 算子清单/语法 | `document/reference/operators.md` |
| 门槛/计分/提交测试/模拟设置 | `document/reference/rules.md` |
| 字段/数据集/区域 | `document/reference/fields.md` + `document/flows/access.md` |
| 顾问路径/权限/风控 | `document/flows/access.md` + `document/reference/rules.md` |
| 方法论模版/社区经验 | `document/reference/templates.md` + `document/reference/community.md` |
