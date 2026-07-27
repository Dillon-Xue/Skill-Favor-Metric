# Skill Favor Metric

跟踪你在 [SkillHub](https://skillhub.cn) 上发布的 skill 的**下载量 / 安装数 / 星标**，自动本地存储每日快照，生成趋势折线图与每 skill 明细，并支持每日自动采集与到期重新授权。

> 名字来源于「favor = 好感 / 青睐」，这里指代 skill 的受欢迎程度指标。

## 功能

- **拉取**：通过 SkillHub 后台接口 `https://api.skillhub.cn/api/v1/dashboard/skills` 自动翻页拉全量已发布 skill。
- **汇总**：每日汇总全部 skill 的 `downloads / installs / stars` 总量。
- **本地存储**：按日期 `YYYY-MM-DD` 为 key 存快照；**同一天多次采集只保留最后一次**。
- **图表**：自包含 HTML 看板（内置 echarts，离线可用）：
  - 趋势折线图：x 轴为日期，三条线 = 每日全部 skill 的下载量 / 安装数 / 星标各自求和；每个数据点默认显示数值；
  - 每 skill 明细表：最新一次快照中每个 skill 的当前数据（名称、slug、分类、三项指标、版本、更新时间）。
- **自动采集**：支持用 WorkBuddy 自动化做每日定时采集；未设置则只在手动触发当天记录。
- **到期重授权**：官方 API Token（PAT）无过期时间，仅可手动撤销；撤销后采集失败并明确提示重新授权。

## 项目目录

```
Skill-Favor-Metric/
├── SKILL.md              # WorkBuddy skill 定义（触发词 + 工作流）
├── README.md             # 本文件
├── .gitignore
├── scripts/
│   ├── common.py         # 公共工具：数据目录路径、凭证读写、HTTP 请求、鉴权头构建
│   ├── auth.py           # 授权管理：PAT 导入 / Cookie 导入 / 凭证校验
│   ├── fetch.py          # 数据采集：翻页拉取 → 汇总 → 写本地快照
│   └── report.py         # 报告生成：读取快照 → 渲染离线 HTML 看板
├── vendor/
│   └── echarts.min.js    # ECharts 5 离线副本（报告内嵌引用）
└── references/           # 参考资料（预留）
```

> **数据与凭证不在本目录内**，统一放在 `~/.workbuddy/skillhub-stats/`，避免更新/重装被清空。

## 使用方式

本项目支持两种使用方式：

| | **命令行 (CLI)** | **WorkBuddy 对话** |
|---|---|---|
| 触发 | 终端直接运行 Python 脚本 | 在对话中说触发词（如"我的 skill 下载量"），AI 按 SKILL.md 工作流执行 |
| 适用场景 | 开发调试 / CI / 手动定时任务 | 日常使用 / 一键查看 / 设置自动化 |
| 输出 | 终端 JSON + 数据目录下 HTML 文件 | 对话中直接打开预览看板 |

下面每个步骤都给出两种方式的操作示例。

---

## 第 0 步：检查授权

### CLI 方式

```bash
python <skill_dir>/scripts/auth.py --check
```

- 返回 `OK` → 进入第 1 步。
- 返回 `MISSING` 或 `EXPIRED` → 进入「首次授权」。

### WorkBuddy 对话方式

直接说：

> "帮我查一下 Skill Favor Metric 的授权状态"

AI 会执行 `auth.py --check` 并把结果告诉你。如果凭证缺失或失效，会引导你走授权流程。

---

## 首次授权（必须）

鉴权使用 **SkillHub 官方 API Token（PAT，`skh_xxx` 格式）**，以 `Authorization: Bearer <PAT>` 发送——这是平台给程序用的「机器人凭证」，不硬编码任何身份，由使用者自己在网页端生成。

**前置操作（两种方式相同）：**

1. 前往 SkillHub 网页端 **个人中心 → API keys**（`https://skillhub.cn/dashboard/keys`）创建一把 API Token（`skh_xxx` 格式），一次性复制保存。

### CLI 方式写入凭证

```bash
# 方式 A：命令行参数（token 会出现在终端历史）
python <skill_dir>/scripts/auth.py --import-pat skh_你的token

# 方式 B：标准输入（推荐，token 不留痕迹）
echo "skh_你的token" | python <skill_dir>/scripts/auth.py --import-pat-stdin
```

校验：

```bash
python <skill_dir>/scripts/auth.py --check   # 应返回 OK (PAT)
```

### WorkBuddy 对话方式

直接把 token 发给 AI：

> "这是我的 SkillHub API Token：`skh_你的token`，帮我导入到 Skill Favor Metric"

AI 会用 `--import-pat-stdin` 方式安全写入（不留命令行历史），然后自动跑 `--check` 确认结果。

> 兜底方案（仅在 PAT 不可用时的极少数情况）：按 F12 复制任意 `api.skillhub.cn` 请求的 Cookie 请求头整段文本，CLI 用 `auth.py --import-cookie-file <文件>` 写入；WorkBuddy 对话中把 Cookie 文本发给 AI 即可。（浏览器 Cookie 鉴权仍被支持。）

---

## 第 1 步：采集今日快照

### CLI 方式

```bash
python <skill_dir>/scripts/fetch.py
```

输出 JSON 摘要（日期、总量、skill 数、诊断信息）。失败时退出码非 0 且 stderr 含错误码：

- `AUTH_EXPIRED` → 凭证失效，重新授权后重跑
- `FETCH_ERROR` → 网络/超时，稍后重试
- `PARSE_ERROR` → 接口结构可能变更

### WorkBuddy 对话方式

说：

> "采集一下今天的 SkillHub 数据"

或更自然地：

> "看看我发布的 skill 今天下载量多少了"

AI 会依次执行 fetch → report → present_files 打开预览，一步到位看到结果。

---

## 第 2 步：生成图表与明细

### CLI 方式

```bash
# 默认输出到数据目录下的 report.html
python <skill_dir>/scripts/report.py

# 或指定输出路径
python <skill_dir>/scripts/report.py --output ./my-report.html
```

生成的 HTML 是自包含的（内置 echarts），可直接用浏览器打开，无需网络。

### WorkBuddy 对话方式

说：

> "生成 Skill Favor Metric 的看板"

AI 执行 report.py 后用 present_files 直接在对话中打开预览，你点开就能看到折线图和明细表。

---

## 开启每日自动采集（可选）

### CLI 方式（crontab / 任务计划程序）

在你的系统定时任务中加入：

```bash
# Linux crontab（每天早上 9 点）
0 9 * * * cd <skill_dir> && python3 scripts/fetch.py >> /var/log/sfm.log 2>&1

# Windows 任务计划程序（每天 9 点）
schtasks /create /tn "SFM-Daily" /tr "python <skill_dir>\scripts\fetch.py" /sc daily /st 09:00
```

### WorkBuddy 方式（推荐）

在 WorkBuddy 对话中说：

> "帮我把 Skill Favor Metric 设成每天自动采集"

AI 会调用 `automation_update` 创建如下每日任务：

```json
{
  "name": "Skill Favor Metric 每日采集",
  "scheduleType": "recurring",
  "rrule": "FREQ=DAILY;INTERVAL=1",
  "prompt": "运行 Skill Favor Metric 每日采集：执行 ~/.workbuddy/skills/Skill-Favor-Metric/scripts/fetch.py；若失败（如 token 过期）直接告知用户需要重新授权。",
  "cwds": ["~/.workbuddy/skills/Skill-Favor-Metric"],
  "status": "ACTIVE"
}
```

也可以指定具体时间（比如每天早上 9 点）：

> "每天早上 9 点自动采集 SkillHub 数据"

对应配置增加 `validFrom` / 定时参数即可。

- 未设置自动化时，只在手动触发当天记录一条快照。
- 若设置「每天多次」，脚本按日期 key 合并，仍只保留当天最后一次。

---

## 数据存储位置（刻意放在 skill 目录之外）

| 内容 | 路径 | 说明 |
|------|------|------|
| 数据快照 | `~/.workbuddy/skillhub-stats/snapshots.json` | 按日期 key 存储的 JSON，含每日 totals + skills 列表 |
| 凭证 | `~/.workbuddy/skillhub-stats/credentials.json` | PAT 或 Cookie，权限 600 / Windows 下 icacls 限制为当前用户，**绝不进 git** |

---

## 已知限制

- 官方 API Token（PAT）无过期时间，仅可手动在 `dashboard/keys` 撤销；撤销后自动采集会失败并提示重新授权（这是预期的重授权机制，不是 bug）。
- 后台接口为内部接口，字段可能变更；`FETCH_ERROR` / `PARSE_ERROR` 即信号。
