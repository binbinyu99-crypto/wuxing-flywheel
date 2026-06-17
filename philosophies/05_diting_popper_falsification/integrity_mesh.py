"""
IntegrityMesh — Six-Dimension Structural Quality Scoring
善良作为骨骼，不是门卫。移除它会让系统变弱，而不仅仅是变"不安全"。

V12.0 Production Module
"""

class IntegrityMesh:
    """Six-dimension integrity scoring for flywheel outputs.
    
    Each dimension represents a structural quality requirement.
    Low scores in any dimension indicate structural weakness —
    the analysis is less trustworthy, not just less "safe".
    """
    
    # Thresholds for weakness detection
    WEAKNESS_THRESHOLD = 0.4
    CRITICAL_THRESHOLD = 0.25
    
    # Dimension weights (sum = 1.0)
    WEIGHTS = {
        "logical_consistency": 0.20,
        "evidence_integrity": 0.20,
        "temporal_robustness": 0.15,
        "stakeholder_symmetry": 0.15,
        "counterfactual_survival": 0.15,
        "information_asymmetry": 0.15,
    }
    
    def compute_integrity_score(self, dim_scores: dict) -> float:
        """Compute weighted integrity score from dimension scores.
        
        Args:
            dim_scores: Dict mapping dimension names to scores [0, 1]
            
        Returns:
            Weighted integrity score [0, 1]
        """
        total = 0.0
        weight_sum = 0.0
        
        for dim, weight in self.WEIGHTS.items():
            score = dim_scores.get(dim, 0.5)  # default to neutral
            score = max(0.0, min(1.0, float(score)))
            total += score * weight
            weight_sum += weight
        
        return round(total / weight_sum if weight_sum > 0 else 0.5, 3)
    
    def detect_structural_weakness(self, dim_scores: dict) -> list:
        """Detect dimensions below threshold.
        
        Returns list of weakness dicts with type, dimension, score, description.
        """
        weaknesses = []
        
        descriptions = {
            "logical_consistency": "论证链存在逻辑断裂或自相矛盾",
            "evidence_integrity": "证据来源不充分或未经交叉验证",
            "temporal_robustness": "结论对时间窗口敏感，可能随条件变化失效",
            "stakeholder_symmetry": "分析偏向某一利益方，缺乏多方视角平衡",
            "counterfactual_survival": "结论在反事实推演下脆弱，替代路径未被充分考虑",
            "information_asymmetry": "分析可能利用信息不对称得出表面正确但实质误导的结论",
        }
        
        for dim, weight in self.WEIGHTS.items():
            score = dim_scores.get(dim, 0.5)
            score = max(0.0, min(1.0, float(score)))
            
            if score < self.CRITICAL_THRESHOLD:
                weaknesses.append({
                    "type": "critical",
                    "dimension": dim,
                    "score": round(score, 3),
                    "description": f"[严重] {descriptions.get(dim, dim)}",
                })
            elif score < self.WEAKNESS_THRESHOLD:
                weaknesses.append({
                    "type": "warning",
                    "dimension": dim,
                    "score": round(score, 3),
                    "description": f"[警告] {descriptions.get(dim, dim)}",
                })
        
        return weaknesses
    
    def format_integrity_report(self, dim_scores: dict) -> str:
        """Generate human-readable integrity report."""
        score = self.compute_integrity_score(dim_scores)
        weaknesses = self.detect_structural_weakness(dim_scores)
        
        lines = [f"完整性评分: {score:.3f}"]
        
        dim_labels = {
            "logical_consistency": "逻辑一致性",
            "evidence_integrity": "证据完整性",
            "temporal_robustness": "时间鲁棒性",
            "stakeholder_symmetry": "利益方对称性",
            "counterfactual_survival": "反事实存活率",
            "information_asymmetry": "信息对称性",
        }
        
        for dim, weight in self.WEIGHTS.items():
            s = dim_scores.get(dim, 0.5)
            label = dim_labels.get(dim, dim)
            bar = "█" * int(float(s) * 10)
            lines.append(f"  {label}: {bar} {s:.2f}")
        
        if weaknesses:
            lines.append(f"\n⚠ {len(weaknesses)} 个结构性弱点:")
            for w in weaknesses:
                lines.append(f"  {w['description']}")
        
        return "\n".join(lines)
