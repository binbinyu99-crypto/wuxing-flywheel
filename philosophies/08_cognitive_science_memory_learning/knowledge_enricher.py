# -*- coding: utf-8 -*-
"""
knowledge_enricher.py v1.0.0 — Knowledge Base Enrichment
===========================================================
Enriches the materials knowledge base with structured data
from pipeline analyses. Tracks S/A/B/C tier materials.

Tiers:
  S: Convergence score >= 6.0 (e.g., CFRP 6.59, HEA 5.98, SiC 5.93)
  A: 4.0 <= score < 6.0
  B: 2.0 <= score < 4.0
  C: score < 2.0

Decision: Robin 2026-05-02
"""

import json, time
from typing import Dict, List

VERSION = "1.0.0"

# Known S-tier materials from previous analysis
MATERIALS_DB = {
    "CFRP": {
        "name_cn": "碳纤维复合材料",
        "convergence": 6.59,
        "tier": "S",
        "domestic_sub": 0.65,
        "key_apps": ["aerospace", "automotive", "wind energy"],
        "top_players": ["Toray", "Hexcel", "光威复材", "中复神鹰"],
    },
    "HEA": {
        "name_cn": "高熵合金",
        "convergence": 5.98,
        "tier": "S",
        "domestic_sub": 0.40,
        "key_apps": ["nuclear", "aerospace", "extreme environments"],
        "top_players": ["Various research labs"],
    },
    "SiC": {
        "name_cn": "碳化硅",
        "convergence": 5.93,
        "tier": "S",
        "domestic_sub": 0.55,
        "key_apps": ["power electronics", "EV", "5G", "solar"],
        "top_players": ["Wolfspeed", "STMicro", "三安光电", "天科合达"],
    },
    "GaN": {
        "name_cn": "氮化镓",
        "convergence": 5.21,
        "tier": "A",
        "domestic_sub": 0.45,
        "key_apps": ["5G RF", "fast charging", "radar"],
        "top_players": ["Infineon", "Navitas", "英诺赛科"],
    },
    "InP": {
        "name_cn": "磷化铟",
        "convergence": 4.82,
        "tier": "A",
        "domestic_sub": 0.20,
        "key_apps": ["optical comm", "data centers", "sensing"],
        "top_players": ["II-VI", "Lumentum", "云岭光电"],
    },
}


class KnowledgeEnricher:
    """Manages materials knowledge base."""
    
    def __init__(self):
        self.db = dict(MATERIALS_DB)
        self._enrichments = []
    
    def add_material(self, symbol: str, data: Dict):
        self.db[symbol] = data
        self._enrichments.append({
            "action": "add",
            "symbol": symbol,
            "timestamp": time.time(),
        })
    
    def update_analysis(self, symbol: str, analysis: Dict):
        if symbol in self.db:
            self.db[symbol]["latest_analysis"] = analysis
            self._enrichments.append({
                "action": "update",
                "symbol": symbol,
                "timestamp": time.time(),
            })
    
    def get_by_tier(self, tier: str) -> List[Dict]:
        return [{"symbol": k, **v} for k, v in self.db.items() if v.get("tier") == tier]
    
    def get_by_app(self, application: str) -> List[Dict]:
        results = []
        for k, v in self.db.items():
            if application in v.get("key_apps", []):
                results.append({"symbol": k, **v})
        return results
    
    def ranking(self) -> List[Dict]:
        items = [{"symbol": k, **v} for k, v in self.db.items()]
        items.sort(key=lambda x: -x.get("convergence", 0))
        return items
    
    def domestic_substitution_gaps(self) -> List[Dict]:
        gaps = []
        for k, v in self.db.items():
            sub = v.get("domestic_sub", 1.0)
            if sub < 0.5:
                gaps.append({
                    "symbol": k,
                    "name_cn": v.get("name_cn", ""),
                    "domestic_sub": sub,
                    "gap": round(1.0 - sub, 2),
                })
        gaps.sort(key=lambda x: x["gap"], reverse=True)
        return gaps
    
    def stats(self) -> Dict:
        tiers = {}
        for v in self.db.values():
            t = v.get("tier", "?")
            tiers[t] = tiers.get(t, 0) + 1
        return {
            "total_materials": len(self.db),
            "by_tier": tiers,
            "enrichments": len(self._enrichments),
        }


def self_test():
    print(f"knowledge_enricher.py v{VERSION}")
    
    ke = KnowledgeEnricher()
    
    s_tier = ke.get_by_tier("S")
    assert len(s_tier) == 3  # CFRP, HEA, SiC
    print("  s_tier: PASS")
    
    ranking = ke.ranking()
    assert ranking[0]["symbol"] == "CFRP"
    print("  ranking: PASS")
    
    gaps = ke.domestic_substitution_gaps()
    assert any(g["symbol"] == "InP" for g in gaps)
    print("  gaps: PASS")
    
    ev = ke.get_by_app("EV")
    assert any(m["symbol"] == "SiC" for m in ev)
    print("  by_app: PASS")
    
    print("  ALL PASS")
    return True


if __name__ == "__main__":
    self_test()
