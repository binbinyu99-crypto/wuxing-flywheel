# -*- coding: utf-8 -*-
"""
feedback_learner.py v1.0.0 — Feedback Ledger + Path Learning
==============================================================
Tracks pipeline execution paths and learns which strategies
produce the best results for different domains.

Features:
  - Path recording (which phases, models, configs led to what scores)
  - Pattern extraction (what works for finance vs tech vs materials)
  - Adaptive recommendations for future runs
  - PG persistence for cross-session learning

Decision: Robin 2026-05-02
"""

import json, time, hashlib
from typing import Dict, List, Optional

VERSION = "1.0.0"


class PathRecord:
    """Records a single pipeline execution path."""
    def __init__(self, topic, domain, config):
        self.topic = topic
        self.domain = domain
        self.config = config
        self.phases = []
        self.final_score = 0.0
        self.verdict = ""
        self.rounds = 0
        self.elapsed = 0.0
        self.timestamp = time.time()
    
    def add_phase(self, element, model, elapsed_s, output_size):
        self.phases.append({
            "element": element,
            "model": model,
            "elapsed_s": elapsed_s,
            "output_size": output_size,
        })
    
    def finalize(self, score, verdict, rounds, elapsed):
        self.final_score = score
        self.verdict = verdict
        self.rounds = rounds
        self.elapsed = elapsed
    
    def to_dict(self):
        return {
            "topic": self.topic, "domain": self.domain,
            "config": self.config, "phases": self.phases,
            "final_score": self.final_score, "verdict": self.verdict,
            "rounds": self.rounds, "elapsed": self.elapsed,
            "timestamp": self.timestamp,
        }


class FeedbackLedger:
    """Stores and queries execution feedback for learning."""
    
    def __init__(self, pg_storage=None):
        self.pg = pg_storage
        self._records = []
    
    def record(self, path_record: PathRecord):
        self._records.append(path_record.to_dict())
    
    def get_best_config(self, domain: str) -> Optional[Dict]:
        """Find the best-performing config for a domain."""
        domain_records = [r for r in self._records if r["domain"] == domain]
        if not domain_records:
            return None
        best = max(domain_records, key=lambda r: r["final_score"])
        return best["config"]
    
    def get_avg_score(self, domain: str) -> float:
        domain_records = [r for r in self._records if r["domain"] == domain]
        if not domain_records:
            return 0.0
        return sum(r["final_score"] for r in domain_records) / len(domain_records)
    
    def get_model_performance(self) -> Dict:
        """Analyze which models perform best per phase."""
        model_scores = {}
        for record in self._records:
            for phase in record["phases"]:
                model = phase["model"]
                element = phase["element"]
                key = f"{element}:{model}"
                if key not in model_scores:
                    model_scores[key] = {"total": 0, "count": 0, "avg_elapsed": 0}
                model_scores[key]["total"] += record["final_score"]
                model_scores[key]["count"] += 1
                model_scores[key]["avg_elapsed"] += phase["elapsed_s"]
        
        for key in model_scores:
            n = model_scores[key]["count"]
            model_scores[key]["avg_score"] = round(model_scores[key]["total"] / n, 3)
            model_scores[key]["avg_elapsed"] = round(model_scores[key]["avg_elapsed"] / n, 1)
        
        return model_scores
    
    def recommend(self, domain: str) -> Dict:
        """Recommend config based on historical performance."""
        best_config = self.get_best_config(domain)
        avg = self.get_avg_score(domain)
        model_perf = self.get_model_performance()
        
        return {
            "domain": domain,
            "recommended_config": best_config,
            "avg_domain_score": avg,
            "model_insights": model_perf,
            "total_records": len(self._records),
        }
    
    def stats(self) -> Dict:
        domains = set(r["domain"] for r in self._records)
        return {
            "total_records": len(self._records),
            "domains": list(domains),
            "avg_score": sum(r["final_score"] for r in self._records) / max(len(self._records), 1),
        }


def self_test():
    print(f"feedback_learner.py v{VERSION}")
    
    ledger = FeedbackLedger()
    
    # Record a path
    path = PathRecord("SiC analysis", "materials", {"max_rounds": 2})
    path.add_phase("wood", "MiniMax", 8.5, 3200)
    path.add_phase("fire", "DeepSeek", 12.3, 5100)
    path.finalize(0.72, "PASS", 2, 45.3)
    ledger.record(path)
    
    path2 = PathRecord("Options pricing", "finance", {"max_rounds": 3})
    path2.add_phase("wood", "MiniMax", 7.2, 2800)
    path2.add_phase("fire", "DeepSeek", 15.1, 6200)
    path2.finalize(0.85, "PASS", 3, 78.5)
    ledger.record(path2)
    
    assert ledger.get_avg_score("finance") == 0.85
    print("  avg_score: PASS")
    
    rec = ledger.recommend("finance")
    assert rec["recommended_config"]["max_rounds"] == 3
    print("  recommend: PASS")
    
    perf = ledger.get_model_performance()
    assert len(perf) > 0
    print("  model_perf: PASS")
    
    print("  ALL PASS")
    return True


if __name__ == "__main__":
    self_test()
