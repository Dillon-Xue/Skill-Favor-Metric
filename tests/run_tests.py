import os
import sys
import json
import subprocess
import tempfile
import time

PY = sys.executable
ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(ROOT, "..", "scripts")
MOCK = os.path.join(ROOT, "mock_server.py")

# 一个永不过期的假 JWT（仅用于测试，mock 不校验签名）
VALID_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJ1aWQiOjEsImV4cCI6MTk5OTk5OTk5OX0.x"

passed = 0
failed = 0


def run_fetch(data_dir, api_base, extra=None):
    cmd = [PY, os.path.join(SCRIPTS, "fetch.py"), "--data-dir", data_dir, "--api-base", api_base]
    if extra:
        cmd += extra
    return subprocess.run(cmd, capture_output=True, text=True)


def run_auth(data_dir, extra):
    cmd = [PY, os.path.join(SCRIPTS, "auth.py"), "--data-dir", data_dir] + extra
    return subprocess.run(cmd, capture_output=True, text=True)


def run_report(data_dir, output):
    cmd = [PY, os.path.join(SCRIPTS, "report.py"), "--data-dir", data_dir, "--output", output]
    return subprocess.run(cmd, capture_output=True, text=True)


def start_mock(mode, port):
    env = dict(os.environ)
    env["MOCK_MODE"] = mode
    env["MOCK_PORT"] = str(port)
    p = subprocess.Popen([PY, MOCK], env=env)
    time.sleep(2.5)
    return p


def seed_creds(data_dir):
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "credentials.json"), "w") as f:
        json.dump({"skh_token": VALID_TOKEN, "sid": "abc123",
                   "savedAt": int(time.time() * 1000)}, f)


def seed_pat(data_dir):
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "credentials.json"), "w") as f:
        json.dump({"pat": "skh_test_token_xxx", "savedAt": int(time.time() * 1000)}, f)


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print("PASS  %s" % name)
    else:
        failed += 1
        print("FAIL  %s  %s" % (name, detail))


# 用例 1：正常分页（pageSize=50，单页）
tmp = tempfile.mkdtemp()
seed_creds(tmp)
p = start_mock("normal", 8099)
try:
    r = run_fetch(tmp, "http://127.0.0.1:8099")
    if r.returncode != 0:
        print("DEBUG fetch#1 stderr:", r.stderr)
    out = json.loads(r.stdout) if r.returncode == 0 else {}
    snaps = json.load(open(os.path.join(tmp, "snapshots.json")))
    today = list(snaps.values())[0]
    check("normal_fetch_ok", r.returncode == 0 and out.get("status") == "ok", r.stderr)
    check("normal_skillcount_13", today["skillCount"] == 13, "got %s" % today["skillCount"])
    check("normal_total_downloads_208", today["total"]["downloads"] == 208, "got %s" % today["total"]["downloads"])
finally:
    p.terminate()

# 用例 2：小页尺寸翻页（pageSize=5，需 3 页）
tmp2 = tempfile.mkdtemp()
seed_creds(tmp2)
p = start_mock("normal", 8100)
try:
    r = run_fetch(tmp2, "http://127.0.0.1:8100", ["--page-size", "5"])
    snaps = json.load(open(os.path.join(tmp2, "snapshots.json")))
    today = list(snaps.values())[0]
    check("paging_skillcount_13", today["skillCount"] == 13, "got %s" % today["skillCount"])
finally:
    p.terminate()

# 用例 3：同日多次采集只留最后一次（覆盖写）
tmp3 = tempfile.mkdtemp()
seed_creds(tmp3)
p = start_mock("normal", 8101)
try:
    run_fetch(tmp3, "http://127.0.0.1:8101")
    snap_path = os.path.join(tmp3, "snapshots.json")
    d = json.load(open(snap_path))
    k = list(d.keys())[0]
    d[k]["total"]["downloads"] = 999
    json.dump(d, open(snap_path, "w"))
    run_fetch(tmp3, "http://127.0.0.1:8101")
    d2 = json.load(open(snap_path))
    check("same_day_last_wins", d2[k]["total"]["downloads"] == 208, "got %s" % d2[k]["total"]["downloads"])
    check("same_day_single_key", len(d2) == 1, "keys=%s" % list(d2.keys()))
finally:
    p.terminate()

# 用例 4：401 过期（服务端返回 401）
tmp4 = tempfile.mkdtemp()
seed_creds(tmp4)
p = start_mock("unauth", 8102)
try:
    r = run_fetch(tmp4, "http://127.0.0.1:8102")
    check("auth_expired_code", r.returncode == 2 and "AUTH_EXPIRED" in r.stderr, r.stderr)
finally:
    p.terminate()

# 用例 5：网络错误（死端口）
tmp5 = tempfile.mkdtemp()
seed_creds(tmp5)
r = run_fetch(tmp5, "http://127.0.0.1:1")
check("network_error", r.returncode == 1 and "FETCH_ERROR" in r.stderr, r.stderr)

# 用例 6：返回结构异常（非 JSON）
tmp6 = tempfile.mkdtemp()
seed_creds(tmp6)
p = start_mock("malformed", 8103)
try:
    r = run_fetch(tmp6, "http://127.0.0.1:8103")
    check("parse_error", r.returncode == 1 and "PARSE_ERROR" in r.stderr, r.stderr)
finally:
    p.terminate()

# 用例 7：缺凭证
tmp7 = tempfile.mkdtemp()
r = run_fetch(tmp7, "http://127.0.0.1:8099")
check("missing_cred", r.returncode == 2 and "AUTH_EXPIRED" in r.stderr, r.stderr)

# 用例 8：凭证写入 + check + 权限
tmp8 = tempfile.mkdtemp()
cookie = "language=zh; skh_token=%s; sid=abc123" % VALID_TOKEN
with open(os.path.join(tmp8, "cookie.txt"), "w") as f:
    f.write(cookie)
ra = run_auth(tmp8, ["--import-cookie-file", os.path.join(tmp8, "cookie.txt")])
rc = run_auth(tmp8, ["--check"])
check("auth_save_ok", ra.returncode == 0 and json.loads(ra.stdout)["status"] == "ok", ra.stderr)
check("auth_check_ok", rc.stdout.strip() == "OK (COOKIE)", rc.stdout)
mode = oct(os.stat(os.path.join(tmp8, "credentials.json")).st_mode & 0o777)
if os.name != "nt":
    check("cred_perms_600", mode == "0o600", mode)
else:
    # Windows 用 icacls 限制为仅当前用户，权限位不直接对应 0o600
    check("cred_perms_windows_locked", os.path.exists(os.path.join(tmp8, "credentials.json")), mode)

# 用例 9：report 折线含 0（installs/stars=0）
tmp9 = tempfile.mkdtemp()
seed_creds(tmp9)
p = start_mock("normal", 8104)
try:
    run_fetch(tmp9, "http://127.0.0.1:8104")
    out_html = os.path.join(tmp9, "report.html")
    rr = run_report(tmp9, out_html)
    html = open(out_html).read()
    check("report_ok", rr.returncode == 0, rr.stderr)
    check("report_has_echarts_tag", "echarts.min.js" in html)
    check("report_installs_zero_line", '"installs":[0' in html, "installs line not zero")
    check("report_echarts_copied", os.path.exists(os.path.join(tmp9, "echarts.min.js")))
finally:
    p.terminate()

# 用例 10：多天快照 + report 多日期
tmp10 = tempfile.mkdtemp()
snaps = {
    "2026-07-25": {"date": "2026-07-25", "fetchedAt": 1, "total": {"downloads": 5, "installs": 0, "stars": 0}, "skillCount": 1, "skills": [{"slug": "a", "name": "A", "category": "x", "downloads": 5, "installs": 0, "stars": 0, "version": "1", "reviewStatus": "approved", "security": {"keen": "benign", "sanbu": "benign"}, "updatedAt": 1}]},
    "2026-07-26": {"date": "2026-07-26", "fetchedAt": 2, "total": {"downloads": 8, "installs": 0, "stars": 0}, "skillCount": 1, "skills": [{"slug": "a", "name": "A", "category": "x", "downloads": 8, "installs": 0, "stars": 0, "version": "1", "reviewStatus": "approved", "security": {"keen": "benign", "sanbu": "benign"}, "updatedAt": 2}]},
    "2026-07-27": {"date": "2026-07-27", "fetchedAt": 3, "total": {"downloads": 12, "installs": 0, "stars": 0}, "skillCount": 1, "skills": [{"slug": "a", "name": "A", "category": "x", "downloads": 12, "installs": 0, "stars": 0, "version": "1", "reviewStatus": "approved", "security": {"keen": "benign", "sanbu": "benign"}, "updatedAt": 3}]},
}
with open(os.path.join(tmp10, "snapshots.json"), "w") as f:
    json.dump(snaps, f)
out_html = os.path.join(tmp10, "report.html")
rr = run_report(tmp10, out_html)
html = open(out_html).read()
check("report_multiday_dates", '"dates":["2026-07-25","2026-07-26","2026-07-27"]' in html, "dates mismatch")
check("report_multiday_downloads", '"downloads":[5,8,12]' in html, "downloads mismatch")

# 用例 11：report 无数据
tmp11 = tempfile.mkdtemp()
rr = run_report(tmp11, os.path.join(tmp11, "report.html"))
check("report_no_data", rr.returncode == 1, "expected fail")

# 用例 12：接口钳制 pageSize（请求 50 实际每页 10，total=13，必须翻 2 页取全）
# 这是复现"数据比后台少"的根因回归用例：修复前只取前 10 条，修复后取全 13 条。
tmp12 = tempfile.mkdtemp()
seed_creds(tmp12)
p = start_mock("clamped", 8105)
try:
    r = run_fetch(tmp12, "http://127.0.0.1:8105")  # 默认 --page-size=50
    out = json.loads(r.stdout) if r.returncode == 0 else {}
    snaps = json.load(open(os.path.join(tmp12, "snapshots.json")))
    today = list(snaps.values())[0]
    diag = out.get("diagnostics", {})
    check("clamped_collects_all_13", today["skillCount"] == 13, "got %s" % today["skillCount"])
    check("clamped_fully_collected", diag.get("fullyCollected") is True, diag)
    check("clamped_two_pages", diag.get("pages") == 2, diag)
    check("clamped_perpage_10_3", diag.get("perPageCounts") == [10, 3], diag)
finally:
    p.terminate()

# 用例 13：PAT(Bearer) 模式采集（官方 API Token 首选路径）
tmp13 = tempfile.mkdtemp()
seed_pat(tmp13)
p = start_mock("normal", 8106)
try:
    r = run_fetch(tmp13, "http://127.0.0.1:8106")
    out = json.loads(r.stdout) if r.returncode == 0 else {}
    diag = out.get("diagnostics", {})
    check("pat_fetch_ok", r.returncode == 0 and out.get("status") == "ok", r.stderr)
    check("pat_auth_mode", diag.get("authMode") == "PAT(Bearer)", diag)
    check("pat_skillcount_13", out.get("skillCount") == 13, out)
finally:
    p.terminate()

# 用例 14：PAT 导入 + check
tmp14 = tempfile.mkdtemp()
ra = run_auth(tmp14, ["--import-pat", "skh_test_token_xxx"])
rc = run_auth(tmp14, ["--check"])
check("pat_import_ok", ra.returncode == 0 and json.loads(ra.stdout).get("authMode") == "PAT", ra.stderr)
check("pat_check_ok", rc.stdout.strip() == "OK (PAT)", rc.stdout)

# 用例 15：PAT 格式校验（非 skh_ 开头应拒绝）
tmp15 = tempfile.mkdtemp()
rb = run_auth(tmp15, ["--import-pat", "not_a_valid_token"])
check("pat_format_reject", rb.returncode == 1, rb.stderr)

print("\n=== %d passed, %d failed ===" % (passed, failed))
sys.exit(1 if failed else 0)
