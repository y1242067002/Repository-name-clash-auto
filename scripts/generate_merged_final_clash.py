import os, yaml, base64, requests, socket, time
from urllib.parse import urlparse, unquote

sources_file = "sub/sources.txt"
out_main = "output/merged.yaml"
out_fast = "output/fast.yaml"

top_candidates = 500
top_stable = 50
top_fast = 30

ping_timeout = 0.6
test_rounds = 2   # 多次测速（更稳）

# ---------------- 获取 ----------------
def fetch(url):
    try:
        return requests.get(url, timeout=15).text
    except:
        return ""

def decode(content):
    try:
        return base64.b64decode(content).decode()
    except:
        return content

# ---------------- 解析 ----------------
def parse_line(line):
    try:
        if line.startswith("vmess://"):
            d = yaml.safe_load(base64.b64decode(line[8:] + "==").decode())
            return {
                "name": d.get("ps","vmess"),
                "type": "vmess",
                "server": d["add"],
                "port": int(d["port"]),
                "uuid": d["id"],
                "alterId": int(d.get("aid",0)),
                "cipher": "auto"
            }

        if line.startswith("trojan://"):
            p = urlparse(line[9:])
            return {
                "name": unquote(p.fragment) or "trojan",
                "type": "trojan",
                "server": p.hostname,
                "port": p.port,
                "password": p.username
            }

        if line.startswith("vless://"):
            p = urlparse(line[8:])
            return {
                "name": unquote(p.fragment) or "vless",
                "type": "vless",
                "server": p.hostname,
                "port": p.port,
                "uuid": p.username
            }
    except:
        return None

def parse(content):
    nodes = []
    for l in content.splitlines():
        n = parse_line(l.strip())
        if n and n.get("server") and n.get("port"):
            nodes.append(n)
    return nodes

# ---------------- TCP测速 ----------------
def ping(host, port):
    delays = []
    for _ in range(test_rounds):
        try:
            s = socket.socket()
            s.settimeout(ping_timeout)
            t = time.time()
            s.connect((host, port))
            s.close()
            delays.append((time.time() - t) * 1000)
        except:
            return None

    return sum(delays)/len(delays)

# ---------------- 主流程 ----------------
os.makedirs("output", exist_ok=True)

urls = open(sources_file).read().splitlines()
nodes = []

for u in urls:
    nodes += parse(decode(fetch(u)))

# 去重
unique, seen = [], set()
for n in nodes:
    k = f"{n['server']}:{n['port']}"
    if k not in seen:
        seen.add(k)
        unique.append(n)

candidates = unique[:top_candidates]

# 测速 + 淘汰失败节点
valid = []
for n in candidates:
    d = ping(n["server"], n["port"])
    if d:
        n["delay"] = d
        valid.append(n)

# 排序
valid.sort(key=lambda x: x["delay"])

stable = valid[:top_stable]
fast = valid[:top_fast]

# ---------------- 生成 YAML ----------------
def build(nodes, path):
    names = [n["name"] for n in nodes] or ["占位"]

    config = {
        "port": 7890,
        "mode": "rule",
        "proxies": nodes,
        "proxy-groups": [
            {
                "name": "🚀 自动选择",
                "type": "url-test",
                "url": "http://www.gstatic.com/generate_204",
                "interval": 120,
                "tolerance": 20,
                "proxies": names
            }
        ],
        "rules": [
            "MATCH,🚀 自动选择"
        ]
    }

    with open(path, "w") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)

build(stable, out_main)
build(fast, out_fast)

print(f"✅ 稳定节点: {len(stable)} | 极速节点: {len(fast)}")
