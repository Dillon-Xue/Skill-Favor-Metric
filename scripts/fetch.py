import sys
import os
import time
import json
import argparse
import urllib.error
from common import (snapshots_path, load_credentials, is_expired,
                    http_get_json, auth_headers, today_key)

API_BASE = "https://api.skillhub.cn"
ENDPOINT = "/api/v1/dashboard/skills"


def fail(code, msg):
    print(json.dumps({"status": "error", "code": code, "message": msg}, ensure_ascii=False),
          file=sys.stderr)
    sys.exit(2 if code == "AUTH_EXPIRED" else 1)


def _num(x):
    try:
        return int(x)
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--api-base", default=API_BASE)
    ap.add_argument("--page-size", type=int, default=50)
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()

    cred = load_credentials(args.data_dir)
    if not cred or is_expired(cred):
        fail("AUTH_EXPIRED", "凭证缺失或已过期，请重新授权（运行 scripts/auth.py --check 查看指引）。")

    auth_mode = "PAT(Bearer)" if cred.get("pat") else "Cookie"

    all_skills = []
    page_info = []
    page = 1
    total = None
    while True:
        url = "%s%s?page=%d&pageSize=%d" % (args.api_base, ENDPOINT, page, args.page_size)
        try:
            code, text = http_get_json(url, auth_headers(cred), timeout=args.timeout)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                fail("AUTH_EXPIRED", "接口返回 %d，token 已失效，请重新授权。" % e.code)
            fail("FETCH_ERROR", "HTTP 错误 %s" % e)
        except Exception as e:
            fail("FETCH_ERROR", "请求失败：%s" % e)

        if code != 200:
            fail("FETCH_ERROR", "接口返回状态码 %s" % code)

        try:
            data = json.loads(text)
        except Exception:
            fail("PARSE_ERROR", "返回不是合法 JSON，接口结构可能已变更。")

        if not isinstance(data, dict) or "skills" not in data:
            fail("PARSE_ERROR", "返回结构异常，缺少 skills 字段。")

        skills = data.get("skills") or []
        if total is None:
            total = data.get("total", len(skills))
        all_skills.extend(skills)
        page_info.append(len(skills))

        if not skills:
            break
        if total is not None and len(all_skills) >= total:
            break
        # 末页信号：本页返回数 < 请求 pageSize。但若 total 已知且仍未取满，说明接口钳制了
        # pageSize（如请求 50 实际每页只回 10），此时不能提前终止，必须继续翻页取全。
        if len(skills) < args.page_size and not (total is not None and len(all_skills) < total):
            break
        page += 1
        if page > 1000:
            break

    totals = {"downloads": 0, "installs": 0, "stars": 0}
    clean = []
    for s in all_skills:
        d = _num(s.get("downloads"))
        i = _num(s.get("installs"))
        st = _num(s.get("stars"))
        totals["downloads"] += d
        totals["installs"] += i
        totals["stars"] += st
        sec = s.get("securityReports") or {}
        clean.append({
            "slug": s.get("slug"),
            "name": s.get("name"),
            "category": s.get("category"),
            "downloads": d,
            "installs": i,
            "stars": st,
            "version": s.get("version"),
            "reviewStatus": s.get("reviewStatus"),
            "security": {
                "keen": (sec.get("keen") or {}).get("status"),
                "sanbu": (sec.get("sanbu") or {}).get("status"),
            },
            "updatedAt": s.get("updatedAt"),
        })

    snap = {
        "date": today_key(),
        "fetchedAt": int(time.time() * 1000),
        "total": totals,
        "skillCount": len(clean),
        "skills": clean,
    }

    # 按日期 key 合并：同一天多次采集只保留最后一次
    sp = snapshots_path(args.data_dir)
    snapshots = {}
    if os.path.exists(sp):
        try:
            with open(sp, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, list):
                snapshots = {s.get("date"): s for s in existing if s.get("date")}
            elif isinstance(existing, dict):
                snapshots = existing
        except Exception:
            snapshots = {}
    snapshots[snap["date"]] = snap
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(snapshots, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "status": "ok",
        "date": snap["date"],
        "totals": totals,
        "skillCount": len(clean),
        "diagnostics": {
            "authMode": auth_mode,
            "totalDeclared": total,
            "collected": len(all_skills),
            "pages": len(page_info),
            "perPageCounts": page_info,
            "pageSizeRequested": args.page_size,
            "fullyCollected": (total is None) or (len(all_skills) >= total),
        },
        "snapshotPath": sp,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
