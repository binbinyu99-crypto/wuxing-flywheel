# -*- coding: utf-8 -*-
"""Engram Knowledge Graph Builder v2.0
Fetches run data from Flywheel API and builds cross-topic knowledge graph."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import urllib.request
import os

def bigram_similarity(s1, s2):
    """Bigram Jaccard similarity between two strings."""
    if not s1 or not s2:
        return 0.0
    bigrams1 = set(s1[i:i+2] for i in range(len(s1)-1))
    bigrams2 = set(s2[i:i+2] for i in range(len(s2)-1))
    if not bigrams1 or not bigrams2:
        return 0.0
    intersection = bigrams1 & bigrams2
    union = bigrams1 | bigrams2
    return len(intersection) / len(union) if union else 0.0

def fetch_runs():
    """Fetch all runs from the flywheel API."""
    url = "http://127.0.0.1:8100/runs"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get("runs", [])
    except Exception as e:
        print(f"Error fetching runs: {e}")
        return []

def detect_topic_category(topic):
    """Categorize topic into industry/domain."""
    topic_lower = topic.lower()
    
    categories = {
        "battery_energy": ["电池", "固态", "半固态", "新能源", "风光", "储能", "光伏", "风电", "充电"],
        "ai_chip": ["AI芯片", "芯片", "Cerebras", "SK海力士", "半导体", "算力", "数据中心"],
        "ai_company": ["小红书", "Anthropic", "软银", "AI", "Agent", "大模型"],
        "real_estate": ["住宅", "房地产", "深圳", "绵阳", "改善型", "房价", "住房"],
        "finance_stock": ["A股", "KOSPI", "中金", "摩根大通", "IPO", "拓普集团", "Beta Capital", "期权"],
        "biotech": ["合成生物学", "基因编辑", "CRISPR", "生物制造", "仿生", "3D打印"],
        "philosophy_ethics": ["电车难题", "AGI伦理", "哲学", "道德"],
        "academic": ["复杂系统", "行为经济学", "学科分析", "认知分析"],
        "news_digest": ["晚报", "点1氪", "快讯", "热点"],
        "skycetus_internal": ["SkyCetus", "五行飞轮", "Grand Cycle", "V6"],
        "auto_ev": ["低空经济", "eVTOL", "汽车", "特斯拉", "人形机器人"],
    }
    
    scores = {}
    for category, keywords in categories.items():
        score = sum(1 for kw in keywords if kw.lower() in topic_lower)
        if score > 0:
            scores[category] = score
    
    if not scores:
        return "other"
    return max(scores, key=scores.get)

def build_knowledge_graph(runs):
    """Build knowledge graph from run topics."""
    if not runs:
        print("No runs found!")
        return None
    
    print(f"Processing {len(runs)} runs...")
    
    # Build nodes with categories
    nodes = []
    for r in runs:
        topic = r.get("topic", "")[:200]
        if len(topic) < 5:
            continue
        category = detect_topic_category(topic)
        nodes.append({
            "id": r.get("run_id", ""),
            "topic": topic,
            "score": r.get("score", 0),
            "verdict": r.get("verdict", ""),
            "grade": r.get("grade", ""),
            "category": category,
            "started_at": r.get("started_at", "")[:10]
        })
    
    print(f"Valid nodes: {len(nodes)}")
    
    # Category distribution
    from collections import Counter
    cat_counts = Counter(n["category"] for n in nodes)
    print("\nCategory distribution:")
    for cat, count in cat_counts.most_common():
        print(f"  {cat}: {count}")
    
    # Compute pairwise similarity (only within same category for relevance)
    edges = []
    for i in range(len(nodes)):
        for j in range(i+1, len(nodes)):
            # Only compute similarity within same category or adjacent categories
            if nodes[i]["category"] != nodes[j]["category"]:
                continue
            sim = bigram_similarity(nodes[i]["topic"], nodes[j]["topic"])
            if sim >= 0.10:
                edges.append({
                    "from": nodes[i]["id"],
                    "to": nodes[j]["id"],
                    "similarity": round(sim, 3),
                    "category": nodes[i]["category"]
                })
    
    edges.sort(key=lambda x: x["similarity"], reverse=True)
    
    print(f"\nKnowledge graph edges (within-category, sim >= 0.10): {len(edges)}")
    print("\nTop connections:")
    for e in edges[:15]:
        n1 = next((n for n in nodes if n["id"] == e["from"]), None)
        n2 = next((n for n in nodes if n["id"] == e["to"]), None)
        if n1 and n2:
            print(f"  {e['similarity']:.3f} [{e['category']}] {n1['topic'][:40]} <-> {n2['topic'][:40]}")
    
    # Build cluster summary
    clusters = {}
    for cat in set(n["category"] for n in nodes):
        cat_nodes = [n for n in nodes if n["category"] == cat]
        cat_edges = [e for e in edges if e["category"] == cat]
        avg_score = round(sum(n["score"] for n in cat_nodes) / len(cat_nodes), 3) if cat_nodes else 0
        converged = sum(1 for n in cat_nodes if n["verdict"] == "converged")
        clusters[cat] = {
            "node_count": len(cat_nodes),
            "edge_count": len(cat_edges),
            "avg_score": avg_score,
            "converged_rate": round(converged / len(cat_nodes), 2) if cat_nodes else 0,
            "topics": [n["topic"][:60] for n in cat_nodes[:5]]
        }
    
    # Save graph
    graph = {
        "nodes": nodes,
        "edges": edges,
        "clusters": clusters,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "categories": len(cat_counts),
            "date_range": f"{nodes[-1]['started_at']} to {nodes[0]['started_at']}" if nodes else ""
        }
    }
    
    output_path = r"D:\ClawMatrix\engram_knowledge_graph.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    print(f"\nKnowledge graph saved to {output_path}")
    print(f"Stats: {graph['stats']}")
    
    return graph

if __name__ == "__main__":
    print("=== Engram Knowledge Graph Builder v2.0 ===\n")
    runs = fetch_runs()
    if runs:
        build_knowledge_graph(runs)
    else:
        print("No data available")
