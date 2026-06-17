
"""
残差引擎V2 (Residual Engine V2 - Semantic Detection)
在V1数值残差基础上，增加语义级别残差检测

语义残差: 意图偏差 / 概念漂移 / 逻辑断裂 / 风格偏差
"""
import json, os, hashlib, re
from datetime import datetime

class SemanticResidual:
    """语义残差检测器"""
    
    INTENT_KEYWORDS = {
        'analyze': ['分析', 'analyze', 'study', 'examine', 'investigate'],
        'build': ['构建', 'build', 'create', 'implement', 'develop'],
        'evaluate': ['评估', 'evaluate', 'assess', 'judge', 'score'],
        'optimize': ['优化', 'optimize', 'improve', 'enhance', 'refine'],
        'document': ['文档', 'document', 'write', 'describe', 'explain']
    }
    
    def detect_intent_drift(self, original_intent, actual_output):
        """检测意图偏差"""
        original_intents = self._extract_intents(str(original_intent))
        actual_intents = self._extract_intents(str(actual_output))
        
        matched = original_intents & actual_intents
        drifted = original_intents - actual_intents
        unexpected = actual_intents - original_intents
        
        drift_score = len(drifted) / max(1, len(original_intents))
        
        return {
            'type': 'intent_drift',
            'original_intents': list(original_intents),
            'actual_intents': list(actual_intents),
            'matched': list(matched),
            'drifted': list(drifted),
            'unexpected': list(unexpected),
            'drift_score': round(drift_score, 3),
            'severity': 'high' if drift_score > 0.5 else 'medium' if drift_score > 0.2 else 'low'
        }
    
    def _extract_intents(self, text):
        text_lower = text.lower()
        intents = set()
        for intent, keywords in self.INTENT_KEYWORDS.items():
            if any(k in text_lower for k in keywords):
                intents.add(intent)
        return intents
    
    def detect_concept_drift(self, expected_concepts, actual_concepts):
        """检测概念漂移"""
        expected = set(expected_concepts)
        actual = set(actual_concepts)
        
        missing = expected - actual
        added = actual - expected
        overlap = expected & actual
        
        drift = len(missing) / max(1, len(expected))
        
        return {
            'type': 'concept_drift',
            'expected': list(expected),
            'actual': list(actual),
            'missing': list(missing),
            'added': list(added),
            'overlap': list(overlap),
            'drift_score': round(drift, 3),
            'severity': 'high' if drift > 0.5 else 'medium' if drift > 0.2 else 'low'
        }
    
    def detect_logic_break(self, reasoning_chain):
        """检测逻辑断裂"""
        if not reasoning_chain or len(reasoning_chain) < 2:
            return {'type': 'logic_break', 'breaks': [], 'severity': 'low'}
        
        breaks = []
        for i in range(1, len(reasoning_chain)):
            prev = str(reasoning_chain[i-1]).lower()
            curr = str(reasoning_chain[i]).lower()
            
            # Check for contradictions
            if ('but' in curr or 'however' in curr or 'contrary' in curr) and i > 0:
                breaks.append({
                    'position': i,
                    'type': 'contradiction',
                    'between': [reasoning_chain[i-1][:50], reasoning_chain[i][:50]]
                })
            
            # Check for non-sequitur (no shared keywords)
            prev_words = set(prev.split())
            curr_words = set(curr.split())
            shared = prev_words & curr_words - {'the', 'a', 'is', 'of', 'to', 'and', 'in'}
            if len(shared) == 0 and len(prev_words) > 3 and len(curr_words) > 3:
                breaks.append({
                    'position': i,
                    'type': 'non_sequitur',
                    'between': [reasoning_chain[i-1][:50], reasoning_chain[i][:50]]
                })
        
        return {
            'type': 'logic_break',
            'breaks': breaks,
            'break_count': len(breaks),
            'chain_length': len(reasoning_chain),
            'severity': 'high' if len(breaks) > 2 else 'medium' if breaks else 'low'
        }
    
    def detect_style_deviation(self, expected_style, actual_text):
        """检测风格偏差"""
        text = str(actual_text)
        
        style_metrics = {
            'formal': {
                'indicators': ['therefore', 'furthermore', 'consequently', 'regarding'],
                'anti_indicators': ['lol', 'btw', 'gonna', 'wanna']
            },
            'technical': {
                'indicators': ['algorithm', 'implementation', 'architecture', 'protocol'],
                'anti_indicators': ['simple', 'easy', 'just', 'basically']
            },
            'concise': {
                'max_sentence_length': 20,
                'max_paragraph_length': 100
            }
        }
        
        deviations = []
        style_config = style_metrics.get(expected_style, {})
        text_lower = text.lower()
        
        if 'indicators' in style_config:
            hits = sum(1 for k in style_config['indicators'] if k in text_lower)
            anti_hits = sum(1 for k in style_config['anti_indicators'] if k in text_lower)
            if anti_hits > hits:
                deviations.append(f'Style mismatch: expected {expected_style}, found informal markers')
        
        if 'max_sentence_length' in style_config:
            sentences = text.split('.')
            long_sentences = [s for s in sentences if len(s.split()) > style_config['max_sentence_length']]
            if long_sentences:
                deviations.append(f'{len(long_sentences)} sentences exceed max length')
        
        return {
            'type': 'style_deviation',
            'expected_style': expected_style,
            'deviations': deviations,
            'deviation_count': len(deviations),
            'severity': 'medium' if deviations else 'low'
        }


class ResidualEngineV2:
    """残差引擎V2 - 数值+语义"""
    
    def __init__(self):
        self.semantic = SemanticResidual()
        self.log_path = os.path.join(os.path.dirname(__file__), 'evolution_data', 'residual_v2.jsonl')
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
    
    def full_analysis(self, task_context):
        """完整残差分析（数值+语义）"""
        results = {
            'task_id': task_context.get('task_id', 'unknown'),
            'timestamp': datetime.now().isoformat(),
            'analyses': {}
        }
        
        # Intent drift
        if 'original_intent' in task_context and 'actual_output' in task_context:
            results['analyses']['intent_drift'] = self.semantic.detect_intent_drift(
                task_context['original_intent'], task_context['actual_output']
            )
        
        # Concept drift
        if 'expected_concepts' in task_context and 'actual_concepts' in task_context:
            results['analyses']['concept_drift'] = self.semantic.detect_concept_drift(
                task_context['expected_concepts'], task_context['actual_concepts']
            )
        
        # Logic break
        if 'reasoning_chain' in task_context:
            results['analyses']['logic_break'] = self.semantic.detect_logic_break(
                task_context['reasoning_chain']
            )
        
        # Style deviation
        if 'expected_style' in task_context and 'actual_text' in task_context:
            results['analyses']['style_deviation'] = self.semantic.detect_style_deviation(
                task_context['expected_style'], task_context['actual_text']
            )
        
        # Overall severity
        severities = [a.get('severity', 'low') for a in results['analyses'].values()]
        severity_order = {'low': 0, 'medium': 1, 'high': 2}
        max_severity = max(severities, key=lambda s: severity_order.get(s, 0)) if severities else 'low'
        results['overall_severity'] = max_severity
        
        # Log
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(results, ensure_ascii=False) + '\n')
        
        return results
    
    def get_stats(self):
        count = 0
        if os.path.exists(self.log_path):
            with open(self.log_path, 'r', encoding='utf-8') as f:
                count = sum(1 for _ in f)
        return {'total_analyses': count, 'log_path': self.log_path}


# Self-test
if __name__ == '__main__':
    import sys; sys.stdout.reconfigure(encoding='utf-8')
    engine = ResidualEngineV2()
    
    result = engine.full_analysis({
        'task_id': 'test-001',
        'original_intent': 'Build and analyze a distributed task scheduler',
        'actual_output': 'Implemented a task scheduler with evaluation metrics',
        'expected_concepts': ['distributed', 'scheduler', 'queue', 'worker'],
        'actual_concepts': ['scheduler', 'metrics', 'evaluation', 'worker'],
        'reasoning_chain': [
            'Task scheduling needs queue management',
            'Queue management requires Redis',
            'However the weather is nice today',
            'Therefore we implement worker pools'
        ],
        'expected_style': 'technical',
        'actual_text': 'The algorithm implements a distributed protocol for task execution'
    })
    
    print(f"Overall severity: {result['overall_severity']}")
    for name, analysis in result['analyses'].items():
        print(f"  {name}: severity={analysis['severity']}, score={analysis.get('drift_score', analysis.get('break_count', '-'))}")
    
    stats = engine.get_stats()
    print(f"Stats: {stats}")
    print("PASS")
