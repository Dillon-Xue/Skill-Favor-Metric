---
name: Skill Favor Metric
description: |
  跟踪你在 SkillHub 上发布的 skill 的下载量 / 安装数 / 星标，自动本地存储每日快照，生成趋势折线图与每 skill 明细，并支持每日自动采集。当用户说"我的 skill 下载量""skillhub 数据统计""查看我发布的 skill 表现""skill 下载趋势""给 skillhub 数据做个图表""设置每日自动统计 skillhub""skill 数据看板"等时使用。
version: 0.1.0
allowed-tools:
  - Read
  - Glob
  - Bash
  - AskUserQuestion
  - automation_update
  - present_files
license: Internal
disable: false
---

# Skill Favor Metric — SkillHub 发布数据跟踪

帮你把 SkillHub 后台「我发布的 skill」列表里的下载量 / 安装数 / 星标拉到本地，按天存快照、画趋势图、列明细，并支持每日自动采集与重新授权。

## 项目目录

```
Skill-Favor-Metric/
├── SKILL.md              # 本文件（WorkBuddy skill 定义）
├── README.md             # 完整使用文档（含 CLI + 对话双模式示例）
├── .gitignore
├── scripts/
│   ├── common.py         # 公共工具：数据目录路径、凭证读写、HTTP 请求、鉴权头构建
│   ├── auth.py           # 授权管理：PAT 导入 / Cookie 导入 / 凭证校验
│   ├── fetch.py          # 数据采集：翻页拉取 → 汇总 → 写本地快照
│   └── report.py         # 报告生成：读取快照 → 渲染离线 HTML 看板（含 echarts）
├── vendor/
│   └── echarts.min.js    # ECharts 5 离线副本
└── references/           # 参考资料（预留）
```

**数据与凭证不在本目录内**，统一放在 `~/.workbuddy/skillhub-stats/`：

| 内容 | 路径 | 说明 |
|------|------|------|
| 数据快照 | `~/.workbuddy/skillhub-stats/snapshots.json` | 按日期 key 存储的 JSON |
| 凭证 | `~/.workbuddy/skillhub-stats/credentials.json` | PAT 或 Cookie，权限 600，绝不进 git |

## 数据从哪来

通过 SkillHub 后台接口 `https://api.skillhub.cn/api/v1/dashboard/skills` 获取（与你 F12 看到的完全一致）。鉴权使用**官方 API Token（PAT，`skh_xxx` 格式）**，以 `Authorization: Bearer <PAT>` 发送——这是 SkillHub 给程序用的「机器人凭证」，比抠浏览器 Cookie 更稳、更长久、无浏览器封号风险。（浏览器 Cookie 鉴权作为兜底仍支持。）

## 工作流

> 每个步骤都给出 **CLI 命令**和 **WorkBuddy 对话**两种方式。作为 AI 执行本 skill 时，优先用对话方式引导用户；用户也可以自己在终端操作。

### 第 0 步：检查授权

**CLI：**
```bash
python <skill_dir>/scripts/auth.py --check
```
- 返回 `OK` → 进入第 1 步。
- 返回 `MISSING` 或 `EXPIRED` → 进入「授权流程」。

**对话中：**
用户说"检查授权状态"或"我的 token 还有效吗"，执行上述命令并告知结果。若失效则引导走授权流程。

### 授权流程（官方 API Token，无需驱动浏览器）

**前置操作（两种方式相同）：**

1. 请用户去 SkillHub 网页端 **个人中心 → API keys**（`https://skillhub.cn/dashboard/keys`）创建一把 **API Token**（`skh_xxx` 格式），一次性复制保存。

**CLI 写入凭证：**
```bash
python <skill_dir>/scripts/auth.py --import-pat <skh_xxx>
# 或（推荐）：echo "<skh_xxx>" | python <skill_dir>/scripts/auth.py --import-pat-stdin
```
然后校验：`python <skill_dir>/scripts/auth.py --check` 应返回 `OK (PAT)`。

**对话中写入凭证：**
用户把 `skh_xxx` 那串发给你后，用 `--import-pat-stdin` 方式安全写入（避免 token 出现在命令行参数里），然后自动跑 `--check` 确认结果并告知用户。

> 兜底方案（仅在 PAT 不可用时的极少数情况）：用户按 F12 复制任意 `api.skillhub.cn` 请求的 **Cookie 请求头整段文本**，CLI 用 `auth.py --import-cookie-file <文件>` 写入；对话中让用户把 Cookie 文本发给你即可。
>
> 安全提醒：凭证只存本机 `~/.workbuddy/skillhub-stats/credentials.json`（权限 600 / Windows 仅当前用户可读写），不写进 skill 目录、不提交 git、不要在对话中回显完整 token。

### 第 1 步：采集今日快照

**CLI：**
```bash
python <skill_dir>/scripts/fetch.py
```
脚本会：
- 自动**翻页**拉全量 skill（接口 `total` 可能大于单页）；
- 汇总当日全部 skill 的 `downloads / installs / stars` 总量；
- 以「今天日期 `YYYY-MM-DD`」为 key 写入快照；**同一天多次采集只保留最后一次**；
- 输出 JSON 摘要（日期、总量、skill 数、诊断信息）。

失败处理（退出码非 0，错误信息同时打到 stderr）：
- `AUTH_EXPIRED`：凭证缺失或失效 → 提示用户重新走「授权流程」生成新 PAT，然后重跑一次采集。
- `FETCH_ERROR`：网络/超时 → 提示稍后重试。
- `PARSE_ERROR`：返回结构异常 → 提示接口可能变更。

**对话中：**
用户说"采集数据"、"看看下载量"、"查 skillhub 数据"等触发词时，执行 fetch.py；成功后直接进入第 2 步生成报告并 present_files 预览，一步到位。

> 若本步由自动化任务触发且失败，上述错误信息会直接回显给用户，明确告知「今日自动采集失败，请重新授权」。

### 第 2 步：生成图表与明细

**CLI：**
```bash
python <skill_dir>/scripts/report.py
# 或指定输出：python <skill_dir>/scripts/report.py --output ./my-report.html
```
生成自包含 HTML 看板（离线可用，内置 echarts）：
- **趋势折线图**：x 轴为日期，三条线 = 每日全部已发布 skill 的 `downloads / installs / stars` 各自**求和**；每个数据点默认显示数值标签；
- **每 skill 明细表**：取**最新一次快照**中每个 skill 的当前数据（名称、slug、分类、三项指标、版本、更新时间）。

**对话中（必须执行）：**
1. 执行 `report.py` 生成 HTML。
2. **必须**调用 `present_files` 将生成的 HTML 绝对路径回显给用户（自动打开预览面板）。这是本步骤的**强制性输出**，不可省略。
3. 在文字回复中一并给出 HTML 的绝对路径（如 `C:\Users\dillon\.workbuddy\skillhub-stats\report.html`），方便用户后续自行打开或转发。

### 第 3 步（可选）：开启每日自动采集

若用户要「每天自动获取」，调用 `automation_update` 创建每日任务：

**完整示例（AI 直接调用）：**
```
automation_update(mode="create",
  name="Skill Favor Metric 每日采集",
  prompt="运行 Skill Favor Metric 每日采集：执行 ~/.workbuddy/skills/Skill-Favor-Metric/scripts/fetch.py；若失败（如 token 过期）直接输出提示告知用户需要重新授权。",
  scheduleType="recurring",
  rrule="FREQ=DAILY;INTERVAL=1",
  cwds=["~/.workbuddy/skills/Skill-Favor-Metric"],
  status="ACTIVE")
```

**指定具体时间（如每天早上 9 点）：**
增加 `validFrom` 参数或在 prompt 中说明时间即可。

**对话中引导：**
用户说"每天自动采集"、"设个定时任务"等 → 用上述配置创建任务，并把创建结果告知用户。

- 用户未设置时，只在手动触发当天记录一条快照（符合需求）。
- 若用户设置「每天多次」，脚本按日期 key 合并，仍只保留当天最后一次。

## 已知限制

- 官方 API Token（PAT）无过期时间，仅可手动在 `dashboard/keys` 撤销；撤销后自动采集会失败并提示重新授权（非 bug，是预期的重授权机制）。
- 接口为后台内部接口，字段可能变更；`PARSE_ERROR` 即信号。
