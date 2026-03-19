import os, yaml, base64, requests, socket, time
from urllib.parse import urlparse, unquote

# ---------------- 配置 ----------------
sources_file = "sub/sources.txt"
output_stable = "output/merged.yaml"
output_fast = "output/fast.yaml"

ping_timeout = 0.6
max_stable = 50
max_fast = 30
test_rounds = 2  # 多次测速，减少误判

# ---------------- 函数 ----------------
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

def parse_line(line):
    try:
        if line.startswith("vmess://"):
            d = yaml.safe_load(base64.b64decode(line[8:] + "==").decode())
            return {
                "name": d.get("ps", "vmess"),
                "type": "vmess",
                "server": d["add"],
                "port": int(d["port"]),
                "uuid": d["id"],
                "alterId": int(d.get("aid", 0)),
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

def ping(host, port):
    delays = []
    for _ in range(test_rounds):
        try:
            s = socket.socket()
            s.settimeout(ping_timeout)
            start = time.time()
            s.connect((host, port))
            s.close()
            delays.append((time.time() - start) * 1000)
        except:
            return None
    return sum(delays)/len(delays) if delays else None

# ---------------- 主流程 ----------------
os.makedirs("output", exist_ok=True)
all_nodes = []

with open(sources_file, "r", encoding="utf-8") as f:
    urls = [u.strip() for u in f.read().splitlines() if u.strip()]

for url in urls:
    content = decode(fetch(url))
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        node = parse_line(line)
        if node and node.get("server") and node.get("port"):
            d = ping(node["server"], node["port"])
            if d:
                node["delay"] = d
                node["quality"] = 1
            else:
                node["delay"] = 9999
                node["quality"] = 0
            all_nodes.append(node)

# 去重
unique, seen = [], set()
for n in all_nodes:
    key = f"{n['server']}:{n['port']}"
    if key not in seen:
        seen.add(key)
        unique.append(n)

# 排序
sorted_nodes = sorted(unique, key=lambda x: (-x["quality"], x["delay"]))

# 分别取稳定版 / 极速版
stable_nodes = sorted_nodes[:max_stable]
fast_nodes = sorted_nodes[:max_fast]

# 生成 YAML
def build_yaml(nodes, path):
    names = [n["name"] for n in nodes] or ["占位"]
    cfg = {
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
        "rules": ["MATCH,🚀 自动选择"]
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

build_yaml(stable_nodes, output_stable)
build_yaml(fast_nodes, output_fast)

print(f"✅ 生成完成：稳定节点 {len(stable_nodes)}，极速节点 {len(fast_nodes)}")
