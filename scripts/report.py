import sys
import os
import json
import argparse
import shutil
from datetime import datetime, timezone, timedelta
from common import snapshots_path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_ECHARTS = os.path.join(SCRIPT_DIR, "..", "vendor", "echarts.min.js")


def esc(x):
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


_BJ = timezone(timedelta(hours=8))


def fmt_ts(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, _BJ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "-"


TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Skill Favor Metric 看板</title>
<script src="./echarts.min.js"></script>
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
<div class="card"><div id="chart" style="width:100%;height:380px;"></div></div>
<div class="card">
  <div style="font-weight:600;margin-bottom:10px;">每 Skill 当前数据（最新快照）</div>
  <table>
    <thead><tr><th>名称</th><th>slug</th><th>分类</th><th>下载</th><th>安装</th><th>星标</th><th>版本</th><th>更新时间</th></tr></thead>
    <tbody>__ROWS__</tbody>
  </table>
</div>
<script>
var D = __DATA__;
var chart = echarts.init(document.getElementById('chart'), 'dark');
chart.setOption({
  backgroundColor:'transparent',
  tooltip:{trigger:'axis'},
  legend:{data:['下载量','安装数','星标'],textStyle:{color:'#e6e6e6'}},
  grid:{left:50,right:24,top:40,bottom:40},
  xAxis:{type:'category',data:D.dates,axisLine:{lineStyle:{color:'#444'}}},
  yAxis:{type:'value',axisLine:{lineStyle:{color:'#444'}}},
  series:[
    {name:'下载量',type:'line',smooth:true,data:D.downloads,itemStyle:{color:'#ef4444'},label:{show:true,position:'top',fontSize:11,color:'#ef4444'}},
    {name:'安装数',type:'line',smooth:true,data:D.installs,itemStyle:{color:'#22c55e'},label:{show:true,position:'top',fontSize:11,color:'#22c55e'}},
    {name:'星标',type:'line',smooth:true,data:D.stars,itemStyle:{color:'#3b82f6'},label:{show:true,position:'top',fontSize:11,color:'#3b82f6'}}
  ]
});
window.addEventListener('resize', function(){ chart.resize(); });
</script>
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
    data_json = json.dumps({
        "dates": dates,
        "downloads": dl,
        "installs": ins,
        "stars": st,
    }, ensure_ascii=False, separators=(",", ":"))
    return (TEMPLATE
            .replace("__DATA__", data_json)
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

    # 复制 echarts 到输出目录，保证离线自包含
    try:
        dst = os.path.join(out_dir, "echarts.min.js")
        if os.path.exists(VENDOR_ECHARTS):
            shutil.copyfile(VENDOR_ECHARTS, dst)
    except Exception:
        pass

    html = build_html(dates, dl, ins, st, skills, latest.get("date"))
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(json.dumps({
        "status": "ok",
        "reportPath": out,
        "dates": dates,
        "skillCount": len(skills),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
