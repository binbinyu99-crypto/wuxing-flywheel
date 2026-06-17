"""
白虎·四Agent对抗评估系统 v0.1 — SkyCetus 天鲸之城
Tasks #51-55: 乐观/悲观/现实/逆向 Agent + 对抗结果聚合

核心: 不选"正确答案"，保留四个视角的冲突
"""
import json, datetime, sys

class BaihuEngine:
    """白虎对抗评估引擎 — 4Agent多视角评分"""
    
    def __init__(self):
        self.evaluations = []
        self.agents = {
            'optimist': OptimistAgent(),
            'pessimist': PessimistAgent(),
            'realist': RealistAgent(),
            'contrarian': ContrarianAgent(),
        }
    
    def evaluate(self, seed):
        """四Agent对抗评估一个种子/方案"""
        results = {}
        for name, agent in self.agents.items():
            results[name] = agent.evaluate(seed)
        
        # Aggregate (不强制收敛)
        aggregated = self._aggregate(seed, results)
        self.evaluations.append(aggregated)
        return aggregated
    
    def _aggregate(self, seed, agent_results):
        """聚合四个视角 — TEP: 保留冲突"""
        # 4维打分取加权平均
        dims = ['feasibility', 'impact', 'risk', 'scalability']
        dim_scores = {}
        for d in dims:
            scores = [r['scores'].get(d, 5) for r in agent_results.values()]
            dim_scores[d] = {
                'mean': sum(scores) / len(scores),
                'min': min(scores),
                'max': max(scores),
                'spread': max(scores) - min(scores),  # 分歧度
                'scores': {name: r['scores'].get(d, 5) for name, r in agent_results.items()}
            }
        
        # 加权总分: 可行性25% × 影响力30% × 风险20%(反转) × 扩展性25%
        weights = {'feasibility': 0.25, 'impact': 0.30, 'risk': 0.20, 'scalability': 0.25}
        weighted_score = sum(
            dim_scores[d]['mean'] * w for d, w in weights.items()
        )
        # Risk is inverse: high risk = low score contribution
        risk_adj = (10 - dim_scores['risk']['mean']) * weights['risk']
        weighted_score = weighted_score - dim_scores['risk']['mean'] * weights['risk'] + risk_adj
        
        # 冲突检测
        conflicts = []
        for d in dims:
            if dim_scores[d]['spread'] > 3:  # 分歧>3分 = 显著冲突
                conflicts.append({
                    'dimension': d,
                    'spread': dim_scores[d]['spread'],
                    'details': dim_scores[d]['scores']
                })
        
        return {
            'seed': seed.get('title', 'unknown'),
            'timestamp': datetime.datetime.now().isoformat(),
            'weighted_score': round(weighted_score, 2),
            'dimension_scores': dim_scores,
            'agent_opinions': {name: r['opinion'] for name, r in agent_results.items()},
            'agent_recommendations': {name: r['recommendation'] for name, r in agent_results.items()},
            'conflicts': conflicts,
            'conflict_count': len(conflicts),
            'consensus': len(conflicts) == 0,
            'verdict': self._verdict(weighted_score, conflicts)
        }
    
    def _verdict(self, score, conflicts):
        """生成判定 (不是最终决策，是信息)"""
        if score >= 7.5 and len(conflicts) == 0:
            return 'STRONG_GO'
        elif score >= 6.5:
            return 'GO_WITH_REVIEW' if conflicts else 'GO'
        elif score >= 5.0:
            return 'HOLD_FOR_FEEDBACK'
        else:
            return 'RECONSIDER'


class BaseAgent:
    """Agent基类"""
    def evaluate(self, seed):
        return {
            'scores': self._score(seed),
            'opinion': self._opinion(seed),
            'recommendation': self._recommend(seed)
        }
    
    def _score(self, seed): raise NotImplementedError
    def _opinion(self, seed): raise NotImplementedError
    def _recommend(self, seed): raise NotImplementedError


class OptimistAgent(BaseAgent):
    """乐观Agent — 看到机会和潜力"""
    def _score(self, seed):
        base = seed.get('base_scores', {})
        return {
            'feasibility': min(10, base.get('feasibility', 6) + 1.5),
            'impact': min(10, base.get('impact', 7) + 2),
            'risk': max(1, base.get('risk', 5) - 2),  # 低估风险
            'scalability': min(10, base.get('scalability', 6) + 1.5)
        }
    
    def _opinion(self, seed):
        title = seed.get('title', '')
        return f"'{title}'有巨大潜力。市场时机好，技术可行性高，先发优势明显。"
    
    def _recommend(self, seed):
        return "立即推进，快速迭代，抢占市场窗口"


class PessimistAgent(BaseAgent):
    """悲观Agent — 看到风险和障碍"""
    def _score(self, seed):
        base = seed.get('base_scores', {})
        return {
            'feasibility': max(1, base.get('feasibility', 6) - 2),
            'impact': max(1, base.get('impact', 7) - 1.5),
            'risk': min(10, base.get('risk', 5) + 2.5),  # 高估风险
            'scalability': max(1, base.get('scalability', 6) - 2)
        }
    
    def _opinion(self, seed):
        title = seed.get('title', '')
        return f"'{title}'面临严重挑战。竞争激烈，技术门槛高，资源可能不足。"
    
    def _recommend(self, seed):
        return "谨慎评估，先做小规模验证，准备退出方案"


class RealistAgent(BaseAgent):
    """现实Agent — 基于数据的客观判断"""
    def _score(self, seed):
        base = seed.get('base_scores', {})
        return {
            'feasibility': base.get('feasibility', 6),
            'impact': base.get('impact', 7),
            'risk': base.get('risk', 5),
            'scalability': base.get('scalability', 6)
        }
    
    def _opinion(self, seed):
        title = seed.get('title', '')
        return f"'{title}'需要平衡评估。有明确的价值点，也有需要解决的障碍。关键看执行力。"
    
    def _recommend(self, seed):
        return "制定清晰路线图，设置里程碑检查点，保持灵活调整"


class ContrarianAgent(BaseAgent):
    """逆向Agent — 挑战主流假设"""
    def _score(self, seed):
        base = seed.get('base_scores', {})
        # 逆向思考: 大家看好的反而给低分，大家忽略的反而给高分
        return {
            'feasibility': 10 - base.get('feasibility', 6) + 3,  # clamp later
            'impact': max(1, min(10, 10 - base.get('impact', 7) + 4)),
            'risk': base.get('risk', 5) + 1,  # 发现隐藏风险
            'scalability': max(1, min(10, base.get('scalability', 6) - 1 + (3 if base.get('scalability',6) < 5 else -1)))
        }
    
    def _opinion(self, seed):
        title = seed.get('title', '')
        return f"'{title}'的主流看法可能有盲点。需要考虑替代路径和非显性机会。"
    
    def _recommend(self, seed):
        return "探索非主流方向，测试反直觉假设，寻找被忽视的价值"


# ===== Demo =====
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    
    engine = BaihuEngine()
    
    # Test seeds
    seeds = [
        {
            'title': '券商清算四流合一SaaS',
            'base_scores': {'feasibility': 7, 'impact': 8, 'risk': 6, 'scalability': 7}
        },
        {
            'title': '智慧楼宇AI机器人',
            'base_scores': {'feasibility': 6, 'impact': 7, 'risk': 5, 'scalability': 8}
        },
        {
            'title': '热力学计算芯片',
            'base_scores': {'feasibility': 3, 'impact': 9, 'risk': 8, 'scalability': 4}
        }
    ]
    
    print("=" * 60)
    print("白虎·四Agent对抗评估系统 v0.1")
    print("=" * 60)
    
    for seed in seeds:
        result = engine.evaluate(seed)
        
        print(f"\n{'─' * 50}")
        print(f"种子: {result['seed']}")
        print(f"加权总分: {result['weighted_score']}/10")
        print(f"判定: {result['verdict']}")
        print(f"冲突数: {result['conflict_count']}")
        
        print(f"\n  四维评分:")
        for dim, data in result['dimension_scores'].items():
            bar = '█' * int(data['mean']) + '░' * (10 - int(data['mean']))
            spread_icon = '⚡' if data['spread'] > 3 else '  '
            print(f"    {dim:15s} {data['mean']:4.1f} {bar} (分歧{data['spread']:.1f}) {spread_icon}")
        
        print(f"\n  Agent意见:")
        for name, opinion in result['agent_opinions'].items():
            emoji = {'optimist': '😊', 'pessimist': '😟', 'realist': '🤔', 'contrarian': '🔄'}
            print(f"    {emoji.get(name,'')} {name:12s}: {opinion[:60]}")
        
        if result['conflicts']:
            print(f"\n  ⚡ 冲突:")
            for c in result['conflicts']:
                print(f"    {c['dimension']}: 分歧{c['spread']:.1f} — {c['details']}")
    
    print(f"\n{'=' * 60}")
    print(f"评估完成: {len(engine.evaluations)} 个种子")
    verdicts = [e['verdict'] for e in engine.evaluations]
    print(f"判定分布: {dict((v, verdicts.count(v)) for v in set(verdicts))}")
