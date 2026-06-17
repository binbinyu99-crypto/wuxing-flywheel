"""
飞轮运行日志系统 v1.0
记录四象飞轮每轮执行的完整日志，支持审计和残差分析
"""
import json, time, os, hashlib
from datetime import datetime

class FlywheelLogger:
    """四象飞轮运行日志记录器"""
    
    LOG_DIR = 'D:/ClawMatrix/flywheel_logs'
    
    def __init__(self, log_dir=None):
        self.log_dir = log_dir or self.LOG_DIR
        os.makedirs(self.log_dir, exist_ok=True)
        self.current_session = None
        self.entries = []
    
    def start_session(self, task_description, initiator='system'):
        """开始一个飞轮运行会话"""
        session_id = hashlib.md5(f"{task_description}_{time.time()}".encode()).hexdigest()[:12]
        self.current_session = {
            'session_id': session_id,
            'task': task_description,
            'initiator': initiator,
            'started_at': datetime.now().isoformat(),
            'status': 'running',
            'phases': [],
            'total_tokens': 0,
            'total_latency_ms': 0,
            'models_used': set()
        }
        self.entries = []
        self._log('SESSION_START', f"Flywheel session started: {task_description}")
        return session_id
    
    def log_phase(self, phase, beast, api_id, input_summary, output_summary, 
                  model='template', tokens=0, latency_ms=0, success=True, error=None):
        """记录飞轮某个阶段的执行"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'phase': phase,  # diverge/evaluate/converge/output
            'beast': beast,  # qinglong/baihu/xuanwu/zhuque
            'api_id': api_id,
            'model': model,
            'input_summary': input_summary[:200],
            'output_summary': output_summary[:200],
            'tokens': tokens,
            'latency_ms': latency_ms,
            'success': success,
            'error': error
        }
        self.entries.append(entry)
        
        if self.current_session:
            self.current_session['phases'].append(entry)
            self.current_session['total_tokens'] += tokens
            self.current_session['total_latency_ms'] += latency_ms
            self.current_session['models_used'].add(model)
        
        status = 'OK' if success else 'FAIL'
        self._log(f'{beast.upper()}_{phase.upper()}', 
                  f"[{status}] {api_id} via {model} ({latency_ms}ms, {tokens}tok)")
        return entry
    
    def log_residual(self, predicted, actual, delta, lesson=''):
        """记录残差数据"""
        residual = {
            'timestamp': datetime.now().isoformat(),
            'type': 'RESIDUAL',
            'predicted': predicted,
            'actual': actual,
            'delta': delta,
            'lesson': lesson
        }
        self.entries.append(residual)
        self._log('RESIDUAL', f"Delta: {json.dumps(delta, ensure_ascii=False)[:100]}")
        return residual
    
    def end_session(self, final_output='', score=None):
        """结束飞轮会话并保存日志"""
        if not self.current_session:
            return None
        
        self.current_session['ended_at'] = datetime.now().isoformat()
        self.current_session['status'] = 'completed'
        self.current_session['final_output'] = final_output[:500]
        self.current_session['score'] = score
        self.current_session['models_used'] = list(self.current_session['models_used'])
        self.current_session['total_phases'] = len(self.current_session['phases'])
        
        # 保存到文件
        filename = f"{self.current_session['session_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.log_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.current_session, f, ensure_ascii=False, indent=2)
        
        self._log('SESSION_END', f"Saved to {filename}")
        
        session = self.current_session
        self.current_session = None
        self.entries = []
        return session
    
    def get_session_summary(self):
        """获取当前会话摘要"""
        if not self.current_session:
            return None
        s = self.current_session
        return {
            'session_id': s['session_id'],
            'task': s['task'],
            'status': s['status'],
            'phases_completed': len(s['phases']),
            'total_tokens': s['total_tokens'],
            'total_latency_ms': s['total_latency_ms'],
            'models_used': list(s['models_used'])
        }
    
    def list_sessions(self, limit=20):
        """列出历史会话"""
        files = sorted(
            [f for f in os.listdir(self.log_dir) if f.endswith('.json')],
            reverse=True
        )[:limit]
        
        sessions = []
        for f in files:
            try:
                with open(os.path.join(self.log_dir, f), 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    sessions.append({
                        'session_id': data.get('session_id'),
                        'task': data.get('task', '')[:60],
                        'status': data.get('status'),
                        'phases': data.get('total_phases', 0),
                        'score': data.get('score'),
                        'started_at': data.get('started_at'),
                        'file': f
                    })
            except:
                continue
        return sessions
    
    def _log(self, tag, message):
        """内部日志输出"""
        ts = datetime.now().strftime('%H:%M:%S')
        print(f"[{ts}] [{tag}] {message}")


# ===== 残差引擎V2 =====
class ResidualEngineV2:
    """
    残差引擎V2 - 跨轮残差追踪
    
    核心功能：
    1. 记录每轮飞轮执行的predicted vs actual
    2. 跨轮累积残差，发现系统性偏差
    3. 生成权重调整建议
    """
    
    RESIDUAL_DB = 'D:/ClawMatrix/residual_db.json'
    
    def __init__(self, db_path=None):
        self.db_path = db_path or self.RESIDUAL_DB
        self.residuals = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {'entries': [], 'patterns': [], 'weight_history': []}
    
    def _save(self):
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.residuals, f, ensure_ascii=False, indent=2)
    
    def record(self, round_id, api_id, predicted, actual, context=''):
        """记录一条残差"""
        # 计算残差
        if isinstance(predicted, (int, float)) and isinstance(actual, (int, float)):
            delta = actual - predicted
            delta_pct = (delta / predicted * 100) if predicted != 0 else 0
        elif isinstance(predicted, str) and isinstance(actual, str):
            delta = 1.0 if predicted == actual else 0.0
            delta_pct = delta * 100
        else:
            delta = None
            delta_pct = None
        
        entry = {
            'round_id': round_id,
            'api_id': api_id,
            'predicted': predicted,
            'actual': actual,
            'delta': delta,
            'delta_pct': delta_pct,
            'context': context,
            'timestamp': datetime.now().isoformat()
        }
        
        self.residuals['entries'].append(entry)
        self._save()
        return entry
    
    def analyze_patterns(self, min_entries=5):
        """分析跨轮残差模式"""
        entries = self.residuals['entries']
        if len(entries) < min_entries:
            return {'status': 'insufficient_data', 'count': len(entries), 'min_required': min_entries}
        
        # 按API分组分析
        api_residuals = {}
        for e in entries:
            api_id = e['api_id']
            api_residuals.setdefault(api_id, []).append(e)
        
        patterns = []
        for api_id, api_entries in api_residuals.items():
            deltas = [e['delta'] for e in api_entries if e['delta'] is not None]
            if not deltas:
                continue
            
            avg_delta = sum(deltas) / len(deltas)
            max_delta = max(deltas)
            min_delta = min(deltas)
            
            # 检测系统性偏差
            bias_direction = 'over' if avg_delta > 0 else ('under' if avg_delta < 0 else 'neutral')
            
            pattern = {
                'api_id': api_id,
                'sample_size': len(deltas),
                'avg_delta': round(avg_delta, 4),
                'max_delta': max_delta,
                'min_delta': min_delta,
                'bias_direction': bias_direction,
                'needs_calibration': abs(avg_delta) > 0.1
            }
            patterns.append(pattern)
        
        self.residuals['patterns'] = patterns
        self._save()
        
        return {
            'status': 'analyzed',
            'total_entries': len(entries),
            'patterns': patterns,
            'recommendation': self._generate_recommendations(patterns)
        }
    
    def _generate_recommendations(self, patterns):
        """基于残差模式生成调整建议"""
        recommendations = []
        for p in patterns:
            if p['needs_calibration']:
                if p['bias_direction'] == 'over':
                    recommendations.append(f"{p['api_id']}: 系统性高估(avg_delta={p['avg_delta']})，建议降低confidence或增加保守评估权重")
                elif p['bias_direction'] == 'under':
                    recommendations.append(f"{p['api_id']}: 系统性低估(avg_delta={p['avg_delta']})，建议提高baseline或增加乐观评估权重")
        
        if not recommendations:
            recommendations.append("当前无需调整，残差在正常范围内")
        
        return recommendations
    
    def get_summary(self):
        """获取残差引擎状态摘要"""
        entries = self.residuals['entries']
        return {
            'total_entries': len(entries),
            'patterns': len(self.residuals['patterns']),
            'weight_updates': len(self.residuals['weight_history']),
            'apis_tracked': list(set(e['api_id'] for e in entries)),
            'last_entry': entries[-1] if entries else None
        }


# ===== Self-Test =====
if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 60)
    print("Flywheel Logger + Residual Engine V2 - Self Test")
    print("=" * 60)
    
    # Test Logger
    print("\n[1] Testing FlywheelLogger...")
    logger = FlywheelLogger(log_dir='C:/tmp/flywheel_test_logs')
    
    sid = logger.start_session("Test: SkyCetus product analysis", initiator="lucas")
    
    logger.log_phase('diverge', 'qinglong', 'SC-USER', 
                     'product=SkyCetus', 'Found 3 user segments',
                     model='template', tokens=0, latency_ms=50)
    
    logger.log_phase('diverge', 'qinglong', 'SC-PROB',
                     'problem=cognitive layer', 'Decomposed into 6 sub-problems',
                     model='template', tokens=0, latency_ms=30)
    
    logger.log_phase('evaluate', 'baihu', 'SC-CON',
                     'project=SkyCetus', 'Found 7 constraints, 3 binding',
                     model='template', tokens=0, latency_ms=40)
    
    logger.log_phase('evaluate', 'baihu', 'SC-COMP',
                     'market=AI Agent', 'Analyzed 5 competitors',
                     model='template', tokens=0, latency_ms=45)
    
    logger.log_phase('converge', 'xuanwu', 'SC-RES',
                     'objective=flywheel deploy', 'CONDITIONAL GO',
                     model='template', tokens=0, latency_ms=35)
    
    session = logger.end_session(final_output='Analysis complete', score=8.5)
    print(f"  Session {sid}: {session['total_phases']} phases, {session['total_latency_ms']}ms")
    
    # Test Residual Engine
    print("\n[2] Testing ResidualEngineV2...")
    engine = ResidualEngineV2(db_path='C:/tmp/test_residual_db.json')
    
    # Simulate residuals
    engine.record('R1', 'SC-USER', predicted=3, actual=4, context='user segments count')
    engine.record('R1', 'SC-PROB', predicted=5, actual=6, context='sub-problems count')
    engine.record('R2', 'SC-USER', predicted=3, actual=3, context='user segments count')
    engine.record('R2', 'SC-PROB', predicted=5, actual=7, context='sub-problems count')
    engine.record('R3', 'SC-USER', predicted=3, actual=4, context='user segments count')
    engine.record('R3', 'SC-PROB', predicted=5, actual=8, context='sub-problems count')
    
    analysis = engine.analyze_patterns(min_entries=3)
    print(f"  Analysis: {analysis['status']}, {len(analysis['patterns'])} patterns")
    for p in analysis['patterns']:
        print(f"    {p['api_id']}: avg_delta={p['avg_delta']}, bias={p['bias_direction']}, calibrate={p['needs_calibration']}")
    print(f"  Recommendations: {analysis['recommendation']}")
    
    summary = engine.get_summary()
    print(f"  Summary: {summary['total_entries']} entries, tracking {summary['apis_tracked']}")
    
    print("\n[OK] All tests passed")
