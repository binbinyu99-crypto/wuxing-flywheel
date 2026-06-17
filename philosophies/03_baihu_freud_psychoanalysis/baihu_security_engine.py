#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
白虎安全策略引擎 v1.0
Baihu Security Policy Engine

功能：
1. 动态策略生成 - 基于威胁情报自动生成安全策略
2. 威胁情报分析 - 收集分析安全威胁
3. 自动响应 - 检测到威胁自动执行响应
4. 策略评估 - 评估策略有效性
"""
import sys
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional

sys.stdout.reconfigure(encoding='utf-8')

class SecurityPolicyEngine:
    """
    安全策略引擎 - 白虎核心组件
    """
    
    def __init__(self):
        self.policies = {}
        self.threat_intel = {}
        self.response_actions = {
            'block': self._action_block,
            'alert': self._action_alert,
            'quarantine': self._action_quarantine,
            'escalate': self._action_escalate
        }
        self.policy_templates = self._load_templates()
    
    def _load_templates(self) -> Dict:
        """加载策略模板"""
        return {
            'node_anomaly': {
                'name': '节点异常策略',
                'triggers': ['node_timeout', 'node_performance_degradation'],
                'actions': ['alert', 'quarantine'],
                'threshold': 0.7
            },
            'task_manipulation': {
                'name': '任务篡改策略',
                'triggers': ['task_unauthorized_modify', 'task_lux_manipulation'],
                'actions': ['block', 'alert', 'escalate'],
                'threshold': 0.9
            },
            'auth_bypass': {
                'name': '认证绕过策略',
                'triggers': ['auth_failure_spike', 'privilege_escalation'],
                'actions': ['block', 'escalate'],
                'threshold': 0.95
            },
            'resource_abuse': {
                'name': '资源滥用策略',
                'triggers': ['resource_spike', 'unauthorized_access'],
                'actions': ['alert', 'quarantine'],
                'threshold': 0.8
            }
        }
    
    def generate_policy(self, threat_type: str, context: Dict) -> Dict:
        """
        基于威胁类型和上下文生成策略
        """
        template = self.policy_templates.get(threat_type)
        if not template:
            return {'error': f'Unknown threat type: {threat_type}'}
        
        policy = {
            'policy_id': f"POL-{hashlib.md5(f'{threat_type}{datetime.now()}'.encode()).hexdigest()[:8]}",
            'name': template['name'],
            'threat_type': threat_type,
            'triggers': template['triggers'],
            'actions': template['actions'],
            'threshold': template['threshold'],
            'context': context,
            'created_at': datetime.now().isoformat(),
            'status': 'active',
            'version': '1.0'
        }
        
        self.policies[policy['policy_id']] = policy
        return policy
    
    def evaluate_threat(self, event: Dict) -> Dict:
        """
        评估威胁等级
        """
        threat_score = 0.0
        indicators = []
        
        # 分析事件特征
        if event.get('type') == 'node':
            if event.get('subtype') == 'timeout':
                threat_score += 0.3
                indicators.append('节点超时')
            elif event.get('subtype') == 'performance_drop':
                threat_score += 0.2
                indicators.append('性能下降')
        
        elif event.get('type') == 'auth':
            if event.get('subtype') == 'failure':
                threat_score += 0.4
                indicators.append('认证失败')
            elif event.get('subtype') == 'privilege_escalation':
                threat_score += 0.9
                indicators.append('权限提升')
        
        elif event.get('type') == 'task':
            if event.get('subtype') == 'lux_manipulation':
                threat_score += 0.8
                indicators.append('LUX篡改')
            elif event.get('subtype') == 'unauthorized_claim':
                threat_score += 0.7
                indicators.append('未授权领取')
        
        # 计算最终威胁等级
        threat_level = 'low'
        if threat_score >= 0.9:
            threat_level = 'critical'
        elif threat_score >= 0.7:
            threat_level = 'high'
        elif threat_score >= 0.4:
            threat_level = 'medium'
        
        return {
            'threat_score': min(threat_score, 1.0),
            'threat_level': threat_level,
            'indicators': indicators,
            'recommendation': self._get_recommendation(threat_level)
        }
    
    def _get_recommendation(self, level: str) -> str:
        """获取建议"""
        recommendations = {
            'low': '监控观察，记录日志',
            'medium': '加强监控，准备响应',
            'high': '立即响应，隔离风险',
            'critical': '紧急处理，上报人类'
        }
        return recommendations.get(level, '未知')
    
    def execute_response(self, policy_id: str, event: Dict) -> Dict:
        """
        执行响应动作
        """
        policy = self.policies.get(policy_id)
        if not policy:
            return {'error': f'Policy not found: {policy_id}'}
        
        results = []
        for action in policy['actions']:
            handler = self.response_actions.get(action)
            if handler:
                result = handler(event)
                results.append({
                    'action': action,
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                })
        
        return {
            'policy_id': policy_id,
            'actions_executed': len(results),
            'results': results,
            'status': 'completed'
        }
    
    def _action_block(self, event: Dict) -> str:
        """阻断动作"""
        target = event.get('source', 'unknown')
        return f"已阻断: {target}"
    
    def _action_alert(self, event: Dict) -> str:
        """告警动作"""
        return f"告警: {event.get('type')}-{event.get('subtype')}"
    
    def _action_quarantine(self, event: Dict) -> str:
        """隔离动作"""
        target = event.get('source', 'unknown')
        return f"已隔离: {target}"
    
    def _action_escalate(self, event: Dict) -> str:
        """升级动作"""
        return "已升级至人类处理"
    
    def get_policy_stats(self) -> Dict:
        """获取策略统计"""
        return {
            'total_policies': len(self.policies),
            'active': sum(1 for p in self.policies.values() if p['status'] == 'active'),
            'templates': len(self.policy_templates),
            'last_updated': datetime.now().isoformat()
        }


# 演示
if __name__ == '__main__':
    print("=== 白虎安全策略引擎 v1.0 ===\n")
    
    engine = SecurityPolicyEngine()
    
    # 生成策略
    print("🛡️ 生成安全策略...")
    policy = engine.generate_policy('node_anomaly', {
        'target': 'all_nodes',
        'timeout_threshold': 300
    })
    print(f"  策略ID: {policy['policy_id']}")
    print(f"  名称: {policy['name']}")
    print(f"  触发器: {', '.join(policy['triggers'])}")
    print(f"  动作: {', '.join(policy['actions'])}")
    
    # 评估威胁
    print("\n🔍 评估威胁事件...")
    test_events = [
        {'type': 'node', 'subtype': 'timeout', 'source': 'node1'},
        {'type': 'auth', 'subtype': 'privilege_escalation', 'source': 'user_x'},
        {'type': 'task', 'subtype': 'lux_manipulation', 'source': 'task_123'}
    ]
    
    for event in test_events:
        result = engine.evaluate_threat(event)
        print(f"  [{result['threat_level'].upper()}] {event['type']}-{event['subtype']}")
        print(f"    分数: {result['threat_score']:.2f}")
        print(f"    指标: {', '.join(result['indicators'])}")
        print(f"    建议: {result['recommendation']}")
    
    # 执行响应
    print("\n⚡ 执行响应动作...")
    response = engine.execute_response(policy['policy_id'], test_events[0])
    print(f"  执行动作数: {response['actions_executed']}")
    for result in response['results']:
        print(f"    {result['action']}: {result['result']}")
    
    # 统计
    print("\n📊 策略统计:")
    stats = engine.get_policy_stats()
    print(f"  总策略: {stats['total_policies']}")
    print(f"  活跃: {stats['active']}")
    print(f"  模板: {stats['templates']}")
    
    print("\n✅ 白虎安全策略引擎演示完成")
