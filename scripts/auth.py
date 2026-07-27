import sys
import json
import argparse
from common import (cred_path, load_credentials, save_credentials,
                    is_expired, parse_cookie)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="检查凭证是否存在且未过期")
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
        print("OK")
        sys.exit(0)

    raw = None
    if args.import_cookie_file:
        with open(args.import_cookie_file, "r", encoding="utf-8") as f:
            raw = f.read()
    elif args.stdin:
        raw = sys.stdin.read()

    if not raw:
        print("ERROR: 未提供 cookie 文本（用 --import-cookie-file 或 --stdin）", file=sys.stderr)
        sys.exit(1)

    skh, sid = parse_cookie(raw)
    if not skh or not sid:
        print("ERROR: 无法从文本中解析出 skh_token / sid", file=sys.stderr)
        sys.exit(1)
    p = save_credentials(skh, sid, args.data_dir)
    print(json.dumps({"status": "ok", "credPath": p}, ensure_ascii=False))


if __name__ == "__main__":
    main()
