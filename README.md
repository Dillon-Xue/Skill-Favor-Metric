# Skill Favor Metric

跟踪你在 [SkillHub](https://skillhub.cn) 上发布的 skill 的**下载量 / 安装数 / 星标**，自动本地存储每日快照，生成趋势折线图与每 skill 明细，并支持每日自动采集与到期重新授权。

> 名字来源于「favor = 好感 / 青睐」，这里指代 skill 的受欢迎程度指标。

## 功能

- **拉取**：通过 SkillHub 后台接口 `https://api.skillhub.cn/api/v1/dashboard/skills` 自动翻页拉全量已发布 skill。
- **汇总**：每日汇总全部 skill 的 `downloads / installs / stars` 总量。
- **本地存储**：按日期 `YYYY-MM-DD` 为 key 存快照；**同一天多次采集只保留最后一次**。
- **图表**：自包含 HTML 看板（内置 echarts，离线可用）：
  - 趋势折线图：x 轴为日期，三条线 = 每日全部 skill 的下载量 / 安装数 / 星标各自求和；
  - 每 skill 明细表：最新一次快照中每个 skill 的当前数据。
- **自动采集**：支持用 WorkBuddy 自动化做每日定时采集；未设置则只在手动触发当天记录。
- **到期重授权**：token 约 7 天过期，过期后采集失败并明确提示重新授权。

## 安装

将本仓库放到 WorkBuddy 的技能目录：

```
~/.workbuddy/skills/Skill-Favor-Metric/
```

## 首次授权（必须）

接口需要登录态 Cookie（`skh_token` + `sid`），且**不硬编码任何身份**——由使用者自己登录后提供。

1. 用 `web-access` 打开 `https://skillhub.cn` 并登录（或你已在浏览器登录）。
2. 登录后按 F12 → Network → 复制任意一个 `api.skillhub.cn` 请求的 **Cookie 请求头整段文本**，存成文件（如 `cookie.txt`）。
3. 写入凭证：

```bash
python <skill_dir>/scripts/auth.py --import-cookie-file cookie.txt
# 或： echo "<cookie文本>" | python <skill_dir>/scripts/auth.py --stdin
```

4. 校验：`python <skill_dir>/scripts/auth.py --check` 应返回 `OK`。

## 日常使用

```bash
# 采集今日快照（翻页拉全量 + 写本地）
python <skill_dir>/scripts/fetch.py

# 生成 HTML 看板（默认写到数据目录 report.html）
python <skill_dir>/scripts/report.py
```

`fetch.py` 输出 JSON 摘要；失败时退出码非 0 且 stderr 含 `AUTH_EXPIRED` / `FETCH_ERROR` / `PARSE_ERROR`。

## 开启每日自动采集（可选）

用 WorkBuddy 的 `automation_update` 工具创建每日任务，prompt 例如：

```
运行 Skill Favor Metric 的每日采集（静默模式）：执行 <skill_dir>/scripts/fetch.py；
若失败（如 token 过期）直接输出提示告知用户需要重新授权。
```

- 未设置自动化时，只在手动触发当天记录一条快照（符合需求）。
- 若设置「每天多次」，脚本按日期 key 合并，仍只保留当天最后一次。

## 数据存储位置（刻意放在 skill 目录之外）

- 数据快照：`~/.workbuddy/skillhub-stats/snapshots.json`
- 凭证：`~/.workbuddy/skillhub-stats/credentials.json`（仅本机，权限 600 / Windows 下 icacls 限制为当前用户，绝不进 git）

## 已知限制

- `installs` / `stars` 当前多为 0，对应折线初期是平地，有数据后自动显示。
- token 有效期约 7 天，过期后自动采集会失败并提示重新授权（这是预期的重授权机制，不是 bug）。
- 后台接口为内部接口，字段可能变更；`PARSE_ERROR` 即信号。

## 测试

```bash
python tests/run_tests.py
```

使用本地 mock 服务覆盖：正常分页、小页翻页、同日覆盖写、401 过期、网络错误、结构异常、缺凭证、凭证写入与权限、报表折线含 0、多天快照、无数据等场景。
