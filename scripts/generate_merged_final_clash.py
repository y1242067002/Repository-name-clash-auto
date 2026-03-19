import os, yaml, base64, requests, socket, time
from urllib.parse import urlparse, unquote

# ===== 基础配置 =====
sources_file = "sub/sources.txt"
output_file = "output/merged.yaml"

ping_timeout = 0.6
max_nodes = 50   # 最终节点数量（建议 30~80）

# ===== 获取订阅 =====
def fetch(url):
    try:
        return requests.get(url, timeout=15).text
    except:
        return ""

# ===== 自动识别 base64 =====
def decode(content):
    try:
        return base64.b64decode(content).decode()
    except:
        return content

# ===== 节点解析 =====
def parse_line(line):
    try:
        # vmess
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

        # trojan
        if line.startswith("trojan://"):
            p = urlparse(line[9:])
            return {
                "name": unquote(p.fragment) or "trojan",
                "type": "trojan",
                "server": p.hostname,
                "port": p.port,
                "password": p.username
            }

        # vless
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

# ===== TCP测速 =====
def ping(host, port):
    try:
        s = socket.socket()
        s.settimeout(ping_timeout)
        start = time.time()
        s.connect((host, port))
        s.close()
        return (time.time() - start) * 1000
    except:
        return None

# ===== 主流程 =====
os.makedirs("output", exist_ok=True)

nodes = []

# 读取 sources
with open(sources_file, "r", encoding="utf-8") as f:
    urls = f.read().splitlines()

for url in urls:
    if not url.strip():
        continue

    content = decode(fetch(url.strip()))

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        node = parse_line(line)

        if node and node.get("server") and node.get("port"):
            delay = ping(node["server"], node["port"])

            # ⭐ 核心改动（关键！）
            if delay:
                node["delay"] = delay
                node["quality"] = 1   # 优质节点
            else:
                node["delay"] = 9999
                node["quality"] = 0   # 备用节点

            nodes.append(node)

# ===== 去重 =====
unique = []
seen = set()

for n in nodes:
    key = f"{n['server']}:{n['port']}"
    if key not in seen:
        seen.add(key)
        unique.append(n)

# ===== 排序（重点！）=====
nodes = sorted(unique, key=lambda x: (-x["quality"], x["delay"]))

# ===== 截取 =====
nodes = nodes[:max_nodes]

# ===== 生成 YAML =====
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

with open(output_file, "w", encoding="utf-8") as f:
    yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)

print(f"✅ 完成：共 {len(nodes)} 个节点（已筛选）")
