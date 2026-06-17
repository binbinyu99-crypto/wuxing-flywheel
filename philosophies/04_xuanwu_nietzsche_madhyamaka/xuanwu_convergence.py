
"""
玄武收敛算法 (Xuanwu Multi-Objective Convergence)
多目标优化收敛：在多个矛盾目标间找到帕累托最优解

核心: Pareto Front + Weighted Sum + Constraint Satisfaction
"""
import json, os, math, random
from datetime import datetime

class Solution:
    """候选解"""
    def __init__(self, sol_id, description, objectives, constraints_met=True):
        self.sol_id = sol_id
        self.description = description
        self.objectives = objectives  # dict: {obj_name: value}
        self.constraints_met = constraints_met
        self.dominated_by = []
        self.dominates = []
        self.pareto_rank = -1
    
    def to_dict(self):
        return {
            'sol_id': self.sol_id,
            'description': self.description,
            'objectives': self.objectives,
            'constraints_met': self.constraints_met,
            'pareto_rank': self.pareto_rank,
            'dominated_by_count': len(self.dominated_by),
            'dominates_count': len(self.dominates)
        }

class XuanwuConvergence:
    """玄武多目标收敛引擎"""
    
    def __init__(self):
        self.solutions = []
        self.objectives_config = {}
        self.constraints = []
    
    def set_objectives(self, objectives):
        """设置优化目标
        objectives: dict of {name: {'direction': 'maximize'|'minimize', 'weight': float}}
        """
        self.objectives_config = objectives
    
    def add_solution(self, sol_id, description, objectives, constraints_met=True):
        """添加候选解"""
        sol = Solution(sol_id, description, objectives, constraints_met)
        self.solutions.append(sol)
        return sol
    
    def _dominates(self, sol_a, sol_b):
        """判断sol_a是否支配sol_b"""
        at_least_one_better = False
        for obj_name, config in self.objectives_config.items():
            val_a = sol_a.objectives.get(obj_name, 0)
            val_b = sol_b.objectives.get(obj_name, 0)
            
            if config['direction'] == 'maximize':
                if val_a < val_b:
                    return False
                if val_a > val_b:
                    at_least_one_better = True
            else:  # minimize
                if val_a > val_b:
                    return False
                if val_a < val_b:
                    at_least_one_better = True
        
        return at_least_one_better
    
    def compute_pareto_front(self):
        """计算帕累托前沿"""
        feasible = [s for s in self.solutions if s.constraints_met]
        
        # Clear previous
        for s in feasible:
            s.dominated_by = []
            s.dominates = []
        
        # Pairwise dominance check
        for i, a in enumerate(feasible):
            for j, b in enumerate(feasible):
                if i == j:
                    continue
                if self._dominates(a, b):
                    a.dominates.append(b.sol_id)
                    b.dominated_by.append(a.sol_id)
        
        # Assign ranks (non-dominated sorting)
        remaining = list(feasible)
        rank = 0
        while remaining:
            front = [s for s in remaining if len([d for d in s.dominated_by if d in [r.sol_id for r in remaining]]) == 0]
            for s in front:
                s.pareto_rank = rank
            remaining = [s for s in remaining if s not in front]
            rank += 1
        
        pareto_front = [s for s in feasible if s.pareto_rank == 0]
        return pareto_front
    
    def weighted_sum_rank(self):
        """加权和排序"""
        if not self.objectives_config:
            return []
        
        ranked = []
        for sol in self.solutions:
            if not sol.constraints_met:
                continue
            
            total = 0
            for obj_name, config in self.objectives_config.items():
                val = sol.objectives.get(obj_name, 0)
                weight = config.get('weight', 1.0)
                if config['direction'] == 'minimize':
                    val = -val  # flip for minimization
                total += val * weight
            
            ranked.append((sol, total))
        
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked
    
    def converge(self, strategy='pareto_weighted'):
        """执行收敛，返回推荐解"""
        if not self.solutions:
            return {'error': 'no solutions'}
        
        pareto = self.compute_pareto_front()
        weighted = self.weighted_sum_rank()
        
        if strategy == 'pareto_weighted':
            # Pareto front solutions, then weighted rank within front
            front_ids = {s.sol_id for s in pareto}
            front_weighted = [(s, score) for s, score in weighted if s.sol_id in front_ids]
            recommended = front_weighted[0][0] if front_weighted else (weighted[0][0] if weighted else None)
        elif strategy == 'weighted_only':
            recommended = weighted[0][0] if weighted else None
        else:  # pareto_only
            recommended = pareto[0] if pareto else None
        
        result = {
            'strategy': strategy,
            'total_solutions': len(self.solutions),
            'feasible_solutions': len([s for s in self.solutions if s.constraints_met]),
            'pareto_front_size': len(pareto),
            'pareto_front': [s.to_dict() for s in pareto],
            'weighted_ranking': [(s.sol_id, round(score, 3)) for s, score in weighted[:5]],
            'recommended': recommended.to_dict() if recommended else None,
            'timestamp': datetime.now().isoformat()
        }
        
        return result
    
    def get_trade_off_analysis(self):
        """分析目标间的权衡关系"""
        if len(self.solutions) < 2:
            return {}
        
        trade_offs = {}
        obj_names = list(self.objectives_config.keys())
        
        for i, name_a in enumerate(obj_names):
            for name_b in obj_names[i+1:]:
                vals_a = [s.objectives.get(name_a, 0) for s in self.solutions if s.constraints_met]
                vals_b = [s.objectives.get(name_b, 0) for s in self.solutions if s.constraints_met]
                
                if len(vals_a) >= 2:
                    # Simple correlation
                    mean_a = sum(vals_a) / len(vals_a)
                    mean_b = sum(vals_b) / len(vals_b)
                    cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(vals_a, vals_b)) / len(vals_a)
                    std_a = math.sqrt(sum((a - mean_a)**2 for a in vals_a) / len(vals_a))
                    std_b = math.sqrt(sum((b - mean_b)**2 for b in vals_b) / len(vals_b))
                    
                    corr = cov / (std_a * std_b) if std_a > 0 and std_b > 0 else 0
                    
                    trade_offs[f'{name_a}_vs_{name_b}'] = {
                        'correlation': round(corr, 3),
                        'relationship': 'synergy' if corr > 0.3 else 'trade-off' if corr < -0.3 else 'independent'
                    }
        
        return trade_offs


# Self-test
if __name__ == '__main__':
    xuanwu = XuanwuConvergence()
    
    xuanwu.set_objectives({
        'performance': {'direction': 'maximize', 'weight': 0.35},
        'cost': {'direction': 'minimize', 'weight': 0.25},
        'reliability': {'direction': 'maximize', 'weight': 0.25},
        'innovation': {'direction': 'maximize', 'weight': 0.15}
    })
    
    xuanwu.add_solution('S1', 'High-perf expensive', {'performance': 9, 'cost': 8, 'reliability': 7, 'innovation': 6})
    xuanwu.add_solution('S2', 'Budget reliable', {'performance': 5, 'cost': 2, 'reliability': 9, 'innovation': 3})
    xuanwu.add_solution('S3', 'Innovative risky', {'performance': 7, 'cost': 5, 'reliability': 4, 'innovation': 9})
    xuanwu.add_solution('S4', 'Balanced', {'performance': 7, 'cost': 4, 'reliability': 7, 'innovation': 6})
    xuanwu.add_solution('S5', 'Dominated', {'performance': 4, 'cost': 7, 'reliability': 3, 'innovation': 2}, constraints_met=False)
    
    result = xuanwu.converge()
    print(f"Pareto front: {result['pareto_front_size']} solutions")
    print(f"Recommended: {result['recommended']['sol_id']} - {result['recommended']['description']}")
    print(f"Weighted ranking: {result['weighted_ranking']}")
    
    trade_offs = xuanwu.get_trade_off_analysis()
    for pair, analysis in trade_offs.items():
        print(f"  {pair}: {analysis['relationship']} (r={analysis['correlation']})")
    
    print("PASS")
