
"""
baihu_api.py - 白虎(评估)API
四Agent对抗评分：乐观者/悲观者/现实者/反向者
"""
import json, time, hashlib
from datetime import datetime

class BaihuAPI:
    """
    白虎评估API - Four-Agent Adversarial Scoring
    
    Agents:
    - Optimist: Sees opportunities, potential, upside
    - Pessimist: Sees risks, challenges, failure modes
    - Realist: Balanced view based on data and precedents
    - Contrarian: Challenges assumptions, finds hidden risks
    
    Scoring dimensions:
    - Feasibility (可行性)
    - Impact (影响力)
    - Risk (风险可控度)
    - Scalability (可扩展性)
    """
    
    AGENTS = {
        'optimist': {
            'name': '乐观者',
            'weight': 0.20,
            'bias': 1.5,  # positive bias
            'prompt_style': 'Focus on opportunities, market potential, best-case scenarios, and competitive advantages.'
        },
        'pessimist': {
            'name': '悲观者',
            'weight': 0.25,
            'bias': -1.5,
            'prompt_style': 'Focus on risks, challenges, failure modes, competitive threats, and worst-case scenarios.'
        },
        'realist': {
            'name': '现实者',
            'weight': 0.35,
            'bias': 0,
            'prompt_style': 'Provide balanced analysis based on market data, precedents, and realistic expectations.'
        },
        'contrarian': {
            'name': '反向者',
            'weight': 0.20,
            'bias': -0.5,
            'prompt_style': 'Challenge every assumption. What if the opposite is true? Find hidden risks and blind spots.'
        }
    }
    
    DIMENSIONS = ['feasibility', 'impact', 'risk', 'scalability']
    DIMENSION_LABELS = {
        'feasibility': '可行性',
        'impact': '影响力',
        'risk': '风险可控度',
        'scalability': '可扩展性'
    }
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client  # Optional LLM for real evaluation
        self.evaluations = []
    
    def evaluate(self, proposal, context=None):
        """
        Run four-agent adversarial evaluation on a proposal.
        Returns structured scoring with reasoning.
        """
        eval_id = f"baihu-{hashlib.md5(f'{proposal[:50]}{time.time()}'.encode()).hexdigest()[:12]}"
        start = time.time()
        
        # Run each agent
        agent_results = {}
        for agent_key, agent_config in self.AGENTS.items():
            if self.llm_client:
                result = self._evaluate_with_llm(agent_key, agent_config, proposal, context)
            else:
                result = self._evaluate_template(agent_key, agent_config, proposal, context)
            agent_results[agent_key] = result
        
        # Aggregate scores
        final_scores = self._aggregate(agent_results)
        weighted_total = sum(
            final_scores[d] * (0.30 if d == 'feasibility' else 0.25 if d in ('impact', 'risk') else 0.20)
            for d in self.DIMENSIONS
        )
        
        # Decision
        if weighted_total >= 7.0 and final_scores['risk'] >= 5.0:
            decision = 'approve'
        elif weighted_total >= 5.0:
            decision = 'review'
        else:
            decision = 'reject'
        
        elapsed = time.time() - start
        
        evaluation = {
            'eval_id': eval_id,
            'proposal': proposal[:300],
            'agents': agent_results,
            'final_scores': final_scores,
            'weighted_total': round(weighted_total, 2),
            'decision': decision,
            'consensus': self._check_consensus(agent_results),
            'elapsed_seconds': round(elapsed, 3),
            'timestamp': datetime.now().isoformat()
        }
        
        self.evaluations.append(evaluation)
        return evaluation
    
    def _evaluate_template(self, agent_key, config, proposal, context):
        """Template-based evaluation (no LLM needed)"""
        import random
        
        base = 6.0 + config['bias']
        # Adjust based on proposal length/complexity
        complexity = min(2.0, len(proposal) / 200)
        
        scores = {}
        reasoning = {}
        
        for dim in self.DIMENSIONS:
            noise = random.uniform(-1.0, 1.0)
            score = max(1.0, min(10.0, base + complexity * 0.5 + noise))
            scores[dim] = round(score, 1)
            reasoning[dim] = f"{config['name']} perspective on {self.DIMENSION_LABELS[dim]}"
        
        return {
            'agent': config['name'],
            'scores': scores,
            'reasoning': reasoning,
            'mode': 'template'
        }
    
    def _evaluate_with_llm(self, agent_key, config, proposal, context):
        """LLM-based evaluation"""
        prompt = f"""You are the {config['name']} ({agent_key}) in a four-agent evaluation panel.
{config['prompt_style']}

Evaluate this proposal on 4 dimensions (score 1-10 each):
1. Feasibility (可行性): Can this actually be built/done?
2. Impact (影响力): How significant is the potential impact?
3. Risk (风险可控度): How well can risks be managed? (higher = more controllable)
4. Scalability (可扩展性): Can this scale?

Proposal: {proposal}
{f'Context: {json.dumps(context, ensure_ascii=False)}' if context else ''}

Respond in JSON: {{"scores": {{"feasibility": X, "impact": X, "risk": X, "scalability": X}}, "reasoning": {{"feasibility": "...", "impact": "...", "risk": "...", "scalability": "..."}}}}"""
        
        try:
            result = self.llm_client(prompt)
            # Parse JSON from LLM response
            start = result.find('{')
            end = result.rfind('}') + 1
            if start >= 0 and end > start:
                parsed = json.loads(result[start:end])
                return {
                    'agent': config['name'],
                    'scores': parsed.get('scores', {}),
                    'reasoning': parsed.get('reasoning', {}),
                    'mode': 'llm'
                }
        except Exception as e:
            pass
        
        # Fallback to template
        return self._evaluate_template(agent_key, config, proposal, context)
    
    def _aggregate(self, agent_results):
        """Weighted aggregation of agent scores"""
        final = {}
        for dim in self.DIMENSIONS:
            weighted_sum = 0
            total_weight = 0
            for agent_key, result in agent_results.items():
                weight = self.AGENTS[agent_key]['weight']
                score = result['scores'].get(dim, 5.0)
                weighted_sum += score * weight
                total_weight += weight
            final[dim] = round(weighted_sum / total_weight if total_weight else 5.0, 2)
        return final
    
    def _check_consensus(self, agent_results):
        """Check if agents agree or disagree"""
        all_totals = []
        for result in agent_results.values():
            avg = sum(result['scores'].values()) / len(result['scores'])
            all_totals.append(avg)
        
        spread = max(all_totals) - min(all_totals)
        if spread < 2.0:
            return {'level': 'strong', 'spread': round(spread, 2), 'note': 'Agents largely agree'}
        elif spread < 4.0:
            return {'level': 'moderate', 'spread': round(spread, 2), 'note': 'Some disagreement between agents'}
        else:
            return {'level': 'weak', 'spread': round(spread, 2), 'note': 'Significant disagreement - needs human review'}
    
    def get_history(self, limit=10):
        return self.evaluations[-limit:]


# === Self-test ===
if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    api = BaihuAPI()
    
    result = api.evaluate(
        "Build a distributed clearing system for securities firms using event sourcing, "
        "double-entry ledger, and real-time risk monitoring. Target: mid-size brokerages.",
        context={'industry': 'finance', 'competition': 'hengshen, jinzheng'}
    )
    
    print("=== Baihu Evaluation API Test ===")
    print(f"Eval ID: {result['eval_id']}")
    print(f"Decision: {result['decision']}")
    print(f"Weighted Total: {result['weighted_total']}/10")
    print(f"Consensus: {result['consensus']['level']} (spread: {result['consensus']['spread']})")
    print(f"Elapsed: {result['elapsed_seconds']}s")
    print(f"\nAgent Scores:")
    for agent_key, agent_data in result['agents'].items():
        avg = sum(agent_data['scores'].values()) / len(agent_data['scores'])
        print(f"  {agent_data['agent']}: avg={avg:.1f} scores={agent_data['scores']}")
    print(f"\nFinal Scores:")
    for dim, score in result['final_scores'].items():
        label = BaihuAPI.DIMENSION_LABELS[dim]
        print(f"  {label}: {score}")
    print("\nBaihu API: OK")
