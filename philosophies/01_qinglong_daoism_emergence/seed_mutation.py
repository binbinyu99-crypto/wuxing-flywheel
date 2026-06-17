# -*- coding: utf-8 -*-
"""
Seed Mutation Engine v1.0
青龙·种子飞轮 — 种子变异与进化

核心: 种子不只是"发现"，还可以"变异"
- 交叉: 两个领域的种子组合产生新种子
- 变异: 随机扰动产生意外方向
- 选择: 残差反馈驱动优胜劣汰
"""
import json, os, random, hashlib
from datetime import datetime

class SeedMutation:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "seed_mutations.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"mutations": [], "crossovers": [], "meta": {"version": "1.0"}}
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def crossover(self, seed_a, seed_b):
        """Cross two seeds from different domains"""
        new_seed = {
            "id": f"cross_{hashlib.md5(f'{seed_a[\"domain\"]}_{seed_b[\"domain\"]}_{random.random()}'.encode()).hexdigest()[:8]}",
            "parents": [seed_a.get("id", "unknown"), seed_b.get("id", "unknown")],
            "domain": f"{seed_a['domain']}+{seed_b['domain']}",
            "name": f"{seed_a['domain']}\u00D7{seed_b['domain']} crossover",
            "potential_value": (seed_a.get("potential_value", 5) + seed_b.get("potential_value", 5)) * 0.7,
            "novelty": min(10, (seed_a.get("potential_value", 5) + seed_b.get("potential_value", 5)) * 0.4),
            "generation": max(seed_a.get("generation", 0), seed_b.get("generation", 0)) + 1,
            "created": datetime.now().isoformat(),
        }
        self.data["crossovers"].append(new_seed)
        self._save()
        return new_seed
    
    def mutate(self, seed, mutation_strength=0.3):
        """Mutate a seed with random perturbation"""
        perturbation = random.uniform(-mutation_strength, mutation_strength)
        mutated = {
            "id": f"mut_{hashlib.md5(f'{seed.get(\"id\", \"\")}_{random.random()}'.encode()).hexdigest()[:8]}",
            "parent": seed.get("id", "unknown"),
            "domain": seed["domain"],
            "name": f"{seed.get('name', seed['domain'])} (mutated)",
            "potential_value": max(0, min(10, seed.get("potential_value", 5) + perturbation * 10)),
            "novelty": min(10, seed.get("novelty", 5) + abs(perturbation) * 5),
            "generation": seed.get("generation", 0) + 1,
            "mutation_strength": round(perturbation, 3),
            "created": datetime.now().isoformat(),
        }
        self.data["mutations"].append(mutated)
        self._save()
        return mutated
    
    def evolve_generation(self, seeds, crossover_rate=0.3, mutation_rate=0.2):
        """Evolve a generation of seeds"""
        new_gen = []
        
        # Crossovers
        n_cross = max(1, int(len(seeds) * crossover_rate))
        for _ in range(n_cross):
            if len(seeds) >= 2:
                a, b = random.sample(seeds, 2)
                new_gen.append(self.crossover(a, b))
        
        # Mutations
        n_mut = max(1, int(len(seeds) * mutation_rate))
        for _ in range(n_mut):
            s = random.choice(seeds)
            new_gen.append(self.mutate(s))
        
        return new_gen
    
    def get_stats(self):
        return {
            "total_crossovers": len(self.data["crossovers"]),
            "total_mutations": len(self.data["mutations"]),
            "unique_cross_domains": len(set(c["domain"] for c in self.data["crossovers"])),
            "max_generation": max(
                [c.get("generation", 0) for c in self.data["crossovers"]] +
                [m.get("generation", 0) for m in self.data["mutations"]] + [0]
            ),
        }


def main():
    engine = SeedMutation()
    
    # Base seeds
    seeds = [
        {"id": "s1", "domain": "finance", "potential_value": 8, "generation": 0},
        {"id": "s2", "domain": "materials", "potential_value": 7, "generation": 0},
        {"id": "s3", "domain": "medical", "potential_value": 7, "generation": 0},
        {"id": "s4", "domain": "semiconductor", "potential_value": 6, "generation": 0},
        {"id": "s5", "domain": "robot", "potential_value": 5, "generation": 0},
        {"id": "s6", "domain": "energy", "potential_value": 6, "generation": 0},
        {"id": "s7", "domain": "building", "potential_value": 4, "generation": 0},
        {"id": "s8", "domain": "ai", "potential_value": 9, "generation": 0},
    ]
    
    # Evolve 3 generations
    current = seeds
    for gen in range(3):
        new = engine.evolve_generation(current)
        current = current + new
        print(f"Gen {gen+1}: {len(new)} new seeds ({len(current)} total)")
    
    stats = engine.get_stats()
    print(f"\n=== Seed Mutation Engine v1.0 ===")
    print(f"Crossovers: {stats['total_crossovers']}, Mutations: {stats['total_mutations']}")
    print(f"Unique Cross-Domains: {stats['unique_cross_domains']}, Max Gen: {stats['max_generation']}")

if __name__ == "__main__":
    main()
