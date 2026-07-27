import os
import json
import time
import base64
import urllib.request
import urllib.error

DEFAULT_DATA_DIR = os.path.expanduser("~/.workbuddy/skillhub-stats")
SNAPSHOTS_FILE = "snapshots.json"
CRED_FILE = "credentials.json"


def data_dir(custom=None):
    d = custom or os.environ.get("SKILL_FAVOR_DATA_DIR") or DEFAULT_DATA_DIR
    os.makedirs(d, exist_ok=True)
    return d


def snapshots_path(custom=None):
    return os.path.join(data_dir(custom), SNAPSHOTS_FILE)


def cred_path(custom=None):
    return os.path.join(data_dir(custom), CRED_FILE)


def load_credentials(custom=None):
    p = cred_path(custom)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_credentials(skh_token, sid, custom=None):
    d = data_dir(custom)
    os.makedirs(d, exist_ok=True)
    p = cred_path(custom)
    payload = {"skh_token": skh_token, "sid": sid, "savedAt": int(time.time() * 1000)}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    try:
        if os.name == "nt":
            # Windows 不走 POSIX 权限位，用 icacls 收为仅当前用户可读写
            import subprocess
            user = os.environ.get("USERNAME", "")
            if user:
                subprocess.run(
                    ["icacls", p, "/inheritance:r", "/grant:r", "%s:(R,W)" % user],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            os.chmod(p, 0o600)
    except Exception:
        pass
    return p


def decode_jwt_exp(token):
    try:
        seg = token.split(".")[1]
        seg += "=" * (-len(seg) % 4)
        payload = json.loads(base64.urlsafe_b64decode(seg))
        return payload.get("exp")
    except Exception:
        return None


def is_expired(cred, skew=3600):
    if not cred or not cred.get("skh_token"):
        return True
    exp = decode_jwt_exp(cred["skh_token"])
    if exp is None:
        saved = cred.get("savedAt", 0)
        return (time.time() * 1000 - saved) > (6 * 86400 * 1000)
    return time.time() > (exp - skew)


def parse_cookie(raw):
    raw = (raw or "").strip()
    if raw.startswith("{"):
        try:
            o = json.loads(raw)
            return o.get("skh_token"), o.get("sid")
        except Exception:
            pass
    skh = sid = None
    for part in raw.split(";"):
        part = part.strip()
        if part.startswith("skh_token="):
            skh = part[len("skh_token="):]
        elif part.startswith("sid="):
            sid = part[len("sid="):]
    return skh, sid


def today_key():
    return time.strftime("%Y-%m-%d", time.localtime())


def http_get_json(url, cookie_value, timeout=20):
    req = urllib.request.Request(url, headers={
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json",
        "origin": "https://skillhub.cn",
        "referer": "https://skillhub.cn/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
        "cookie": cookie_value,
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.getcode(), resp.read().decode("utf-8")
