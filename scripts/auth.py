import sys
import json
import argparse
from common import (cred_path, load_credentials, save_credentials,
                    is_expired, parse_cookie)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="检查凭证是否存在且未过期")
    ap.add_argument("--import-pat", default=None, help="保存官方 API Token（skh_xxx 格式），使用 Bearer 鉴权")
    ap.add_argument("--import-pat-stdin", action="store_true", help="从标准输入读取 PAT 文本")
    ap.add_argument("--import-cookie-file", default=None, help="从文件读取 Cookie 请求头文本并保存")
    ap.add_argument("--stdin", action="store_true", help="从标准输入读取 Cookie 请求头文本")
    ap.add_argument("--data-dir", default=None)
    args = ap.parse_args()

    if args.check:
        cred = load_credentials(args.data_dir)
        if not cred:
            print("MISSING")
            sys.exit(3)
        if is_expired(cred):
            print("EXPIRED")
            sys.exit(4)
        mode = "PAT" if cred.get("pat") else "COOKIE"
        print("OK (%s)" % mode)
        sys.exit(0)

    # PAT 模式：官方 API Token，Bearer 鉴权
    pat = args.import_pat
    if args.import_pat_stdin:
        pat = sys.stdin.read().strip()
    if pat:
        pat = pat.strip()
        if not pat.startswith("skh_"):
            print("ERROR: PAT 格式异常，应以 skh_ 开头", file=sys.stderr)
            sys.exit(1)
        p = save_credentials(pat=pat, custom=args.data_dir)
        print(json.dumps({"status": "ok", "authMode": "PAT", "credPath": p}, ensure_ascii=False))
        sys.exit(0)

    # Cookie 模式（兜底）
    raw = None
    if args.import_cookie_file:
        with open(args.import_cookie_file, "r", encoding="utf-8") as f:
            raw = f.read()
    elif args.stdin:
        raw = sys.stdin.read()

    if not raw:
        print("ERROR: 未提供凭证（用 --import-pat / --import-cookie-file / --stdin）", file=sys.stderr)
        sys.exit(1)

    skh, sid = parse_cookie(raw)
    if not skh or not sid:
        print("ERROR: 无法从文本中解析出 skh_token / sid", file=sys.stderr)
        sys.exit(1)
    p = save_credentials(skh_token=skh, sid=sid, custom=args.data_dir)
    print(json.dumps({"status": "ok", "authMode": "COOKIE", "credPath": p}, ensure_ascii=False))


if __name__ == "__main__":
    main()
