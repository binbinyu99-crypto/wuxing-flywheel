# -*- coding: utf-8 -*-
"""
Seed Competition Engine v1.0
青龙·种子飞轮 — 种子竞争

核心: 多种子竞争同一任务槽位
- 种子擂台赛(tournament)
- 适应度评分(fitness scoring)
- 淘汰与晋级(elimination)
- 保护弱种子(diversity floor 10%)
"""
import json, os, random
from datetime import datetime

class SeedCompetition:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "seed_competition.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"tournaments": [], "hall_of_fame": [], "eliminated": [], "meta": {"version": "1.0", "diversity_floor": 0.10}}
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def create_tournament(self, slot_id, slot_name, candidates):
        """candidates: list of {seed_id, name, domain, fitness}"""
        tournament = {
            "id": f"TOURN-{len(self.data['tournaments'])+1:03d}",
            "slot": slot_id, "slot_name": slot_name,
            "candidates": candidates, "rounds": [],
            "winner": None, "status": "active",
            "created": datetime.now().isoformat()
        }
        self.data["tournaments"].append(tournament)
        self._save()
        return tournament
    
    def run_round(self, tournament_id):
        tourn = next((t for t in self.data["tournaments"] if t["id"] == tournament_id), None)
        if not tourn or tourn["status"] != "active":
            return None
        
        candidates = [c for c in tourn["candidates"] if c.get("alive", True)]
        if len(candidates) <= 1:
            if candidates:
                tourn["winner"] = candidates[0]
                tourn["status"] = "completed"
                self.data["hall_of_fame"].append(candidates[0])
            self._save()
            return {"status": "completed", "winner": tourn["winner"]}
        
        # Pairwise competition
        random.shuffle(candidates)
        round_results = []
        survivors = []
        
        for i in range(0, len(candidates) - 1, 2):
            a, b = candidates[i], candidates[i+1]
            # Fitness + random noise (exploration)
            a_score = a["fitness"] + random.uniform(-1, 1)
            b_score = b["fitness"] + random.uniform(-1, 1)
            
            if a_score >= b_score:
                winner, loser = a, b
            else:
                winner, loser = b, a
            
            # Diversity floor: 10% chance loser survives anyway
            loser_survives = random.random() < self.data["meta"]["diversity_floor"]
            
            survivors.append(winner)
            if loser_survives:
                survivors.append(loser)
                round_results.append({"winner": winner["seed_id"], "loser": loser["seed_id"], "loser_saved": True})
            else:
                loser["alive"] = False
                self.data["eliminated"].append(loser)
                round_results.append({"winner": winner["seed_id"], "loser": loser["seed_id"], "loser_saved": False})
        
        # Odd one out gets a bye
        if len(candidates) % 2 == 1:
            survivors.append(candidates[-1])
        
        tourn["rounds"].append({"round": len(tourn["rounds"]) + 1, "results": round_results, "survivors": len(survivors)})
        self._save()
        return {"status": "round_complete", "survivors": len(survivors), "eliminated": len(candidates) - len(survivors)}
    
    def get_stats(self):
        completed = [t for t in self.data["tournaments"] if t["status"] == "completed"]
        return {
            "total_tournaments": len(self.data["tournaments"]),
            "completed": len(completed),
            "hall_of_fame": len(self.data["hall_of_fame"]),
            "total_eliminated": len(self.data["eliminated"])
        }


def main():
    engine = SeedCompetition()
    
    candidates = [
        {"seed_id": "S-101", "name": "四流合一v2", "domain": "finance", "fitness": 8.5, "alive": True},
        {"seed_id": "S-102", "name": "DRG智能清算", "domain": "medical", "fitness": 7.2, "alive": True},
        {"seed_id": "S-103", "name": "供应链AI路由", "domain": "semiconductor", "fitness": 7.8, "alive": True},
        {"seed_id": "S-104", "name": "碳纤维数据库", "domain": "materials", "fitness": 7.0, "alive": True},
        {"seed_id": "S-105", "name": "量子计算模拟", "domain": "ai", "fitness": 5.5, "alive": True},
        {"seed_id": "S-106", "name": "智能建筑控制", "domain": "robotics", "fitness": 6.8, "alive": True},
    ]
    
    tourn = engine.create_tournament("SLOT-01", "Q2核心产品", candidates)
    print(f"=== Seed Competition v1.0 ===")
    print(f"  Tournament {tourn['id']}: {tourn['slot_name']} ({len(candidates)} candidates)")
    
    for i in range(3):
        result = engine.run_round(tourn["id"])
        if not result:
            break
        print(f"  Round {i+1}: {result}")
        if result["status"] == "completed":
            print(f"  WINNER: {result['winner']['name']} (fitness={result['winner']['fitness']})")
            break
    
    stats = engine.get_stats()
    print(f"\n  Stats: {stats}")

if __name__ == "__main__":
    main()
