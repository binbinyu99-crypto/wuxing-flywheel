#!/usr/bin/env python3
"""
Flywheel API Client — 五行飞轮远程分析
用法:
  python flywheel_client.py analyze "话题" [domain]
  python flywheel_client.py status <run_id>
  python flywheel_client.py result <run_id>
  python flywheel_client.py health
  python flywheel_client.py submit "话题" [domain] [mode]
"""
import sys, json, argparse, time

try:
    import requests
except ImportError:
    print("requests not installed, trying urllib fallback...")
    requests = None

BASE = "http://<SERVER_IP>:8100"
TOKEN = "<YOUR_AUTH_TOKEN>"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def _get(path):
    if requests:
        r = requests.get(f"{BASE}{path}", headers={"Authorization": f"Bearer {TOKEN}"}, timeout=30)
        return r.json()
    import urllib.request
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as resp:
        return json.loads(resp.read().decode())

def _post(path, data):
    if requests:
        r = requests.post(f"{BASE}{path}", json=data, headers=HEADERS, timeout=60)
        return r.json()
    import urllib.request
    req = urllib.request.Request(f"{BASE}{path}",
        data=json.dumps(data).encode(), headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())

def analyze(topic, domain="strategy"):
    """Submit and wait for result (blocking, up to 10 min)."""
    resp = _post("/analyze", {"topic": topic, "domain": domain})
    if "error" in resp:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return
    run_id = resp.get("run_id")
    print(f"Run ID: {run_id}")
    print("Waiting for analysis... (polling every 15s)")
    for i in range(40):  # max 10 min
        time.sleep(15)
        prog = _get(f"/progress/{run_id}")
        status = prog.get("status", "unknown")
        print(f"  [{i*15+15}s] status={status}")
        if status in ("completed", "failed", "error"):
            break
    result = _get(f"/result/{run_id}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

def submit(topic, domain="strategy", mode=None):
    """Submit analysis and return run_id immediately (non-blocking)."""
    data = {"topic": topic, "domain": domain}
    if mode:
        data["mode"] = mode
    resp = _post("/analyze", data)
    print(json.dumps(resp, ensure_ascii=False, indent=2))
    return resp

def status(run_id):
    prog = _get(f"/progress/{run_id}")
    print(json.dumps(prog, ensure_ascii=False, indent=2))

def result(run_id):
    res = _get(f"/result/{run_id}")
    print(json.dumps(res, ensure_ascii=False, indent=2))

def health():
    h = _get("/health")
    print(json.dumps(h, ensure_ascii=False, indent=2))

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    
    p = sub.add_parser("analyze", help="Submit + wait for result")
    p.add_argument("topic"); p.add_argument("domain", nargs="?", default="strategy")
    
    p = sub.add_parser("submit", help="Submit and return immediately")
    p.add_argument("topic"); p.add_argument("domain", nargs="?", default="strategy")
    p.add_argument("--mode", choices=["standard","flagship","local"], default=None)
    
    p = sub.add_parser("status", help="Check progress")
    p.add_argument("run_id")
    
    p = sub.add_parser("result", help="Get result")
    p.add_argument("run_id")
    
    sub.add_parser("health", help="Health check")
    
    args = parser.parse_args()
    
    if args.cmd == "analyze":
        analyze(args.topic, args.domain)
    elif args.cmd == "submit":
        submit(args.topic, args.domain, args.mode)
    elif args.cmd == "status":
        status(args.run_id)
    elif args.cmd == "result":
        result(args.run_id)
    elif args.cmd == "health":
        health()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
