# -*- coding: utf-8 -*-
"""
Residual Aggregator v1.0
玄武·认知飞轮 — 残差聚合与趋势分析

功能:
- 从所有引擎收集残差数据
- 聚合分析: 哪些领域残差最大(=最需要探索)
- 趋势: 残差是在收敛还是发散
- 输出: 推荐青龙下一轮探索方向
"""
import json, os
from datetime import datetime
from collections import defaultdict

class ResidualAggregator:
    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(__file__)
        self.agg_path = os.path.join(self.base_dir, "residual_aggregation.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.agg_path):
            with open(self.agg_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"entries": [], "domain_stats": {}, "meta": {"version": "1.0"}}
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.agg_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def ingest(self, domain, source, residual_type, strength, description=""):
        """Ingest a residual from any engine"""
        entry = {
            "domain": domain,
            "source": source,
            "type": residual_type,  # knowledge_gap, optimization, anomaly, discovery
            "strength": strength,  # 0-10
            "description": description,
            "timestamp": datetime.now().isoformat(),
        }
        self.data["entries"].append(entry)
        self._update_stats()
        self._save()
        return entry
    
    def _update_stats(self):
        """Update domain-level statistics"""
        domain_data = defaultdict(lambda: {"count": 0, "total_strength": 0, "types": defaultdict(int)})
        for entry in self.data["entries"]:
            d = entry["domain"]
            domain_data[d]["count"] += 1
            domain_data[d]["total_strength"] += entry["strength"]
            domain_data[d]["types"][entry["type"]] += 1
        
        self.data["domain_stats"] = {}
        for domain, stats in domain_data.items():
            avg = stats["total_strength"] / max(stats["count"], 1)
            self.data["domain_stats"][domain] = {
                "count": stats["count"],
                "avg_strength": round(avg, 2),
                "total_strength": round(stats["total_strength"], 2),
                "types": dict(stats["types"]),
            }
    
    def get_exploration_priority(self):
        """Recommend next exploration priorities for 青龙"""
        priorities = []
        for domain, stats in self.data["domain_stats"].items():
            # High residual = high exploration value
            score = stats["avg_strength"] * 0.6 + (stats.get("types", {}).get("knowledge_gap", 0) * 2)
            priorities.append({
                "domain": domain,
                "score": round(score, 2),
                "avg_residual": stats["avg_strength"],
                "knowledge_gaps": stats.get("types", {}).get("knowledge_gap", 0),
            })
        priorities.sort(key=lambda x: x["score"], reverse=True)
        return priorities
    
    def get_summary(self):
        total_entries = len(self.data["entries"])
        total_domains = len(self.data["domain_stats"])
        avg_strength = sum(e["strength"] for e in self.data["entries"]) / max(total_entries, 1)
        return {
            "total_residuals": total_entries,
            "domains": total_domains,
            "avg_strength": round(avg_strength, 2),
            "top_domain": max(self.data["domain_stats"].items(), key=lambda x: x[1]["avg_strength"])[0] if self.data["domain_stats"] else None,
        }


def main():
    agg = ResidualAggregator()
    
    # Ingest residuals from various engines
    agg.ingest("finance", "four_flow_engine", "knowledge_gap", 7.5, "\u6e05\u7b97\u89c4\u5219\u590d\u6742\u5ea6\u8d85\u51fa\u6a21\u578b\u8986\u76d6")
    agg.ingest("finance", "trust_scoring", "optimization", 4.2, "\u4fe1\u4efb\u8bc4\u5206\u7b97\u6cd5\u5f85\u4f18\u5316")
    agg.ingest("materials", "residual_extractor", "discovery", 8.1, "\u65b0\u578b\u56fa\u6001\u7535\u89e3\u8d28\u53d1\u73b0")
    agg.ingest("materials", "knowledge_graph", "knowledge_gap", 6.3, "\u4ea7\u4e1a\u94fe\u4e0a\u6e38\u6570\u636e\u7f3a\u5931")
    agg.ingest("medical", "four_flow_engine", "knowledge_gap", 8.8, "\u533b\u4fdd\u6e05\u7b97\u89c4\u5219\u672a\u5efa\u6a21")
    agg.ingest("semiconductor", "baihu_agents", "anomaly", 5.5, "\u82af\u7247\u4ef7\u683c\u5f02\u5e38\u6ce2\u52a8")
    agg.ingest("robot", "seed_incubator", "knowledge_gap", 7.0, "\u673a\u5668\u4eba\u63a7\u5236\u7b97\u6cd5\u7f3a\u5931")
    agg.ingest("energy", "knowledge_graph", "discovery", 6.8, "\u6c22\u80fd\u50a8\u5b58\u65b0\u8def\u5f84")
    agg.ingest("building", "seed_incubator", "optimization", 3.5, "\u5efa\u7b51\u68c0\u6d4b\u6d41\u7a0b\u53ef\u4f18\u5316")
    agg.ingest("finance", "baihu_agents", "anomaly", 6.0, "OTC\u884d\u751f\u54c1\u5bf9\u51b2\u7b56\u7565\u5f02\u5e38")
    
    summary = agg.get_summary()
    print("=== Residual Aggregator v1.0 ===")
    print(f"Total: {summary['total_residuals']} residuals across {summary['domains']} domains")
    print(f"Avg Strength: {summary['avg_strength']}, Top Domain: {summary['top_domain']}")
    
    print("\nExploration Priorities (for \u9752\u9f99):")
    for p in agg.get_exploration_priority():
        print(f"  {p['domain']:15s} score={p['score']:5.1f} (avg_res={p['avg_residual']}, gaps={p['knowledge_gaps']})")

if __name__ == "__main__":
    main()
