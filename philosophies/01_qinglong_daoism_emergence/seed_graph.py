# -*- coding: utf-8 -*-
"""
Seed Graph v1.0
青龙·种子飞轮 — 种子关系图谱

种子之间的关联、竞争、演化关系可视化数据生成
"""
import json, os
from datetime import datetime

class SeedGraph:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "seed_graph.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"nodes": [], "edges": [], "clusters": [], "meta": {"version": "1.0"}}
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def add_seed_node(self, seed_id, name, domain, score, stage="active"):
        node = {
            "id": seed_id, "name": name, "domain": domain,
            "score": score, "stage": stage,
            "size": max(10, score * 5)  # Visual size based on score
        }
        self.data["nodes"].append(node)
        self._save()
        return node
    
    def add_relation(self, from_id, to_id, relation_type, strength):
        """relation_type: derives_from, competes_with, synergy, conflicts"""
        edge = {
            "from": from_id, "to": to_id,
            "type": relation_type, "strength": strength
        }
        self.data["edges"].append(edge)
        self._save()
        return edge
    
    def detect_clusters(self):
        """简单连通分量检测"""
        if not self.data["nodes"]:
            return []
        
        node_ids = [n["id"] for n in self.data["nodes"]]
        adjacency = {n: set() for n in node_ids}
        for e in self.data["edges"]:
            if e["from"] in adjacency and e["to"] in adjacency:
                adjacency[e["from"]].add(e["to"])
                adjacency[e["to"]].add(e["from"])
        
        visited = set()
        clusters = []
        
        for node in node_ids:
            if node not in visited:
                cluster = []
                stack = [node]
                while stack:
                    n = stack.pop()
                    if n not in visited:
                        visited.add(n)
                        cluster.append(n)
                        stack.extend(adjacency[n] - visited)
                clusters.append(cluster)
        
        self.data["clusters"] = [{"id": f"C-{i}", "members": c, "size": len(c)} for i, c in enumerate(clusters)]
        self._save()
        return self.data["clusters"]
    
    def get_stats(self):
        domains = {}
        for n in self.data["nodes"]:
            d = n["domain"]
            domains[d] = domains.get(d, 0) + 1
        
        return {
            "total_nodes": len(self.data["nodes"]),
            "total_edges": len(self.data["edges"]),
            "clusters": len(self.data["clusters"]),
            "domains": domains,
            "density": round(len(self.data["edges"]) / max(len(self.data["nodes"]) * (len(self.data["nodes"])-1) / 2, 1), 2)
        }


def main():
    graph = SeedGraph()
    
    seeds = [
        ("S-001", "四流合一清算", "finance", 8.5),
        ("S-002", "SiC外延片路由", "semiconductor", 7.0),
        ("S-003", "DRG医疗清算", "medical", 6.2),
        ("S-004", "碳纤维DB", "materials", 7.5),
        ("S-005", "智能建筑OS", "robotics", 6.8),
        ("S-006", "LUX经济体", "ai", 7.8),
        ("S-007", "信任网络", "ai", 7.2),
        ("S-008", "预测引擎", "ai", 7.0),
    ]
    
    for sid, name, domain, score in seeds:
        graph.add_seed_node(sid, name, domain, score)
    
    relations = [
        ("S-001", "S-003", "synergy", 0.8),
        ("S-001", "S-006", "derives_from", 0.7),
        ("S-002", "S-004", "synergy", 0.6),
        ("S-003", "S-001", "competes_with", 0.4),
        ("S-005", "S-004", "synergy", 0.5),
        ("S-006", "S-007", "derives_from", 0.9),
        ("S-007", "S-008", "synergy", 0.7),
    ]
    
    for f, t, rtype, strength in relations:
        graph.add_relation(f, t, rtype, strength)
    
    clusters = graph.detect_clusters()
    stats = graph.get_stats()
    
    print("=== Seed Graph v1.0 ===")
    print(f"  {stats['total_nodes']} nodes | {stats['total_edges']} edges | "
          f"density={stats['density']} | {stats['clusters']} clusters")
    print(f"  Domains: {stats['domains']}")
    for cl in clusters:
        print(f"  Cluster {cl['id']}: {cl['members']}")

if __name__ == "__main__":
    main()
