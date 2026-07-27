import sys
import os
import json
import math
import webbrowser
import argparse
from datetime import datetime, timezone, timedelta
from common import snapshots_path

_BJ = timezone(timedelta(hours=8))


def esc(x):
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def fmt_ts(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, _BJ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "-"


def _nice_max(v):
    """把 Y 轴上界取整到“好看”的数：1/2/2.5/5/10 的倍数。"""
    if v <= 0:
        return 10
    exp = 10 ** int(math.log10(v))
    n = v / exp
    for step in (1, 2, 2.5, 5, 10):
        if n <= step:
            return int(step * exp)
    return int(10 * exp)


def build_svg(dates, dl, ins, st):
    """纯静态 SVG 折线图，不依赖任何 JS 库，所有预览器都能直接渲染。"""
    W, H = 800, 400
    ml, mr, mt, mb = 50, 20, 30, 56
    pw, ph = W - ml - mr, H - mt - mb
    allv = dl + ins + st
    maxv = max(allv) if allv else 0
    ymax = _nice_max(maxv)
    n = len(dates)

    def x_of(i):
        if n <= 1:
            return ml + pw / 2.0
        return ml + pw * i / (n - 1)

    def y_of(v):
        return mt + ph * (1 - v / ymax)

    p = []
    p.append('<svg viewBox="0 0 %d %d" width="100%%" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">' % (W, H))
    # Y 轴网格 + 刻度
    ticks = 5
    for t in range(ticks + 1):
        val = ymax * t / ticks
        y = y_of(val)
        p.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#262b33" stroke-width="1"/>' % (ml, y, ml + pw, y))
        p.append('<text x="%g" y="%g" fill="#9aa0a6" font-size="11" text-anchor="end">%d</text>' % (ml - 8, y + 4, int(val)))
    # X 轴基线
    p.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#444" stroke-width="1"/>' % (ml, mt + ph, ml + pw, mt + ph))
    for i, d in enumerate(dates):
        x = x_of(i)
        label = (d[5:] if d and len(d) >= 10 else d or "")
        p.append('<text x="%g" y="%g" fill="#9aa0a6" font-size="11" text-anchor="middle">%s</text>' % (x, mt + ph + 18, label))
    # 三条线：下载量 / 安装数 / 星标
    series = [("下载量", dl, "#ef4444"), ("安装数", ins, "#22c55e"), ("星标", st, "#3b82f6")]
    for name, data, color in series:
        if n == 0 or not data:
            continue
        if n == 1:
            cx, cy = x_of(0), y_of(data[0])
            p.append('<circle cx="%g" cy="%g" r="4" fill="%s"/>' % (cx, cy, color))
            p.append('<text x="%g" y="%g" fill="%s" font-size="11">%s</text>' % (cx + 8, cy + 4, color, data[0]))
        else:
            pts = " ".join("%g,%g" % (x_of(i), y_of(v)) for i, v in enumerate(data))
            p.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2"/>' % (pts, color))
            for i, v in enumerate(data):
                cx, cy = x_of(i), y_of(v)
                p.append('<circle cx="%g" cy="%g" r="3.5" fill="%s"/>' % (cx, cy, color))
                p.append('<text x="%g" y="%g" fill="%s" font-size="11">%s</text>' % (cx + 6, cy - 7, color, v))
    # 图例
    lx = ml
    ly = H - 12
    for name, data, color in series:
        p.append('<rect x="%g" y="%g" width="10" height="10" fill="%s"/>' % (lx, ly - 9, color))
        p.append('<text x="%g" y="%g" fill="#e6e6e6" font-size="11">%s</text>' % (lx + 14, ly, name))
        lx += 70
    p.append('</svg>')
    return "\n".join(p)


TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Skill Favor Metric 看板</title>
<style>
  body{background:#0f1115;color:#e6e6e6;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;padding:24px;}
  h1{font-size:20px;margin:0 0 4px;}
  .sub{color:#9aa0a6;font-size:13px;margin-bottom:20px;}
  .card{background:#171a21;border:1px solid #262b33;border-radius:12px;padding:16px;margin-bottom:20px;}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #262b33;}
  th{color:#9aa0a6;font-weight:600;}
  tr:hover td{background:#1d212a;}
</style>
</head>
<body>
<h1>SkillHub 发布数据看板</h1>
<div class="sub">最新快照日期：__DATE__ ｜ 数据本地存储于 ~/.workbuddy/skillhub-stats/snapshots.json</div>
<div class="card">__CHART__</div>
<div class="card">
  <div style="font-weight:600;margin-bottom:10px;">每 Skill 当前数据（最新快照）</div>
  <table>
    <thead><tr><th>名称</th><th>slug</th><th>分类</th><th>下载</th><th>安装</th><th>星标</th><th>版本</th><th>更新时间</th></tr></thead>
    <tbody>__ROWS__</tbody>
  </table>
</div>
</body>
</html>
"""


def build_html(dates, dl, ins, st, skills, latest_date):
    rows = ""
    for s in skills:
        rows += (
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
            "<td>%s</td><td>%s</td><td>%s</td></tr>" % (
                esc(s.get("name")), esc(s.get("slug")), esc(s.get("category")),
                s.get("downloads"), s.get("installs"), s.get("stars"),
                esc(s.get("version")), esc(fmt_ts(s.get("updatedAt"))),
            )
        )
    svg = build_svg(dates, dl, ins, st)
    return (TEMPLATE
            .replace("__CHART__", svg)
            .replace("__ROWS__", rows)
            .replace("__DATE__", latest_date or ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    sp = snapshots_path(args.data_dir)
    if not os.path.exists(sp):
        print("ERROR: 暂无快照数据，请先运行 fetch.py", file=sys.stderr)
        sys.exit(1)
    with open(sp, "r", encoding="utf-8") as f:
        snapshots = json.load(f)

    if isinstance(snapshots, list):
        snaps = sorted(snapshots, key=lambda s: s.get("date", ""))
    else:
        snaps = sorted(snapshots.values(), key=lambda s: s.get("date", ""))

    dates = [s.get("date") for s in snaps]
    dl = [s.get("total", {}).get("downloads", 0) for s in snaps]
    ins = [s.get("total", {}).get("installs", 0) for s in snaps]
    st = [s.get("total", {}).get("stars", 0) for s in snaps]

    latest = snaps[-1] if snaps else {"skills": []}
    skills = latest.get("skills", [])

    out = args.output or os.path.join(os.path.dirname(sp), "report.html")
    out_dir = os.path.dirname(os.path.abspath(out))
    os.makedirs(out_dir, exist_ok=True)

    html = build_html(dates, dl, ins, st, skills, latest.get("date"))
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(json.dumps({
        "status": "ok",
        "reportPath": out,
        "dates": dates,
        "skillCount": len(skills),
    }, ensure_ascii=False))

    # 自动用系统默认浏览器打开报告，确保用户一定能看到（不依赖 AI 调 present_files）
    try:
        webbrowser.open("file://" + os.path.abspath(out))
    except Exception:
        pass


if __name__ == "__main__":
    main()
