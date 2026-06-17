# -*- coding: utf-8 -*-
"""
knowledge_tree_api.py - 知识树状态API + 飞轮自动部署管道
部署位置: D:\ClawMatrix\knowledge_tree_api.py
由飞轮API导入，提供以下能力：
1. GET /knowledge-tree - 返回知识树当前状态 + Gap分析
2. POST /auto-deploy - 飞轮完成后自动渲染+部署到网站
3. GET /knowledge-tree/gaps - 返回知识树需要填补的空白
"""

import json, os, time, hashlib, re
from datetime import datetime, timedelta
from pathlib import Path

CONTENT_DIR = r"C:\SkyCetus-2.0\content"
FLYWHEEL_DIR = os.path.join(CONTENT_DIR, "flywheel")
REPORTS_DIR = os.path.join(FLYWHEEL_DIR, "reports")
REGISTRY_PATH = os.path.join(CONTENT_DIR, "page-registry.json")

# ---- 知识树状态读取 ----

def load_registry():
    """加载page-registry.json"""
    try:
        with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"version": "1.0", "updated": "", "total": 0, "pages": []}

def get_knowledge_tree_state():
    """返回知识树完整状态"""
    reg = load_registry()
    pages = reg.get("pages", [])
    
    # 按tier分组
    tiers = {"L0": [], "L1": [], "L2": [], "L3": []}
    for p in pages:
        tier = p.get("tier", "L3")
        tiers.setdefault(tier, []).append(p)
    
    # 统计flywheel报告
    flywheel_reports = []
    if os.path.exists(REPORTS_DIR):
        for f in os.listdir(REPORTS_DIR):
            if f.endswith('.html') and f != 'index.html':
                fpath = os.path.join(REPORTS_DIR, f)
                stat = os.stat(fpath)
                flywheel_reports.append({
                    "name": f,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "url": f"/flywheel/reports/{f}"
                })
    
    # 统计flywheel主目录的专题页
    flywheel_pages = []
    curated_pages = [
        "formulas-2026.html", "ai-agent-2026.html", "ai-education.html",
        "ai-roi-2026.html", "coffee-market-2026.html", "clearing-2026.html",
        "derivatives-2026.html", "ev-battery-recycling-2026.html",
        "nev-overseas-2026.html", "nev-supply-chain-2026.html",
        "risc-v-vs-arm-2026.html", "computing-power-future-trends-2026.html"
    ]
    if os.path.exists(FLYWHEEL_DIR):
        for f in os.listdir(FLYWHEEL_DIR):
            if f.endswith('.html') and f not in ['index.html', 'index.html.bak']:
                fpath = os.path.join(FLYWHEEL_DIR, f)
                stat = os.stat(fpath)
                is_curated = f in curated_pages
                flywheel_pages.append({
                    "name": f,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "curated": is_curated,
                    "url": f"/flywheel/{f}"
                })
    
    return {
        "registry_version": reg.get("version"),
        "registry_updated": reg.get("updated"),
        "total_pages": reg.get("total", len(pages)),
        "tiers": {k: {"count": len(v), "pages": [p["name"] for p in v]} for k, v in tiers.items()},
        "flywheel_reports": flywheel_reports,
        "flywheel_pages_count": len(flywheel_pages),
        "flywheel_curated_count": sum(1 for p in flywheel_pages if p.get("curated")),
        "timestamp": datetime.now().isoformat()
    }

# ---- Gap分析 ----

# 知识树应该覆盖的核心领域
EXPECTED_DOMAINS = {
    "新材料": {"starmap": "materials-starmap.html", "sub_topics": [
        "钙钛矿", "固态电池", "碳化硅", "氮化镓", "石墨烯", "稀土",
        "碳纤维", "气凝胶", "超导材料", "生物基材料"
    ]},
    "商业航天": {"starmap": "starsea.html", "sub_topics": [
        "火箭发射", "卫星制造", "太空旅游", "在轨服务", "深空探测"
    ]},
    "AI芯片": {"starmap": "chip-design.html", "sub_topics": [
        "GPU通用", "可重构FPGA", "存算一体", "刻进芯片", "光子计算", "神经形态"
    ]},
    "新能源汽车": {"starmap": "ev-chain.html", "sub_topics": [
        "动力电池", "电驱系统", "智能驾驶", "充电基础设施", "电池回收"
    ]},
    "金融衍生品": {"starmap": "derivatives-hub.html", "sub_topics": [
        "期权定价", "套期保值", "波动率套利", "券商清算", "风险对冲"
    ]},
    "AGI理论": {"starmap": "kunpeng.html", "sub_topics": [
        "智能压缩论", "TEP框架", "碳硅共生", "对齐悖论", "认知三角"
    ]},
    "生物医药": {"starmap": None, "sub_topics": [
        "基因治疗", "mRNA", "细胞治疗", "AI制药", "脑机接口"
    ]},
    "量子计算": {"starmap": None, "sub_topics": [
        "超导量子", "光量子", "离子阱", "量子纠错", "量子软件"
    ]}
}

def analyze_gaps():
    """分析知识树的Gap"""
    reg = load_registry()
    pages = reg.get("pages", [])
    page_names = set(p["name"] for p in pages)
    
    # 检查flywheel目录的实际文件
    flywheel_files = set()
    if os.path.exists(FLYWHEEL_DIR):
        flywheel_files = set(f for f in os.listdir(FLYWHEEL_DIR) if f.endswith('.html'))
    
    gaps = []
    covered = []
    
    for domain, info in EXPECTED_DOMAINS.items():
        starmap = info["starmap"]
        has_starmap = starmap and (starmap in page_names or starmap in flywheel_files)
        
        sub_coverage = []
        for sub in info["sub_topics"]:
            # 检查是否有对应页面（模糊匹配）
            sub_slug = sub.lower().replace(" ", "-")
            found = any(sub_slug in p.lower() or sub.lower() in p.lower() 
                       for p in page_names | flywheel_files)
            sub_coverage.append({"topic": sub, "covered": found})
        
        coverage_rate = sum(1 for s in sub_coverage if s["covered"]) / max(len(sub_coverage), 1)
        
        entry = {
            "domain": domain,
            "starmap_page": starmap,
            "has_starmap": has_starmap,
            "coverage_rate": round(coverage_rate, 2),
            "sub_topics": sub_coverage,
            "missing": [s["topic"] for s in sub_coverage if not s["covered"]]
        }
        
        if coverage_rate < 0.5 or not has_starmap:
            gaps.append(entry)
        else:
            covered.append(entry)
    
    # 找出L2页面中超过30天没更新的
    stale_pages = []
    for p in pages:
        if p.get("tier") in ["L1", "L2"]:
            # 检查实际文件的修改时间
            fpath = os.path.join(CONTENT_DIR, p["name"])
            if os.path.exists(fpath):
                mtime = datetime.fromtimestamp(os.stat(fpath).st_mtime)
                if datetime.now() - mtime > timedelta(days=30):
                    stale_pages.append({
                        "name": p["name"],
                        "tier": p["tier"],
                        "last_modified": mtime.isoformat(),
                        "days_stale": (datetime.now() - mtime).days
                    })
    
    return {
        "gaps": gaps,
        "covered": covered,
        "stale_l1_l2_pages": stale_pages,
        "summary": {
            "total_domains": len(EXPECTED_DOMAINS),
            "covered_domains": len(covered),
            "gap_domains": len(gaps),
            "stale_pages": len(stale_pages),
            "recommended_next": gaps[0]["domain"] if gaps else None,
            "recommended_topics": gaps[0]["missing"][:3] if gaps else []
        },
        "timestamp": datetime.now().isoformat()
    }

# ---- 飞轮报告自动部署 ----

REPORT_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | SkyCetus Flywheel</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Noto+Sans+SC:wght@300;400;500;700;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/skycetus-base.css">
<style>
.sw{{max-width:1200px;margin:0 auto;padding:40px 20px}}
.hero{{min-height:50vh;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:80px 20px 40px;background:linear-gradient(180deg,#0a0e1a 0%,#0d1520 100%);position:relative}}
.hero::before{{content:'';position:absolute;top:50%;left:50%;width:500px;height:500px;background:radial-gradient(circle,rgba(88,166,255,0.08) 0%,transparent 70%);transform:translate(-50%,-50%)}}
.hero-eyebrow{{font-size:11px;text-transform:uppercase;letter-spacing:.15em;color:#58a6ff;margin-bottom:12px}}
.hero-title{{font-size:clamp(24px,4vw,42px);font-weight:900;background:linear-gradient(135deg,#fff,#8ab4d4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:12px}}
.hero-sub{{color:#7a8ba3;font-size:.95rem;max-width:600px;line-height:1.7}}
.meta-row{{display:flex;gap:20px;justify-content:center;flex-wrap:wrap;margin-top:20px}}
.meta-item{{text-align:center}}
.meta-val{{font-family:'JetBrains Mono';font-size:1.2em;font-weight:700;color:#58a6ff}}
.meta-lbl{{font-size:.7rem;color:#556}}
.section{{margin:48px 0}}
.stitle{{font-size:1.3rem;font-weight:800;color:#e0e8f0;margin-bottom:16px;border-left:3px solid #58a6ff;padding-left:12px}}
.card-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}}
.card{{background:#0d1b2a;border:1px solid #1e3a5f;border-radius:10px;padding:20px;transition:border-color .3s}}
.card:hover{{border-color:#58a6ff}}
.card h3{{font-size:1rem;font-weight:700;color:#e0e8f0;margin-bottom:8px}}
.card p{{font-size:.85rem;color:#7a8ba3;line-height:1.6}}
.dim-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:24px 0}}
.dim{{background:#0d1b2a;border:1px solid #1e3a5f;border-radius:8px;padding:12px;text-align:center}}
.dim-score{{font-family:'JetBrains Mono';font-size:1.4em;font-weight:700}}
.dim-label{{font-size:.72em;color:#556;margin-top:4px}}
.dim-high{{color:#00ff80;border-color:rgba(0,255,128,.3)}}
.dim-mid{{color:#ffd700;border-color:rgba(255,215,0,.3)}}
.dim-low{{color:#ff6666;border-color:rgba(255,80,80,.3)}}
table{{width:100%;border-collapse:collapse;margin:16px 0}}
th,td{{padding:10px 14px;text-align:left;border-bottom:1px solid #1e3a5f;font-size:.85rem}}
th{{color:#58a6ff;font-weight:700;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}}
td{{color:#c0d0e0}}
.verdict{{display:inline-block;padding:4px 12px;border-radius:12px;font-size:.8em;font-weight:700}}
.v-converged{{background:rgba(0,255,128,.1);color:#00ff80;border:1px solid rgba(0,255,128,.2)}}
.v-diverging{{background:rgba(255,100,0,.1);color:#ff9500;border:1px solid rgba(255,100,0,.2)}}
.v-conditional{{background:rgba(255,200,0,.1);color:#ffd700;border:1px solid rgba(255,200,0,.2)}}
.content-block{{background:#0d1b2a;border:1px solid #1e3a5f;border-radius:10px;padding:24px;margin:16px 0;font-size:.9rem;color:#c0d0e0;line-height:1.8}}
.content-block h4{{color:#58a6ff;margin-bottom:12px}}
.tag{{display:inline-block;padding:3px 10px;border-radius:10px;font-size:.72em;font-weight:600;margin-right:6px;margin-bottom:4px}}
.tag-domain{{background:rgba(88,166,255,.12);color:#58a6ff;border:1px solid rgba(88,166,255,.25)}}
.tag-depth{{background:rgba(0,212,255,.12);color:#00d4ff;border:1px solid rgba(0,212,255,.25)}}
.footer{{text-align:center;padding:40px;color:#556;font-size:.8rem;border-top:1px solid #1e3a5f;margin-top:60px}}
</style>
</head>
<body>
<nav id="nav">
  <a href="/">&#x1F40B; SKYCETUS</a>
  <a href="/starsea.html">星辰大海</a>
  <a href="/materials-starmap.html">材料图谱</a>
  <a href="/flywheel/flywheel-live.html">飞轮</a>
  <a href="/flywheel/reports/index.html" style="color:#58a6ff">报告索引</a>
  <a href="/tech.html">技术</a>
</nav>
<div class="hero">
  <div class="hero-eyebrow">WUXING FLYWHEEL · {verdict_upper}</div>
  <h1 class="hero-title">{title}</h1>
  <p class="hero-sub">{description}</p>
  <div class="meta-row">
    <div class="meta-item"><div class="meta-val">{score}</div><div class="meta-lbl">收敛评分</div></div>
    <div class="meta-item"><div class="meta-val">{domain}</div><div class="meta-lbl">分析域</div></div>
    <div class="meta-item"><div class="meta-val">{date}</div><div class="meta-lbl">生成日期</div></div>
    <div class="meta-item"><div class="meta-val">{run_id_short}</div><div class="meta-lbl">Run ID</div></div>
  </div>
</div>
<div class="sw">
{content_html}
<div class="footer">
  <p>SkyCetus Wuxing Flywheel v5.3.0 · 自动生成 · <a href="/flywheel/reports/index.html" style="color:#58a6ff">返回报告索引</a></p>
  <p>Run ID: {run_id} · Score: {score} · Verdict: {verdict} · Feishu: <a href="{feishu_url}" style="color:#58a6ff">{feishu_url}</a></p>
</div>
</div>
</body>
</html>'''

def render_report(run_data):
    """将飞轮分析结果渲染为HTML页面"""
    topic = run_data.get("topic", "未知主题")
    score = run_data.get("score", 0)
    run_id = run_data.get("run_id", "unknown")
    domain = run_data.get("domain", "general")
    verdict = "converged" if score >= 0.7 else ("conditional" if score >= 0.5 else "diverging")
    feishu_url = run_data.get("feishu_doc_url", "")
    content = run_data.get("readable_summary", run_data.get("result", ""))
    
    # 生成slug
    slug = re.sub(r'[^\w\u4e00-\u9fff-]', '-', topic.lower())[:60].strip('-')
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{slug}-{date_str}.html"
    
    # 简单内容HTML化
    content_html = ""
    if isinstance(content, str):
        sections = content.split("\n\n")
        for sec in sections:
            sec = sec.strip()
            if not sec:
                continue
            if sec.startswith("##"):
                title = sec.lstrip("#").strip()
                content_html += f'<div class="section"><h2 class="stitle">{title}</h2></div>\n'
            elif sec.startswith("#"):
                title = sec.lstrip("#").strip()
                content_html += f'<div class="section"><h2 class="stitle">{title}</h2></div>\n'
            else:
                content_html += f'<div class="content-block"><p>{sec}</p></div>\n'
    
    html = REPORT_TEMPLATE.format(
        title=topic,
        description=f"五行飞轮深度分析 · {domain} · Score {score}",
        score=score,
        domain=domain,
        date=date_str,
        run_id=run_id,
        run_id_short=run_id[:12] if run_id else "N/A",
        verdict=verdict,
        verdict_upper=verdict.upper(),
        feishu_url=feishu_url or "#",
        content_html=content_html
    )
    
    return filename, html

def deploy_report(run_data):
    """渲染并部署报告到网站"""
    filename, html = render_report(run_data)
    filepath = os.path.join(REPORTS_DIR, filename)
    
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return {
        "deployed": True,
        "filename": filename,
        "filepath": filepath,
        "url": f"/flywheel/reports/{filename}",
        "size": len(html.encode('utf-8'))
    }

# ---- 更新reports/index.html ----

def update_reports_index():
    """扫描reports目录，重新生成index.html"""
    # 这个函数会被Spark调用，暂时返回当前报告列表
    reports = []
    if os.path.exists(REPORTS_DIR):
        for f in sorted(os.listdir(REPORTS_DIR), reverse=True):
            if f.endswith('.html') and f != 'index.html':
                fpath = os.path.join(REPORTS_DIR, f)
                stat = os.stat(fpath)
                reports.append({
                    "name": f,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "url": f"/flywheel/reports/{f}"
                })
    return reports


if __name__ == "__main__":
    # 测试
    print("=== Knowledge Tree State ===")
    state = get_knowledge_tree_state()
    print(json.dumps(state, indent=2, ensure_ascii=False, default=str))
    
    print("\n=== Gap Analysis ===")
    gaps = analyze_gaps()
    print(json.dumps(gaps, indent=2, ensure_ascii=False, default=str))


# ---- KT Update Functions ----

DOMAIN_MAPPING = {
    "新材料": "materials-starmap.html",
    "商业航天": "starsea.html",
    "AI芯片": "chip-design.html",
    "新能源汽车": "ev-chain.html",
    "金融衍生品": "derivatives-hub.html",
    "AGI理论": "kunpeng.html",
    "生物医药": "materials-starmap.html",
    "量子计算": "starsea.html",
}

def classify_domain(topic):
    topic_lower = topic.lower()
    if any(k in topic_lower for k in ["钙钛矿", "固态电池", "碳化硅", "新材料", "材料科学"]):
        return "新材料"
    if any(k in topic_lower for k in ["航天", "卫星", "火箭", "太空", "商业航天"]):
        return "商业航天"
    if any(k in topic_lower for k in ["芯片", "半导体", "gpu", "ai芯片", "ic", "集成电路"]):
        return "AI芯片"
    if any(k in topic_lower for k in ["新能源", "电动汽车", "充电", "电池", "电动车", "锂电", "动力电池"]):
        return "新能源汽车"
    if any(k in topic_lower for k in ["金融", "期权", "期货", "衍生品", "量化", "对冲"]):
        return "金融衍生品"
    if any(k in topic_lower for k in ["agi", "通用人工智能", "大模型", "llm", "认知", "智能压缩", "tep"]):
        return "AGI理论"
    if any(k in topic_lower for k in ["基因", "mrna", "细胞治疗", "脑机接口", "生物医药", "医药"]):
        return "生物医药"
    if any(k in topic_lower for k in ["量子", "量子计算", "quantum"]):
        return "量子计算"
    return None


def generate_kt_entry(run_id, topic, result, score):
    if isinstance(result, str):
        return None
    kunpeng = result.get("kunpeng", {}) or {}
    verdict = result.get("verdict", "unknown")
    grade = result.get("grade", "N/A")
    kd = kunpeng.get("kun_dive", {})
    if isinstance(kd, dict):
        conclusion = kd.get("conclusion", "")[:500]
        predictions = kd.get("predictions", [])[:3]
    elif isinstance(kd, str):
        conclusion = kd[:500]
        predictions = []
    else:
        predictions = []
    pred_strs = []
    for p in predictions:
        if isinstance(p, dict):
            pred_strs.append("[%s] %s" % (p.get("when",""), p.get("what","")[:100]))
        elif isinstance(p, str):
            pred_strs.append(p[:120])
    gaps = []
    for g in kunpeng.get("data_gaps", [])[:5]:
        if isinstance(g, dict):
            desc = g.get("gap") or g.get("description") or str(g)
            gaps.append(desc[:200])
        elif isinstance(g, str):
            gaps.append(g[:200])
    recs = []
    for r in kunpeng.get("strategic_recommendations", [])[:4]:
        if isinstance(r, dict):
            recs.append(r.get("title", str(r))[:100])
        elif isinstance(r, str):
            recs.append(r[:100])
    return {
        "run_id": run_id,
        "topic": topic,
        "score": score,
        "grade": grade,
        "verdict": verdict,
        "conclusion": conclusion,
        "predictions": pred_strs,
        "data_gaps": gaps,
        "strategic_recs": recs,
        "domain": classify_domain(topic),
        "meta_checks": {
            "dao": bool(kunpeng.get("dao_merge")),
            "buddhist": bool(kunpeng.get("buddhist_three")),
            "freudian": bool(kunpeng.get("freudian_layers")),
            "core_contradiction": bool(kunpeng.get("core_contradiction")),
        },
        "updated": datetime.now().strftime("%Y-%m-%d")
    }


def update_knowledge_tree(run_id, topic, result, score):
    domain = classify_domain(topic)
    if domain is None:
        return {"action": "skip", "reason": "unclassified topic"}
    entry = generate_kt_entry(run_id, topic, result, score)
    if entry is None:
        return {"action": "skip", "reason": "could not parse result"}
    reg = load_registry()
    entries = reg.get("entries", {})
    if domain not in entries or not isinstance(entries.get(domain), list):
        entries[domain] = []
    existing_idx = None
    for i, e in enumerate(entries[domain]):
        if isinstance(e, dict) and e.get("run_id") == run_id:
            existing_idx = i
            break
    if existing_idx is not None:
        entries[domain][existing_idx] = entry
        action = "updated"
    else:
        entries[domain].append(entry)
        action = "created"
    reg["entries"] = entries
    reg["updated"] = datetime.now().isoformat()
    reg["version"] = "1.1"
    save_registry(reg)
    total = sum(len(v) if isinstance(v, list) else 0 for v in entries.values())
    return {"action": action, "domain": domain, "run_id": run_id, "entry_count": len(entries.get(domain,[])), "total_entries": total}


def get_kt_entries():
    reg = load_registry()
    entries = reg.get("entries", {})
    result = {}
    for domain in DOMAIN_MAPPING.keys():
        domain_entries = entries.get(domain, [])
        if isinstance(domain_entries, list):
            result[domain] = {"count": len(domain_entries), "entries": domain_entries[-10:]}
    return result

