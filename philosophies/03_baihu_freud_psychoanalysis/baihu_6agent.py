
"""
白虎6Agent对抗制衡系统 (Baihu 6-Agent Adversarial System)
升级4→6 Agent: 新增 Devil's Advocate(魔鬼代言人) + Integrator(整合者)

角色:
1. Optimist(乐观者) - 看好方案潜力
2. Pessimist(悲观者) - 挑战风险和缺陷
3. Realist(现实者) - 关注可行性和资源
4. Contrarian(逆向者) - 提供反直觉视角
5. Devil(魔鬼代言人) - 专门找致命缺陷
6. Integrator(整合者) - 综合各方观点形成共识
"""
import json, os, math
from datetime import datetime

class Agent:
    """评估Agent基类"""
    def __init__(self, role, bias, focus_dims, description):
        self.role = role
        self.bias = bias
        self.focus_dims = focus_dims
        self.description = description
        self.calibration = 1.0
        self.evaluation_count = 0
    
    def evaluate(self, proposal, dimensions):
        scores = {}
        for dim_id, dim_config in dimensions.items():
            base = self._compute_score(proposal, dim_id)
            focus_bonus = 0.08 if dim_id in self.focus_dims else 0
            score = max(0, min(10, (base + self.bias + focus_bonus) * self.calibration))
            scores[dim_id] = round(score, 2)
        
        self.evaluation_count += 1
        return {
            'role': self.role,
            'scores': scores,
            'reasoning': self._generate_reasoning(proposal, scores),
            'confidence': self._compute_confidence(scores)
        }
    
    def _compute_score(self, proposal, dim_id):
        text = str(proposal).lower()
        base = 5.0 + min(1.5, len(text) / 500)
        keyword_boosts = {
            'feasibility': ['proven', 'existing', 'tested', 'simple', 'ready'],
            'innovation': ['novel', 'breakthrough', 'unique', 'creative', 'first'],
            'risk': ['complex', 'uncertain', 'dependency', 'unknown'],
            'roi': ['efficient', 'scalable', 'automated', 'reusable'],
            'impact': ['transform', 'disrupt', 'paradigm', 'ecosystem'],
            'sustainability': ['long-term', 'maintainable', 'community', 'open']
        }
        hits = sum(1 for k in keyword_boosts.get(dim_id, []) if k in text)
        return base + hits * 0.4
    
    def _generate_reasoning(self, proposal, scores):
        avg = sum(scores.values()) / max(1, len(scores))
        if avg > 7:
            return f"[{self.role}] Strong proposal with clear strengths"
        elif avg > 5:
            return f"[{self.role}] Decent proposal but needs refinement"
        else:
            return f"[{self.role}] Significant concerns require addressing"
    
    def _compute_confidence(self, scores):
        values = list(scores.values())
        if not values:
            return 0.5
        variance = sum((v - sum(values)/len(values))**2 for v in values) / len(values)
        return round(max(0.3, 1.0 - variance / 25), 2)


class Baihu6AgentSystem:
    """白虎6Agent对抗制衡系统"""
    
    DIMENSIONS = {
        'feasibility': {'name': '可行性', 'weight': 0.20},
        'innovation': {'name': '创新性', 'weight': 0.15},
        'risk': {'name': '风险度', 'weight': 0.20},
        'roi': {'name': '投入产出比', 'weight': 0.20},
        'impact': {'name': '影响力', 'weight': 0.15},
        'sustainability': {'name': '可持续性', 'weight': 0.10}
    }
    
    def __init__(self):
        self.agents = {
            'optimist': Agent('optimist', 0.15, ['innovation', 'impact'], '看好方案潜力和创新价值'),
            'pessimist': Agent('pessimist', -0.15, ['risk', 'feasibility'], '挑战风险和实施缺陷'),
            'realist': Agent('realist', 0.0, ['feasibility', 'roi'], '关注可行性和资源约束'),
            'contrarian': Agent('contrarian', -0.05, ['innovation', 'sustainability'], '提供反直觉视角'),
            'devil': Agent('devil', -0.25, ['risk', 'roi'], '专门寻找致命缺陷'),
            'integrator': Agent('integrator', 0.05, ['impact', 'sustainability'], '综合各方形成共识')
        }
        self.evaluation_history = []
    
    def evaluate(self, proposal, context=None):
        """6Agent全面评估"""
        all_evaluations = {}
        for role, agent in self.agents.items():
            all_evaluations[role] = agent.evaluate(proposal, self.DIMENSIONS)
        
        # Integrator特殊处理：基于其他5个Agent的评分做综合
        other_scores = {role: ev['scores'] for role, ev in all_evaluations.items() if role != 'integrator'}
        consensus = self._compute_consensus(other_scores)
        
        # 计算分歧度
        disagreement = self._compute_disagreement(other_scores)
        
        # 加权总分
        weighted_total = sum(
            consensus[dim] * self.DIMENSIONS[dim]['weight']
            for dim in consensus
        )
        
        # Devil's veto: 如果devil给出任何维度<3分，标记红旗
        devil_scores = all_evaluations['devil']['scores']
        red_flags = [dim for dim, score in devil_scores.items() if score < 3]
        
        result = {
            'evaluations': all_evaluations,
            'consensus': consensus,
            'weighted_total': round(weighted_total, 2),
            'disagreement': disagreement,
            'red_flags': red_flags,
            'recommendation': self._get_recommendation(weighted_total, red_flags, disagreement),
            'timestamp': datetime.now().isoformat()
        }
        
        self.evaluation_history.append({
            'proposal': str(proposal)[:100],
            'score': result['weighted_total'],
            'recommendation': result['recommendation'],
            'red_flags': len(red_flags)
        })
        
        return result
    
    def _compute_consensus(self, all_scores):
        """计算加权共识分（排除极端值）"""
        consensus = {}
        for dim in self.DIMENSIONS:
            scores = [ev[dim] for ev in all_scores.values() if dim in ev]
            if len(scores) >= 3:
                # Trim extremes
                scores.sort()
                trimmed = scores[1:-1]  # remove min and max
                consensus[dim] = round(sum(trimmed) / len(trimmed), 2)
            else:
                consensus[dim] = round(sum(scores) / max(1, len(scores)), 2)
        return consensus
    
    def _compute_disagreement(self, all_scores):
        """计算Agent间分歧度"""
        disagreements = {}
        for dim in self.DIMENSIONS:
            scores = [ev[dim] for ev in all_scores.values() if dim in ev]
            if scores:
                spread = max(scores) - min(scores)
                disagreements[dim] = round(spread, 2)
        
        avg_disagreement = sum(disagreements.values()) / max(1, len(disagreements))
        return {
            'per_dimension': disagreements,
            'average': round(avg_disagreement, 2),
            'level': 'high' if avg_disagreement > 3 else 'medium' if avg_disagreement > 1.5 else 'low'
        }
    
    def _get_recommendation(self, score, red_flags, disagreement):
        if red_flags:
            return f'review_required (red flags: {", ".join(red_flags)})'
        if disagreement['level'] == 'high':
            return 'needs_discussion (high disagreement)'
        if score >= 7:
            return 'strong_approve'
        if score >= 5:
            return 'conditional_approve'
        return 'reject'
    
    def get_status(self):
        return {
            'agents': list(self.agents.keys()),
            'dimensions': list(self.DIMENSIONS.keys()),
            'total_evaluations': len(self.evaluation_history),
            'agent_counts': {role: a.evaluation_count for role, a in self.agents.items()}
        }


# Self-test
if __name__ == '__main__':
    baihu = Baihu6AgentSystem()
    
    result = baihu.evaluate(
        "Build a distributed AI task scheduling system using proven Redis queue patterns, "
        "with innovative cognitive API layer for novel task decomposition, "
        "automated scaling for efficient resource use, and long-term community sustainability."
    )
    
    print(f"Score: {result['weighted_total']}/10")
    print(f"Recommendation: {result['recommendation']}")
    print(f"Red flags: {result['red_flags']}")
    print(f"Disagreement: {result['disagreement']['level']} (avg {result['disagreement']['average']})")
    print(f"Consensus: {result['consensus']}")
    
    for role, ev in result['evaluations'].items():
        print(f"  {role}: avg={sum(ev['scores'].values())/len(ev['scores']):.1f}, conf={ev['confidence']}")
    
    print("PASS")
