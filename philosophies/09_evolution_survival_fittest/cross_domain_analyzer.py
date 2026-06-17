# -*- coding: utf-8 -*-
"""
Cross-Domain Analyzer v1.0
玄武·认知飞轮 — 跨域关联发现

核心: 发现不同领域之间的隐藏关联
- 技术迁移: 一个领域的技术可用于另一个领域
- 供应链交叉: 共享供应商/原材料
- 方法论复用: 算法/框架可跨域应用
"""
import json, os
from datetime import datetime
from collections import defaultdict

class CrossDomainAnalyzer:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "cross_domain.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"links": [], "patterns": [], "meta": {"version": "1.0"}}
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def discover_link(self, domain_a, domain_b, link_type, description, strength=0.5):
        """Discover a cross-domain link"""
        link = {
            "domains": sorted([domain_a, domain_b]),
            "type": link_type,
            "description": description,
            "strength": strength,
            "discovered": datetime.now().isoformat(),
            "validated": False,
        }
        self.data["links"].append(link)
        self._save()
        return link
    
    def find_patterns(self):
        """Find recurring cross-domain patterns"""
        pair_counts = defaultdict(int)
        pair_types = defaultdict(list)
        for link in self.data["links"]:
            key = tuple(link["domains"])
            pair_counts[key] += 1
            pair_types[key].append(link["type"])
        
        patterns = []
        for pair, count in pair_counts.items():
            if count >= 1:
                patterns.append({
                    "domains": list(pair),
                    "link_count": count,
                    "types": list(set(pair_types[pair])),
                    "avg_strength": sum(l["strength"] for l in self.data["links"] if tuple(sorted(l["domains"])) == pair) / count,
                })
        patterns.sort(key=lambda x: x["avg_strength"] * x["link_count"], reverse=True)
        self.data["patterns"] = patterns
        self._save()
        return patterns
    
    def get_domain_connectivity(self):
        """Get how connected each domain is to others"""
        connectivity = defaultdict(lambda: {"connections": 0, "linked_domains": set(), "avg_strength": 0, "total_strength": 0})
        for link in self.data["links"]:
            for d in link["domains"]:
                connectivity[d]["connections"] += 1
                connectivity[d]["total_strength"] += link["strength"]
                other = [x for x in link["domains"] if x != d]
                if other:
                    connectivity[d]["linked_domains"].add(other[0])
        
        result = {}
        for d, stats in connectivity.items():
            result[d] = {
                "connections": stats["connections"],
                "linked_domains": len(stats["linked_domains"]),
                "avg_strength": round(stats["total_strength"] / max(stats["connections"], 1), 2),
            }
        return result


def main():
    analyzer = CrossDomainAnalyzer()
    
    # Discover cross-domain links
    analyzer.discover_link("finance", "medical", "tech_transfer",
        "\u56db\u6d41\u5408\u4e00\u5f15\u64ce\u53ef\u590d\u7528: \u5238\u5546\u6e05\u7b97\u56db\u6d41 \u2192 \u533b\u4fdd\u6e05\u7b97\u56db\u6d41", 0.85)
    analyzer.discover_link("finance", "medical", "method_reuse",
        "\u98ce\u63a7\u6a21\u578b\u53ef\u8fc1\u79fb: \u91d1\u878d\u98ce\u63a7 \u2192 \u533b\u7597\u8d28\u63a7", 0.7)
    analyzer.discover_link("materials", "semiconductor", "supply_chain",
        "\u5171\u4eab\u539f\u6750\u6599: SiC/GaN\u540c\u65f6\u670d\u52a1\u4e24\u4e2a\u9886\u57df", 0.9)
    analyzer.discover_link("materials", "energy", "tech_transfer",
        "\u56fa\u6001\u7535\u89e3\u8d28\u7814\u7a76\u53ef\u5e94\u7528\u4e8e\u50a8\u80fd\u548c\u534a\u5bfc\u4f53", 0.75)
    analyzer.discover_link("robot", "building", "tech_transfer",
        "\u5efa\u7b51\u68c0\u6d4b\u673a\u5668\u4eba = \u673a\u5668\u4eba+\u5efa\u7b51\u4ea4\u53c9", 0.8)
    analyzer.discover_link("robot", "semiconductor", "supply_chain",
        "\u673a\u5668\u4eba\u82af\u7247\u9700\u6c42: \u63a7\u5236\u82af\u7247+\u89c6\u89c9\u82af\u7247+\u901a\u4fe1\u82af\u7247", 0.65)
    analyzer.discover_link("ai", "finance", "method_reuse",
        "\u591a\u6a21\u578b\u8def\u7531\u6838\u5fc3\u6280\u672f\u76f4\u63a5\u670d\u52a1\u91d1\u878d\u573a\u666f", 0.95)
    analyzer.discover_link("ai", "materials", "method_reuse",
        "\u6b8b\u5dee\u5b66\u4e60\u53ef\u7528\u4e8e\u6750\u6599\u6027\u80fd\u9884\u6d4b", 0.7)
    analyzer.discover_link("energy", "building", "supply_chain",
        "\u667a\u80fd\u5efa\u7b51\u80fd\u6e90\u7ba1\u7406\u7cfb\u7edf", 0.6)
    analyzer.discover_link("medical", "robot", "tech_transfer",
        "\u624b\u672f\u673a\u5668\u4eba + \u533b\u7597AI\u4ea4\u53c9", 0.55)
    
    patterns = analyzer.find_patterns()
    print("=== Cross-Domain Analyzer v1.0 ===")
    print(f"Links: {len(analyzer.data['links'])}, Patterns: {len(patterns)}")
    print("\nTop cross-domain patterns:")
    for p in patterns[:5]:
        print(f"  {p['domains'][0]:12s} <-> {p['domains'][1]:12s} "
              f"links={p['link_count']} strength={p['avg_strength']:.2f} types={p['types']}")
    
    conn = analyzer.get_domain_connectivity()
    print("\nDomain connectivity:")
    for d, stats in sorted(conn.items(), key=lambda x: x[1]["connections"], reverse=True):
        print(f"  {d:15s} connections={stats['connections']} linked={stats['linked_domains']} avg={stats['avg_strength']}")

if __name__ == "__main__":
    main()
