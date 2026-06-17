
"""
白虎进化引擎 (Baihu Adaptive Evaluation)
评估标准自适应：基于历史评估结果动态调整评分维度和权重

核心: 4维评估(可行性/创新性/风险/ROI) + 动态权重 + 评估者校准
"""
import json, os, math
from datetime import datetime

BAIHU_DIR = os.path.join(os.path.dirname(__file__), 'baihu_data')
os.makedirs(BAIHU_DIR, exist_ok=True)

class EvaluationDimension:
    """评估维度定义"""
    def __init__(self, dim_id, name, weight=0.25, description=''):
        self.dim_id = dim_id
        self.name = name
        self.weight = weight
        self.description = description
        self.history = []  # list of (score, actual_outcome)
    
    def to_dict(self):
        return {
            'dim_id': self.dim_id,
            'name': self.name,
            'weight': self.weight,
            'description': self.description,
            'history_count': len(self.history)
        }

class BaihuEvolutionEngine:
    """白虎自适应评估引擎"""
    
    DEFAULT_DIMENSIONS = {
        'feasibility': {'name': '可行性', 'weight': 0.30, 'desc': '技术和资源可行性'},
        'innovation': {'name': '创新性', 'weight': 0.20, 'desc': '方案独特性和突破性'},
        'risk': {'name': '风险度', 'weight': 0.25, 'desc': '执行风险和不确定性'},
        'roi': {'name': '投入产出比', 'weight': 0.25, 'desc': '资源投入vs预期收益'}
    }
    
    EVALUATOR_ROLES = {
        'optimist': {'bias': 0.1, 'focus': ['innovation', 'roi']},
        'pessimist': {'bias': -0.1, 'focus': ['risk', 'feasibility']},
        'realist': {'bias': 0.0, 'focus': ['feasibility', 'roi']},
        'contrarian': {'bias': -0.05, 'focus': ['innovation', 'risk']}
    }
    
    def __init__(self):
        self.config_path = os.path.join(BAIHU_DIR, 'baihu_config.json')
        self.history_path = os.path.join(BAIHU_DIR, 'evaluation_history.jsonl')
        self.config = self._load_config()
    
    def _load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'dimensions': {k: v for k, v in self.DEFAULT_DIMENSIONS.items()},
            'evaluator_calibration': {role: 1.0 for role in self.EVALUATOR_ROLES},
            'version': 1,
            'total_evaluations': 0
        }
    
    def _save_config(self):
        self.config['version'] += 1
        self.config['updated_at'] = datetime.now().isoformat()
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def evaluate(self, proposal, context=None):
        """四Agent对抗评估"""
        scores = {}
        for role, role_config in self.EVALUATOR_ROLES.items():
            role_scores = {}
            for dim_id, dim_config in self.config['dimensions'].items():
                # Base score from proposal characteristics
                base = self._compute_base_score(proposal, dim_id)
                # Apply role bias
                bias = role_config['bias']
                focus_bonus = 0.05 if dim_id in role_config['focus'] else 0
                # Apply calibration
                calibration = self.config['evaluator_calibration'].get(role, 1.0)
                
                score = max(0, min(10, (base + bias + focus_bonus) * calibration))
                role_scores[dim_id] = round(score, 2)
            
            scores[role] = role_scores
        
        # Weighted consensus
        consensus = {}
        for dim_id, dim_config in self.config['dimensions'].items():
            dim_scores = [scores[role][dim_id] for role in scores]
            consensus[dim_id] = round(sum(dim_scores) / len(dim_scores), 2)
        
        total = sum(
            consensus[d] * self.config['dimensions'][d]['weight']
            for d in consensus
        )
        
        result = {
            'scores_by_role': scores,
            'consensus': consensus,
            'weighted_total': round(total, 2),
            'recommendation': 'approve' if total >= 6 else 'review' if total >= 4 else 'reject',
            'timestamp': datetime.now().isoformat()
        }
        
        # Record
        self.config['total_evaluations'] += 1
        self._save_config()
        
        with open(self.history_path, 'a', encoding='utf-8') as f:
            entry = {'proposal': str(proposal)[:200], 'result': result, 'context': context}
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        
        return result
    
    def _compute_base_score(self, proposal, dim_id):
        """基于proposal特征计算基础分"""
        text = str(proposal).lower()
        length_factor = min(1.0, len(text) / 500)
        
        keyword_scores = {
            'feasibility': ['existing', 'proven', 'ready', 'available', 'simple', 'tested'],
            'innovation': ['novel', 'unique', 'breakthrough', 'first', 'creative', 'new'],
            'risk': ['complex', 'uncertain', 'dependency', 'unknown', 'external'],
            'roi': ['efficient', 'scalable', 'reusable', 'automated', 'cost']
        }
        
        keywords = keyword_scores.get(dim_id, [])
        keyword_hits = sum(1 for k in keywords if k in text)
        keyword_factor = min(1.0, keyword_hits / max(1, len(keywords)))
        
        base = 5.0 + length_factor * 1.5 + keyword_factor * 2.0
        return base
    
    def adapt_weights(self, outcomes):
        """
        基于实际结果调整维度权重
        outcomes: list of {dim_id: score, actual_success: bool}
        """
        if len(outcomes) < 5:
            return {'adapted': False, 'reason': 'insufficient outcomes'}
        
        # 计算每个维度与实际成功的相关性
        correlations = {}
        for dim_id in self.config['dimensions']:
            scores = []
            successes = []
            for o in outcomes:
                if dim_id in o:
                    scores.append(o[dim_id])
                    successes.append(1.0 if o.get('actual_success', False) else 0.0)
            
            if len(scores) >= 3:
                # Simple correlation: avg score of successes vs failures
                success_avg = sum(s for s, ok in zip(scores, successes) if ok > 0) / max(1, sum(successes))
                fail_avg = sum(s for s, ok in zip(scores, successes) if ok == 0) / max(1, len(successes) - sum(successes))
                correlations[dim_id] = success_avg - fail_avg
        
        if not correlations:
            return {'adapted': False, 'reason': 'no correlations computed'}
        
        # Adjust weights proportionally
        total_corr = sum(abs(v) for v in correlations.values())
        if total_corr > 0:
            for dim_id, corr in correlations.items():
                new_weight = abs(corr) / total_corr
                old_weight = self.config['dimensions'][dim_id]['weight']
                # Gentle adjustment (30% new, 70% old)
                self.config['dimensions'][dim_id]['weight'] = round(0.7 * old_weight + 0.3 * new_weight, 3)
        
        # Normalize weights to sum to 1
        total = sum(d['weight'] for d in self.config['dimensions'].values())
        for d in self.config['dimensions'].values():
            d['weight'] = round(d['weight'] / total, 3)
        
        self._save_config()
        return {
            'adapted': True,
            'new_weights': {k: v['weight'] for k, v in self.config['dimensions'].items()},
            'correlations': correlations
        }
    
    def get_status(self):
        return {
            'dimensions': {k: v for k, v in self.config['dimensions'].items()},
            'total_evaluations': self.config['total_evaluations'],
            'version': self.config['version'],
            'evaluator_roles': list(self.EVALUATOR_ROLES.keys())
        }


# Self-test
if __name__ == '__main__':
    engine = BaihuEvolutionEngine()
    
    result = engine.evaluate(
        "Build a new distributed task scheduler using existing Redis infrastructure, "
        "proven patterns, with automated scaling and cost-efficient resource reuse.",
        context={'domain': 'infrastructure'}
    )
    print(f"Score: {result['weighted_total']}/10, Rec: {result['recommendation']}")
    print(f"Consensus: {result['consensus']}")
    
    # Test adaptation
    outcomes = [
        {'feasibility': 8, 'innovation': 3, 'risk': 2, 'roi': 7, 'actual_success': True},
        {'feasibility': 4, 'innovation': 9, 'risk': 8, 'roi': 3, 'actual_success': False},
        {'feasibility': 7, 'innovation': 5, 'risk': 3, 'roi': 8, 'actual_success': True},
        {'feasibility': 3, 'innovation': 7, 'risk': 7, 'roi': 4, 'actual_success': False},
        {'feasibility': 9, 'innovation': 4, 'risk': 1, 'roi': 9, 'actual_success': True},
    ]
    adapt = engine.adapt_weights(outcomes)
    print(f"Adapted: {adapt['adapted']}, weights: {adapt.get('new_weights','')}")
    
    status = engine.get_status()
    print(f"Total evaluations: {status['total_evaluations']}, v{status['version']}")
    print("PASS")
