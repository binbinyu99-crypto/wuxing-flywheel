# -*- coding: utf-8 -*-
"""
Knowledge Graph Builder v1.0
玄武·认知飞轮 — 知识图谱构建

从残差、种子、任务结果中构建知识图谱:
- 实体提取 (领域、公司、技术、材料)
- 关系发现 (供应链、竞争、协同)
- 图谱存储 (JSON邻接表)
"""
import json, os, hashlib
from datetime import datetime

class KnowledgeGraph:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "knowledge_graph.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"entities": {}, "relations": [], "meta": {"version": "1.0"}}
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def add_entity(self, name, entity_type, properties=None):
        eid = hashlib.md5(f"{name}_{entity_type}".encode()).hexdigest()[:10]
        if eid not in self.data["entities"]:
            self.data["entities"][eid] = {
                "name": name,
                "type": entity_type,
                "properties": properties or {},
                "created": datetime.now().isoformat(),
                "connections": 0,
            }
            self._save()
        return eid
    
    def add_relation(self, entity_a, entity_b, relation_type, weight=1.0):
        rel = {
            "source": entity_a,
            "target": entity_b,
            "type": relation_type,
            "weight": weight,
            "created": datetime.now().isoformat(),
        }
        self.data["relations"].append(rel)
        for eid in [entity_a, entity_b]:
            if eid in self.data["entities"]:
                self.data["entities"][eid]["connections"] += 1
        self._save()
        return rel
    
    def query_neighbors(self, entity_id, relation_type=None):
        neighbors = []
        for rel in self.data["relations"]:
            if rel["source"] == entity_id or rel["target"] == entity_id:
                if relation_type and rel["type"] != relation_type:
                    continue
                other = rel["target"] if rel["source"] == entity_id else rel["source"]
                if other in self.data["entities"]:
                    neighbors.append({
                        "id": other,
                        "name": self.data["entities"][other]["name"],
                        "relation": rel["type"],
                        "weight": rel["weight"],
                    })
        return neighbors
    
    def get_stats(self):
        return {
            "entities": len(self.data["entities"]),
            "relations": len(self.data["relations"]),
            "types": list(set(e["type"] for e in self.data["entities"].values())),
            "most_connected": sorted(
                [(eid, e["name"], e["connections"]) for eid, e in self.data["entities"].items()],
                key=lambda x: x[2], reverse=True
            )[:5],
        }


def main():
    kg = KnowledgeGraph()
    
    # Build SkyCetus knowledge graph
    # Domains
    d1 = kg.add_entity("\u5238\u5546\u6e05\u7b97", "domain", {"priority": "P0", "market_size": "300\u4ebf"})
    d2 = kg.add_entity("\u6750\u6599\u79d1\u5b66", "domain", {"priority": "P1", "materials_count": 41})
    d3 = kg.add_entity("\u533b\u7597AI", "domain", {"priority": "P1", "share": "25%"})
    d4 = kg.add_entity("\u534a\u5bfc\u4f53", "domain", {"priority": "P2"})
    d5 = kg.add_entity("\u667a\u80fd\u5efa\u7b51", "domain", {"priority": "P2"})
    
    # Technologies
    t1 = kg.add_entity("\u56db\u6d41\u5408\u4e00", "technology", {"engine": "four_flow_engine_v2.py"})
    t2 = kg.add_entity("\u6b8b\u5dee\u63d0\u53d6", "technology", {"engine": "cognitive-residual-extractor-v2.py"})
    t3 = kg.add_entity("\u591a\u6a21\u578b\u8def\u7531", "technology", {"cost_saving": "87.5%"})
    t4 = kg.add_entity("\u4fe1\u4efb\u8bc4\u5206", "technology", {"engine": "trust_scoring_engine.py"})
    t5 = kg.add_entity("LUX\u4ef7\u503c\u7cfb\u7edf", "technology", {"engine": "value_exchange.py"})
    
    # Companies
    c1 = kg.add_entity("\u6052\u751f\u7535\u5b50", "company", {"market_share": "52%", "product": "UF3.0"})
    c2 = kg.add_entity("\u91d1\u8bc1\u80a1\u4efd", "company", {"market_share": "33%", "product": "FS2.5"})
    c3 = kg.add_entity("\u534e\u6da6\u5fae", "company", {"domain": "semiconductor"})
    c4 = kg.add_entity("SiC/GaN", "material", {"growth_rate": "15%+"})
    c5 = kg.add_entity("\u78f3\u5316\u94df", "material", {"substitution": "<20%"})
    
    # Relations
    kg.add_relation(t1, d1, "serves", 0.9)
    kg.add_relation(t1, d3, "applicable", 0.7)
    kg.add_relation(t2, d2, "analyzes", 0.8)
    kg.add_relation(t3, d1, "optimizes", 0.9)
    kg.add_relation(t4, d1, "evaluates", 0.6)
    kg.add_relation(c1, d1, "dominates", 0.9)
    kg.add_relation(c2, d1, "competes", 0.8)
    kg.add_relation(c3, d4, "leads", 0.7)
    kg.add_relation(c4, d4, "core_material", 0.9)
    kg.add_relation(c5, d2, "strategic", 0.95)
    kg.add_relation(d1, d3, "cross_domain", 0.6)
    kg.add_relation(t5, t4, "integrates", 0.8)
    
    stats = kg.get_stats()
    print("=== Knowledge Graph v1.0 ===")
    print(f"Entities: {stats['entities']}, Relations: {stats['relations']}")
    print(f"Types: {stats['types']}")
    print(f"Most connected:")
    for eid, name, conns in stats["most_connected"]:
        print(f"  {name}: {conns} connections")
    
    # Query example
    neighbors = kg.query_neighbors(d1)
    print(f"\n\u5238\u5546\u6e05\u7b97 neighbors:")
    for n in neighbors:
        print(f"  -> {n['name']} ({n['relation']}, weight={n['weight']})")

if __name__ == "__main__":
    main()
