
"""
evolution-gen 飞轮驱动迭代
基于残差数据自动生成进化方案

输入: 飞轮运行残差 + 历史模式
输出: 进化建议 + 权重调整 + 新模式
"""
import json, os, time
from datetime import datetime

class EvolutionGenerator:
    """飞轮驱动的进化生成器"""
    
    EVOLUTION_STRATEGIES = {
        'weight_adjust': {
            'name': '权重微调',
            'trigger': 'residual_drift > 0.2',
            'action': 'Adjust beast weights based on residual analysis'
        },
        'pattern_learn': {
            'name': '模式学习',
            'trigger': 'repeated_pattern detected',
            'action': 'Extract pattern and add to pattern database'
        },
        'stage_optimize': {
            'name': '阶段优化',
            'trigger': 'stage_timeout or stage_low_quality',
            'action': 'Optimize slow/low-quality stages'
        },
        'prompt_evolve': {
            'name': 'Prompt进化',
            'trigger': 'output_quality < threshold',
            'action': 'Evolve prompts based on output quality feedback'
        },
        'topology_mutate': {
            'name': '拓扑变异',
            'trigger': 'structural_residual detected',
            'action': 'Add/remove/reorder flywheel stages'
        }
    }
    
    def __init__(self):
        self.evolution_log = []
    
    def analyze_residuals(self, residual_data):
        """分析残差数据，生成进化建议"""
        suggestions = []
        
        # Check for intent drift
        intent = residual_data.get('intent_drift', {})
        if intent.get('drift_score', 0) > 0.2:
            suggestions.append({
                'strategy': 'prompt_evolve',
                'priority': 'high',
                'reason': f'Intent drift detected: {intent.get("drift_score", 0):.2f}',
                'action': 'Refine system prompts to reduce intent drift'
            })
        
        # Check for concept drift
        concept = residual_data.get('concept_drift', {})
        if concept.get('drift_score', 0) > 0.3:
            suggestions.append({
                'strategy': 'pattern_learn',
                'priority': 'medium',
                'reason': f'Concept drift: {concept.get("missing", [])}',
                'action': 'Update concept dictionary and add missing concepts'
            })
        
        # Check for logic breaks
        logic = residual_data.get('logic_break', {})
        if logic.get('break_count', 0) > 1:
            suggestions.append({
                'strategy': 'topology_mutate',
                'priority': 'high',
                'reason': f'{logic.get("break_count", 0)} logic breaks detected',
                'action': 'Add validation stage between breaking stages'
            })
        
        # Check for timeout issues
        if residual_data.get('timed_out', False):
            suggestions.append({
                'strategy': 'stage_optimize',
                'priority': 'high',
                'reason': 'Flywheel stage timed out',
                'action': 'Reduce token budget or split into sub-stages'
            })
        
        # Default: weight adjustment
        if not suggestions:
            suggestions.append({
                'strategy': 'weight_adjust',
                'priority': 'low',
                'reason': 'Routine optimization',
                'action': 'Fine-tune beast weights based on recent performance'
            })
        
        evolution = {
            'timestamp': datetime.now().isoformat(),
            'residual_input': str(residual_data)[:200],
            'suggestions': suggestions,
            'total_suggestions': len(suggestions),
            'highest_priority': max(s['priority'] for s in suggestions) if suggestions else 'none'
        }
        
        self.evolution_log.append(evolution)
        return evolution
    
    def generate_weight_update(self, current_weights, performance_data):
        """基于性能数据生成权重更新"""
        new_weights = current_weights.copy()
        
        for beast, perf in performance_data.items():
            if beast in new_weights:
                quality = perf.get('quality', 0.5)
                speed = perf.get('speed', 0.5)
                
                # Increase weight for high quality, decrease for low
                adjustment = (quality - 0.5) * 0.1 + (speed - 0.5) * 0.05
                new_weights[beast] = max(0.1, min(0.5, new_weights[beast] + adjustment))
        
        # Normalize
        total = sum(new_weights.values())
        new_weights = {k: round(v/total, 3) for k, v in new_weights.items()}
        
        return {
            'old_weights': current_weights,
            'new_weights': new_weights,
            'changes': {k: round(new_weights[k] - current_weights.get(k, 0.25), 4) for k in new_weights}
        }
    
    def get_stats(self):
        return {
            'total_evolutions': len(self.evolution_log),
            'strategies_available': len(self.EVOLUTION_STRATEGIES)
        }


if __name__ == '__main__':
    import sys; sys.stdout.reconfigure(encoding='utf-8')
    gen = EvolutionGenerator()
    
    # Test residual analysis
    result = gen.analyze_residuals({
        'intent_drift': {'drift_score': 0.35},
        'concept_drift': {'drift_score': 0.15, 'missing': ['distributed']},
        'logic_break': {'break_count': 2},
        'timed_out': False
    })
    print(f"Suggestions: {result['total_suggestions']}, Priority: {result['highest_priority']}")
    for s in result['suggestions']:
        print(f"  [{s['priority']}] {s['strategy']}: {s['reason']}")
    
    # Test weight update
    weights = gen.generate_weight_update(
        {'qinglong': 0.25, 'baihu': 0.25, 'xuanwu': 0.25, 'zhuque': 0.25},
        {'qinglong': {'quality': 0.8, 'speed': 0.7}, 'baihu': {'quality': 0.6, 'speed': 0.5},
         'xuanwu': {'quality': 0.7, 'speed': 0.6}, 'zhuque': {'quality': 0.9, 'speed': 0.8}}
    )
    print(f"Weight update: {weights['changes']}")
    
    stats = gen.get_stats()
    print(f"Stats: {stats}")
    print("PASS")
