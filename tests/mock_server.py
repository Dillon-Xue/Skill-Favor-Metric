import os
import sys
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

MODE = os.environ.get("MOCK_MODE", "normal")
PORT = int(os.environ.get("MOCK_PORT", "8099"))


def make_skills(n=13, base_downloads=10):
    cats = ["dev-programming", "content-creation", "ai-agent", "it-ops-security",
            "knowledge-management", "business-ops"]
    skills = []
    for i in range(n):
        skills.append({
            "slug": "skill-%d" % i,
            "name": "测试 Skill %d" % i,
            "category": cats[i % len(cats)],
            "downloads": base_downloads + i,
            "installs": 0,
            "stars": 0,
            "version": "1.0.%d" % i,
            "reviewStatus": "approved",
            "securityReports": {"keen": {"status": "benign"}, "sanbu": {"status": "benign"}},
            "updatedAt": int(time.time() * 1000),
        })
    return skills


ALL = make_skills()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if MODE == "unauth":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"unauthorized")
            return
        if MODE == "malformed":
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b"not-json{")
            return
        if MODE == "slow":
            time.sleep(25)
            return
        if MODE == "clamped":
            # 模拟 skillhub 后端钳制 pageSize：忽略客户端请求的 page_size，强制每页最多 10 条
            qs = parse_qs(urlparse(self.path).query)
            page = int(qs.get("page", ["1"])[0])
            ps = 10
            start = (page - 1) * ps
            end = start + ps
            slice_ = ALL[start:end]
            body = json.dumps({"skills": slice_, "total": len(ALL)}).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        qs = parse_qs(urlparse(self.path).query)
        page = int(qs.get("page", ["1"])[0])
        ps = int(qs.get("pageSize", ["50"])[0])
        start = (page - 1) * ps
        end = start + ps
        slice_ = ALL[start:end]
        body = json.dumps({"skills": slice_, "total": len(ALL)}).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", PORT), H)
    srv.serve_forever()
