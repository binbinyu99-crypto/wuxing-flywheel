# -*- coding: utf-8 -*-
"""
Domain Expander v1.0
青龙·种子飞轮 — 赛道拓展与种子繁殖

核心: 从已有种子的交叉点发现新赛道
- 分析种子间的隐藏关联
- 发现跨领域机会
- 生成新赛道种子
"""
import json, os
from datetime import datetime
from collections import defaultdict
import random

class DomainExpander:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "domain_expansion.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"domains": {}, "crossings": [], "new_seeds": [], "meta": {"version": "1.0"}}
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def register_domain(self, domain_id, name, maturity, seed_count, key_techs):
        self.data["domains"][domain_id] = {
            "name": name, "maturity": maturity, "seed_count": seed_count,
            "key_techs": key_techs, "created": datetime.now().isoformat(),
        }
        self._save()
    
    def find_crossings(self):
        """Find crossing points between domains"""
        domains = list(self.data["domains"].items())
        crossings = []
        
        for i in range(len(domains)):
            for j in range(i+1, len(domains)):
                d1_id, d1 = domains[i]
                d2_id, d2 = domains[j]
                
                # Find shared technologies
                shared = set(d1["key_techs"]) & set(d2["key_techs"])
                
                if shared:
                    synergy = len(shared) / max(len(set(d1["key_techs"]) | set(d2["key_techs"])), 1)
                    crossing = {
                        "domains": [d1_id, d2_id],
                        "domain_names": [d1["name"], d2["name"]],
                        "shared_techs": list(shared),
                        "synergy_score": round(synergy, 2),
                        "opportunity": self._gen_opportunity(d1["name"], d2["name"], list(shared)),
                    }
                    crossings.append(crossing)
        
        crossings.sort(key=lambda x: x["synergy_score"], reverse=True)
        self.data["crossings"] = crossings
        self._save()
        return crossings
    
    def _gen_opportunity(self, d1, d2, shared):
        templates = [
            f"{d1}+{d2}: {shared[0]}技术双向赋能",
            f"跨域应用: {d1}的{shared[0]}经验迁移到{d2}",
            f"融合赛道: {d1}×{d2}={shared[0]}驱动的新品类",
        ]
        return random.choice(templates)
    
    def expand_domains(self):
        """Generate new domain seeds from crossings"""
        new_seeds = []
        for crossing in self.data["crossings"]:
            if crossing["synergy_score"] >= 0.2:
                seed = {
                    "name": f"{crossing['domain_names'][0]}×{crossing['domain_names'][1]}",
                    "parent_domains": crossing["domains"],
                    "core_tech": crossing["shared_techs"][0] if crossing["shared_techs"] else "unknown",
                    "synergy": crossing["synergy_score"],
                    "opportunity": crossing["opportunity"],
                    "status": "seed",
                    "created": datetime.now().isoformat(),
                }
                new_seeds.append(seed)
        
        self.data["new_seeds"] = new_seeds
        self._save()
        return new_seeds


def main():
    engine = DomainExpander()
    
    engine.register_domain("finance", "\u91D1\u878D\u6E05\u7B97", 0.7, 45, 
        ["AI", "\u6570\u636E\u5206\u6790", "\u98CE\u63A7", "\u81EA\u52A8\u5316", "\u5408\u89C4"])
    engine.register_domain("materials", "\u524D\u6CBF\u6750\u6599", 0.5, 41,
        ["AI", "\u4EFF\u771F", "\u6570\u636E\u5206\u6790", "\u4F9B\u5E94\u94FE", "\u534A\u5BFC\u4F53"])
    engine.register_domain("medical", "\u533B\u7597AI", 0.3, 25,
        ["AI", "\u6570\u636E\u5206\u6790", "\u98CE\u63A7", "\u5408\u89C4", "\u9690\u79C1\u8BA1\u7B97"])
    engine.register_domain("semiconductor", "\u534A\u5BFC\u4F53", 0.6, 30,
        ["AI", "\u4EFF\u771F", "\u534A\u5BFC\u4F53", "\u4F9B\u5E94\u94FE", "\u81EA\u52A8\u5316"])
    engine.register_domain("robot", "\u673A\u5668\u4EBA", 0.2, 15,
        ["AI", "\u81EA\u52A8\u5316", "\u4EFF\u771F", "\u63A7\u5236\u7B97\u6CD5"])
    engine.register_domain("energy", "\u65B0\u80FD\u6E90", 0.3, 20,
        ["AI", "\u4F9B\u5E94\u94FE", "\u6570\u636E\u5206\u6790", "\u50A8\u80FD"])
    engine.register_domain("building", "\u667A\u80FD\u5EFA\u7B51", 0.2, 10,
        ["AI", "\u81EA\u52A8\u5316", "\u4EFF\u771F", "\u63A7\u5236\u7B97\u6CD5", "\u50A8\u80FD"])
    
    crossings = engine.find_crossings()
    print("=== Domain Expander v1.0 ===")
    print(f"Domains: {len(engine.data['domains'])}, Crossings: {len(crossings)}")
    
    for cr in crossings[:8]:
        print(f"  {cr['domain_names'][0]:6s} x {cr['domain_names'][1]:6s} = "
              f"synergy {cr['synergy_score']:.2f} | shared: {','.join(cr['shared_techs'][:3])}")
    
    new_seeds = engine.expand_domains()
    print(f"  New seeds generated: {len(new_seeds)}")
    for s in new_seeds[:5]:
        print(f"    {s['name']:20s} core={s['core_tech']} synergy={s['synergy']:.2f}")

if __name__ == "__main__":
    main()
