
"""
飞轮超时机制设计 (Flywheel Timeout Manager)
与task_reclaim.py集成，提供飞轮级别的超时管理

核心: 飞轮阶段超时 + 整体飞轮超时 + 自动降级 + 告警
"""
import json, os, time
from datetime import datetime

class FlywheelTimeoutManager:
    """飞轮超时管理器"""
    
    # AI时代超时配置 (Robin 2026-04-25)
    STAGE_TIMEOUTS = {
        'qinglong': 300,   # 5分钟（发散阶段）
        'baihu': 240,      # 4分钟（评估阶段）
        'xuanwu': 300,     # 5分钟（收敛阶段）
        'zhuque': 180,     # 3分钟（输出阶段）
    }
    
    PRIORITY_MULTIPLIERS = {
        'P0': 0.67,  # 20min overall → stages compress
        'P1': 1.0,   # 30min overall → normal
        'P2': 1.5,   # 45min overall → relaxed
        'P3': 2.0,   # 1hr overall → generous
    }
    
    OVERALL_TIMEOUTS = {
        'P0': 1200,   # 20分钟
        'P1': 1800,   # 30分钟
        'P2': 2700,   # 45分钟
        'P3': 3600,   # 1小时
    }
    
    def __init__(self):
        self.active_timers = {}
        self.timeout_log = []
    
    def start_flywheel_timer(self, flywheel_id, priority='P2'):
        """启动飞轮计时器"""
        multiplier = self.PRIORITY_MULTIPLIERS.get(priority, 1.0)
        overall = self.OVERALL_TIMEOUTS.get(priority, 2700)
        
        timer = {
            'flywheel_id': flywheel_id,
            'priority': priority,
            'start_time': time.time(),
            'overall_timeout': overall,
            'stage_timeouts': {k: int(v * multiplier) for k, v in self.STAGE_TIMEOUTS.items()},
            'current_stage': None,
            'stage_start': None,
            'warnings_sent': [],
            'status': 'running'
        }
        self.active_timers[flywheel_id] = timer
        return timer
    
    def enter_stage(self, flywheel_id, stage_beast):
        """进入新阶段"""
        timer = self.active_timers.get(flywheel_id)
        if not timer:
            return None
        timer['current_stage'] = stage_beast
        timer['stage_start'] = time.time()
        return timer
    
    def check_timeout(self, flywheel_id):
        """检查超时状态"""
        timer = self.active_timers.get(flywheel_id)
        if not timer or timer['status'] != 'running':
            return {'timed_out': False, 'reason': 'no active timer'}
        
        now = time.time()
        elapsed_overall = now - timer['start_time']
        
        result = {
            'flywheel_id': flywheel_id,
            'elapsed_overall': round(elapsed_overall, 1),
            'overall_timeout': timer['overall_timeout'],
            'overall_remaining': round(timer['overall_timeout'] - elapsed_overall, 1),
            'timed_out': False,
            'warnings': []
        }
        
        # Check overall timeout
        if elapsed_overall >= timer['overall_timeout']:
            result['timed_out'] = True
            result['reason'] = 'overall_timeout'
            timer['status'] = 'timed_out'
            self.timeout_log.append({
                'flywheel_id': flywheel_id,
                'type': 'overall',
                'elapsed': elapsed_overall,
                'timestamp': datetime.now().isoformat()
            })
            return result
        
        # Check 80% warning
        if elapsed_overall >= timer['overall_timeout'] * 0.8 and '80%' not in timer['warnings_sent']:
            result['warnings'].append('80% of overall timeout reached')
            timer['warnings_sent'].append('80%')
        
        # Check stage timeout
        if timer['current_stage'] and timer['stage_start']:
            stage_elapsed = now - timer['stage_start']
            stage_timeout = timer['stage_timeouts'].get(timer['current_stage'], 300)
            result['stage_elapsed'] = round(stage_elapsed, 1)
            result['stage_timeout'] = stage_timeout
            
            if stage_elapsed >= stage_timeout:
                result['timed_out'] = True
                result['reason'] = f'stage_timeout ({timer["current_stage"]})'
                timer['status'] = 'stage_timed_out'
                self.timeout_log.append({
                    'flywheel_id': flywheel_id,
                    'type': 'stage',
                    'stage': timer['current_stage'],
                    'elapsed': stage_elapsed,
                    'timestamp': datetime.now().isoformat()
                })
        
        return result
    
    def get_degradation_strategy(self, flywheel_id):
        """获取超时降级策略"""
        timer = self.active_timers.get(flywheel_id)
        if not timer:
            return None
        
        strategies = {
            'stage_timed_out': {
                'action': 'skip_stage',
                'description': '跳过当前阶段，使用默认模板结果',
                'fallback': 'template_mode'
            },
            'overall_timeout': {
                'action': 'emergency_output',
                'description': '立即用已有结果生成输出',
                'fallback': 'partial_result'
            },
            'running': {
                'action': 'continue',
                'description': '正常继续',
                'fallback': None
            }
        }
        
        return strategies.get(timer['status'], strategies['running'])
    
    def complete_flywheel(self, flywheel_id):
        """完成飞轮计时"""
        timer = self.active_timers.get(flywheel_id)
        if timer:
            timer['status'] = 'completed'
            timer['end_time'] = time.time()
            timer['total_duration'] = timer['end_time'] - timer['start_time']
        return timer
    
    def get_stats(self):
        completed = [t for t in self.active_timers.values() if t['status'] == 'completed']
        return {
            'active': sum(1 for t in self.active_timers.values() if t['status'] == 'running'),
            'completed': len(completed),
            'timed_out': len(self.timeout_log),
            'avg_duration': round(sum(t.get('total_duration',0) for t in completed)/max(1,len(completed)), 1)
        }


# Self-test
if __name__ == '__main__':
    import sys; sys.stdout.reconfigure(encoding='utf-8')
    mgr = FlywheelTimeoutManager()
    
    # Start a P1 flywheel
    timer = mgr.start_flywheel_timer('fw-test-001', 'P1')
    print(f"Timer started: P1, overall={timer['overall_timeout']}s")
    print(f"Stage timeouts: {timer['stage_timeouts']}")
    
    mgr.enter_stage('fw-test-001', 'qinglong')
    check = mgr.check_timeout('fw-test-001')
    print(f"Check: timed_out={check['timed_out']}, remaining={check['overall_remaining']}s")
    
    strategy = mgr.get_degradation_strategy('fw-test-001')
    print(f"Strategy: {strategy['action']} - {strategy['description']}")
    
    mgr.complete_flywheel('fw-test-001')
    stats = mgr.get_stats()
    print(f"Stats: {stats}")
    print("PASS")
