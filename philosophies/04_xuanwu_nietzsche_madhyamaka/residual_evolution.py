
"""
残差驱动进化引擎 (Residual Evolution Engine)
飞轮自我学习：通过执行残差(predicted vs actual)驱动权重/策略进化

核心: R6(Residual) -> R7(Refine) 闭环
"""
import json, os, time, hashlib, math
from datetime import datetime

EVOLUTION_DIR = os.path.join(os.path.dirname(__file__), 'evolution_data')
os.makedirs(EVOLUTION_DIR, exist_ok=True)

class ResidualRecord:
    """单条残差记录"""
    def __init__(self, task_id, predicted, actual, context=None):
        self.task_id = task_id
        self.predicted = predicted  # dict: {duration, quality, cost, path}
        self.actual = actual        # dict: {duration, quality, cost, path}
        self.residual = self._compute_residual()
        self.context = context or {}
        self.timestamp = datetime.now().isoformat()
    
    def _compute_residual(self):
        r = {}
        for key in set(list(self.predicted.keys()) + list(self.actual.keys())):
            p = self.predicted.get(key, 0)
            a = self.actual.get(key, 0)
            if isinstance(p, (int, float)) and isinstance(a, (int, float)):
                r[key] = {
                    'delta': a - p,
                    'ratio': a / p if p != 0 else float('inf'),
                    'direction': 'over' if a > p else 'under' if a < p else 'exact'
                }
            elif isinstance(p, str) and isinstance(a, str):
                r[key] = {
                    'match': p == a,
                    'predicted': p,
                    'actual': a
                }
        return r
    
    def to_dict(self):
        return {
            'task_id': self.task_id,
            'predicted': self.predicted,
            'actual': self.actual,
            'residual': self.residual,
            'context': self.context,
            'timestamp': self.timestamp
        }


class WeightConfig:
    """可进化的权重配置"""
    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.join(EVOLUTION_DIR, 'weights.json')
        self.weights = self._load()
    
    def _load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self._default_weights()
    
    def _default_weights(self):
        return {
            'path_selection': {
                'aggressive': 0.33, 'balanced': 0.34, 'conservative': 0.33
            },
            'node_preference': {},
            'timeout_multiplier': {
                'P0': 1.0, 'P1': 1.0, 'P2': 1.0, 'P3': 1.0
            },
            'quality_threshold': 0.7,
            'version': 1,
            'last_updated': datetime.now().isoformat()
        }
    
    def save(self):
        self.weights['last_updated'] = datetime.now().isoformat()
        self.weights['version'] = self.weights.get('version', 0) + 1
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.weights, f, ensure_ascii=False, indent=2)
    
    def adjust(self, key_path, delta):
        """按路径调整权重，如 adjust('path_selection.aggressive', 0.05)"""
        keys = key_path.split('.')
        d = self.weights
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        old = d.get(keys[-1], 0)
        d[keys[-1]] = max(0, min(1, old + delta))
        return old, d[keys[-1]]


class PatternDB:
    """模式库：从残差中提取可复用模式"""
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(EVOLUTION_DIR, 'patterns.json')
        self.patterns = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'patterns': [], 'version': 1}
    
    def save(self):
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.patterns, f, ensure_ascii=False, indent=2)
    
    def extract_pattern(self, residuals):
        """从多条残差中提取模式"""
        if len(residuals) < 3:
            return None
        
        # 检测系统性偏差
        duration_deltas = []
        for r in residuals:
            res = r.get('residual', {})
            if 'duration' in res and isinstance(res['duration'], dict):
                duration_deltas.append(res['duration'].get('delta', 0))
        
        if duration_deltas:
            avg_delta = sum(duration_deltas) / len(duration_deltas)
            if abs(avg_delta) > 0.1 * abs(sum(d for d in duration_deltas)):
                pattern = {
                    'type': 'systematic_bias',
                    'metric': 'duration',
                    'direction': 'overestimate' if avg_delta < 0 else 'underestimate',
                    'magnitude': avg_delta,
                    'confidence': min(1.0, len(duration_deltas) / 10),
                    'sample_size': len(duration_deltas),
                    'discovered_at': datetime.now().isoformat()
                }
                self.patterns['patterns'].append(pattern)
                return pattern
        return None


class ResidualEvolutionEngine:
    """残差驱动进化引擎主类"""
    
    def __init__(self):
        self.weights = WeightConfig()
        self.pattern_db = PatternDB()
        self.history_path = os.path.join(EVOLUTION_DIR, 'residual_history.jsonl')
        self.evolution_log = os.path.join(EVOLUTION_DIR, 'evolution_log.jsonl')
    
    def record_residual(self, task_id, predicted, actual, context=None):
        """记录一条残差"""
        record = ResidualRecord(task_id, predicted, actual, context)
        with open(self.history_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + '\n')
        return record
    
    def evolve(self, min_records=5):
        """基于累积残差执行一轮进化"""
        records = self._load_recent_records(min_records * 2)
        if len(records) < min_records:
            return {'evolved': False, 'reason': f'insufficient data ({len(records)}/{min_records})'}
        
        changes = []
        
        # 1. 检测路径偏好
        path_stats = {'aggressive': [], 'balanced': [], 'conservative': []}
        for r in records:
            path = r.get('actual', {}).get('path', r.get('predicted', {}).get('path', ''))
            quality = r.get('actual', {}).get('quality', 0.5)
            if path in path_stats:
                path_stats[path].append(quality)
        
        for path, qualities in path_stats.items():
            if qualities:
                avg_q = sum(qualities) / len(qualities)
                current = self.weights.weights['path_selection'].get(path, 0.33)
                adjustment = (avg_q - 0.5) * 0.1  # gentle adjustment
                old, new = self.weights.adjust(f'path_selection.{path}', adjustment)
                if abs(old - new) > 0.001:
                    changes.append({'type': 'path_weight', 'path': path, 'old': old, 'new': new})
        
        # 2. 提取模式
        pattern = self.pattern_db.extract_pattern(records)
        if pattern:
            changes.append({'type': 'pattern_discovered', 'pattern': pattern})
        
        # 3. 调整超时乘数
        for r in records:
            res = r.get('residual', {})
            ctx = r.get('context', {})
            priority = ctx.get('priority', 'P2')
            if 'duration' in res and isinstance(res['duration'], dict):
                ratio = res['duration'].get('ratio', 1.0)
                if isinstance(ratio, (int, float)) and ratio != float('inf'):
                    # 如果实际耗时经常超过预测，增加超时乘数
                    if ratio > 1.2:
                        old, new = self.weights.adjust(f'timeout_multiplier.{priority}', 0.05)
                        changes.append({'type': 'timeout_adjust', 'priority': priority, 'old': old, 'new': new})
        
        # 保存
        self.weights.save()
        self.pattern_db.save()
        
        # 记录进化日志
        evolution_entry = {
            'timestamp': datetime.now().isoformat(),
            'records_analyzed': len(records),
            'changes': changes,
            'weights_version': self.weights.weights.get('version', 0)
        }
        with open(self.evolution_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(evolution_entry, ensure_ascii=False) + '\n')
        
        return {
            'evolved': bool(changes),
            'changes': changes,
            'records_analyzed': len(records),
            'weights_version': self.weights.weights.get('version', 0)
        }
    
    def _load_recent_records(self, n):
        if not os.path.exists(self.history_path):
            return []
        records = []
        with open(self.history_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except:
                        pass
        return records[-n:]
    
    def get_status(self):
        records = self._load_recent_records(1000)
        return {
            'total_records': len(records),
            'weights_version': self.weights.weights.get('version', 0),
            'patterns_count': len(self.pattern_db.patterns.get('patterns', [])),
            'current_weights': self.weights.weights,
            'last_updated': self.weights.weights.get('last_updated', 'never')
        }


# Self-test
if __name__ == '__main__':
    engine = ResidualEvolutionEngine()
    
    # Simulate 10 task residuals
    for i in range(10):
        engine.record_residual(
            f'test-task-{i}',
            predicted={'duration': 30, 'quality': 0.8, 'path': ['aggressive','balanced','conservative'][i%3]},
            actual={'duration': 30 + (i-5)*3, 'quality': 0.7 + i*0.03, 'path': ['aggressive','balanced','conservative'][i%3]},
            context={'priority': f'P{i%4}'}
        )
    
    result = engine.evolve(min_records=5)
    status = engine.get_status()
    
    print(f"Evolution: {result['evolved']}, changes: {len(result.get('changes',[]))}")
    print(f"Status: {status['total_records']} records, v{status['weights_version']}")
    print("PASS")
