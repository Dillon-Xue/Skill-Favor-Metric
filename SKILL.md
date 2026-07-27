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
license: Internal
disable: false
---

# Skill Favor Metric — SkillHub 发布数据跟踪

帮你把 SkillHub 后台「我发布的 skill」列表里的下载量 / 安装数 / 星标拉到本地，按天存快照、画趋势图、列明细，并支持每日自动采集与重新授权。

## 数据从哪来
通过 SkillHub 后台接口 `https://api.skillhub.cn/api/v1/dashboard/skills` 获取（与你 F12 看到的完全一致）。鉴权使用**官方 API Token（PAT，`skh_xxx` 格式）**，以 `Authorization: Bearer <PAT>` 发送——这是 SkillHub 给程序用的「机器人凭证」，比抠浏览器 Cookie 更稳、更长久、无浏览器封号风险。（浏览器 Cookie 鉴权作为兜底仍支持。）

## 存储位置（刻意放在 skill 目录之外，避免更新/重装被清）
- 数据快照：`~/.workbuddy/skillhub-stats/snapshots.json`
- 凭证：`~/.workbuddy/skillhub-stats/credentials.json`（仅本机，权限 600，绝不进 git）

## 工作流

### 第 0 步：检查授权
运行：
```
python <skill_dir>/scripts/auth.py --check
```
- 返回 `OK` → 进入第 1 步。
- 返回 `MISSING` 或 `EXPIRED` → 进入「授权流程」。

### 授权流程（官方 API Token，无需驱动浏览器）
1. 请用户去 SkillHub 网页端 **个人中心 → API keys**（`https://skillhub.cn/dashboard/keys`）创建一把 **API Token**（`skh_xxx` 格式），一次性复制保存。
2. 用户把 `skh_xxx` 那串发给你后，写入凭证文件：
```
python <skill_dir>/scripts/auth.py --import-pat <skh_xxx>
```
（也可用 `--import-pat-stdin` 从标准输入读，避免 token 出现在命令行参数里。）
3. 再次 `--check` 确认 `OK (PAT)`。

> 兜底方案（仅在 PAT 不可用时的极少数情况）：用户按 F12 复制任意 `api.skillhub.cn` 请求的 **Cookie 请求头整段文本**，用 `auth.py --import-cookie-file <文件>` 写入。

> 安全：凭证只存本机 `~/.workbuddy/skillhub-stats/credentials.json`（权限 600 / Windows 仅当前用户可读写），不写进 skill 目录、不提交 git。token 不要贴进对话或仓库（本会话已按此处理）。

### 第 1 步：采集今日快照
```
python <skill_dir>/scripts/fetch.py
```
脚本会：
- 自动**翻页**拉全量 skill（接口 `total` 可能大于单页）；
- 汇总当日全部 skill 的 `downloads / installs / stars` 总量；
- 以「今天日期 `YYYY-MM-DD`」为 key 写入快照；**同一天多次采集只保留最后一次**；
- 输出 JSON 摘要（日期、总量、skill 数、快照路径）。

失败处理（退出码非 0，错误信息同时打到 stderr）：
- `AUTH_EXPIRED`：凭证缺失或失效 → 提示用户重新走「授权流程」生成新 PAT，然后重跑一次采集。
- `FETCH_ERROR`：网络/超时 → 提示稍后重试。
- `PARSE_ERROR`：返回结构异常 → 提示接口可能变更。

> 若本步由自动化任务触发且失败，上述错误信息会直接回显给用户，明确告知「今日自动采集失败，请重新授权」。

### 第 2 步：生成图表与明细
```
python <skill_dir>/scripts/report.py
```
生成自包含 HTML 看板（离线可用，内置 echarts）：
- **趋势折线图**：x 轴为日期，三条线 = 每日全部已发布 skill 的 `downloads / installs / stars` 各自**求和**；
- **每 skill 明细表**：取**最新一次快照**中每个 skill 的当前数据（名称、slug、分类、三项指标、版本、审核状态、安全扫描结果）。

把生成的 HTML 路径回显给用户（可用 present_files 打开预览）。

### 第 3 步（可选）：开启每日自动采集
若用户要「每天自动获取」，用 `automation_update` 工具创建每日任务：
```
automation_update(mode="create",
  name="Skill Favor Metric 每日采集",
  prompt="运行 Skill Favor Metric 的每日采集（静默模式）：执行 <skill_dir>/scripts/fetch.py；若失败（如 token 过期）直接输出提示告知用户需要重新授权。",
  scheduleType="recurring",
  rrule="FREQ=DAILY;INTERVAL=1")
```
- 用户未设置时，只在手动触发当天记录一条快照（符合需求）。
- 若用户设置「每天多次」，脚本按日期 key 合并，仍只保留当天最后一次。

## 已知限制
- `installs` / `stars` 当前多为 0，对应折线初期会是平地，有数据后自动显示。
- 官方 API Token（PAT）无过期时间，仅可手动在 `dashboard/keys` 撤销；撤销后自动采集会失败并提示重新授权（非 bug，是预期的重授权机制）。
- 接口为后台内部接口，字段可能变更；`PARSE_ERROR` 即信号。
