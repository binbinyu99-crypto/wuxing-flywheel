# -*- coding: utf-8 -*-
"""
Feedback Loop Engine v1.0
白虎·链接飞轮 — 反馈闭环

TEP核心机制: 没有feedback = 没有进化
- 实时反馈收集
- 延迟反馈处理
- 路径权重更新
- 地板值保护(任何路径最低5%)
"""
import json, os
from datetime import datetime

class FeedbackLoop:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "feedback_loop.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "feedbacks": [], "path_weights": {"A": 0.65, "B": 0.25, "C": 0.10},
            "ledger": [], "meta": {"version": "1.0", "floor": 0.05}
        }
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def record_feedback(self, task_id, path, executor, score, feedback_type="immediate"):
        """score: 0-10, feedback_type: immediate/delayed/external"""
        fb = {
            "id": f"FB-{len(self.data['feedbacks'])+1:04d}",
            "task_id": task_id, "path": path, "executor": executor,
            "score": score, "type": feedback_type,
            "timestamp": datetime.now().isoformat()
        }
        self.data["feedbacks"].append(fb)
        self._save()
        return fb
    
    def update_weights(self):
        """根据反馈更新路径权重"""
        path_scores = {"A": [], "B": [], "C": []}
        for fb in self.data["feedbacks"]:
            p = fb["path"]
            if p in path_scores:
                path_scores[p].append(fb["score"])
        
        if not any(path_scores.values()):
            return self.data["path_weights"]
        
        # Calculate average scores
        avg_scores = {}
        for p, scores in path_scores.items():
            if scores:
                avg_scores[p] = sum(scores) / len(scores)
            else:
                avg_scores[p] = 5  # Default neutral
        
        # Normalize to weights
        total = sum(avg_scores.values())
        if total > 0:
            new_weights = {p: s / total for p, s in avg_scores.items()}
        else:
            new_weights = self.data["path_weights"]
        
        # Apply floor (5% minimum)
        floor = self.data["meta"]["floor"]
        for p in new_weights:
            if new_weights[p] < floor:
                deficit = floor - new_weights[p]
                new_weights[p] = floor
                # Redistribute from strongest
                strongest = max(new_weights, key=new_weights.get)
                new_weights[strongest] -= deficit
        
        # Round
        new_weights = {p: round(w, 3) for p, w in new_weights.items()}
        
        # Record to ledger
        self.data["ledger"].append({
            "old_weights": dict(self.data["path_weights"]),
            "new_weights": dict(new_weights),
            "feedback_count": len(self.data["feedbacks"]),
            "timestamp": datetime.now().isoformat()
        })
        
        self.data["path_weights"] = new_weights
        self._save()
        return new_weights
    
    def get_stats(self):
        fbs = self.data["feedbacks"]
        if not fbs:
            return {"total": 0}
        
        by_path = {}
        for fb in fbs:
            p = fb["path"]
            if p not in by_path:
                by_path[p] = {"count": 0, "total_score": 0}
            by_path[p]["count"] += 1
            by_path[p]["total_score"] += fb["score"]
        
        for p, data in by_path.items():
            data["avg_score"] = round(data["total_score"] / data["count"], 1)
        
        return {
            "total_feedbacks": len(fbs),
            "by_path": by_path,
            "weights": self.data["path_weights"],
            "ledger_entries": len(self.data["ledger"])
        }


def main():
    engine = FeedbackLoop()
    
    feedbacks = [
        ("T-001", "A", "spark", 9, "immediate"),
        ("T-002", "A", "spark", 8, "immediate"),
        ("T-003", "B", "xiaoyuan", 7, "immediate"),
        ("T-004", "A", "spark", 9, "delayed"),
        ("T-005", "C", "etern", 6, "immediate"),
        ("T-006", "B", "lucas", 4, "immediate"),
        ("T-007", "A", "spark", 8, "external"),
        ("T-008", "C", "spark", 7, "immediate"),
        ("T-009", "B", "xiaoyuan", 6, "delayed"),
    ]
    
    print("=== Feedback Loop v1.0 ===")
    print(f"  Initial weights: {engine.data['path_weights']}")
    
    for tid, path, executor, score, ftype in feedbacks:
        fb = engine.record_feedback(tid, path, executor, score, ftype)
        print(f"  {fb['id']} path={path} executor={executor:10s} score={score}/10 [{ftype}]")
    
    new_weights = engine.update_weights()
    print(f"\n  Updated weights: {new_weights}")
    
    stats = engine.get_stats()
    print(f"  Total feedbacks: {stats['total_feedbacks']}")
    for p, data in stats["by_path"].items():
        print(f"    Path {p}: {data['count']} feedbacks, avg={data['avg_score']}/10")
    
    # Check floor protection
    print(f"\n  Floor protection: {engine.data['meta']['floor']:.0%} minimum per path")
    for p, w in new_weights.items():
        floor_ok = w >= engine.data["meta"]["floor"]
        print(f"    Path {p}: {w:.1%} {'OK' if floor_ok else 'FLOOR APPLIED'}")

if __name__ == "__main__":
    main()
