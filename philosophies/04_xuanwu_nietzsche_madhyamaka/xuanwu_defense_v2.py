#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xuanwu Defense Layer v2.0 - Trust Scoring Engine
玄武防御层 - 信任评分引擎
"""
import sys
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding='utf-8')

class TrustScoringEngine:
    """
    信任评分引擎 - 玄武核心组件
    
    职责：
    1. 计算节点信任分数
    2. 检测异常行为
    3. 维护信任等级
    4. 生成信任报告
    """
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self.trust_cache = {}
        self.cache_ttl = 300  # 5分钟缓存
        
        # 信任等级定义
        self.trust_levels = {
            'S': {'min_score': 90, 'label': '卓越', 'color': '#00FF00'},
            'A': {'min_score': 75, 'label': '优秀', 'color': '#7FFF00'},
            'B': {'min_score': 60, 'label': '良好', 'color': '#FFFF00'},
            'C': {'min_score': 40, 'label': '一般', 'color': '#FF7F00'},
            'D': {'min_score': 0, 'label': '风险', 'color': '#FF0000'}
        }
        
        # 权重配置
        self.weights = {
            'fulfillment_rate': 0.30,  # 履约率
            'quality_score': 0.25,     # 质量分
            'contribution_score': 0.20, # 贡献度
            'stability_score': 0.15,   # 稳定性
            'community_score': 0.10    # 社区参与
        }
    
    def calculate_trust_score(self, node_id: str, 
                             task_history: List[Dict],
                             interaction_records: List[Dict]) -> Dict:
        """
        计算节点信任分数
        
        Args:
            node_id: 节点ID
            task_history: 任务历史记录
            interaction_records: 交互记录
            
        Returns:
            信任评分报告
        """
        # 1. 计算履约率
        fulfillment_rate = self._calc_fulfillment_rate(task_history)
        
        # 2. 计算质量分
        quality_score = self._calc_quality_score(task_history)
        
        # 3. 计算贡献度
        contribution_score = self._calc_contribution_score(task_history, interaction_records)
        
        # 4. 计算稳定性
        stability_score = self._calc_stability_score(task_history)
        
        # 5. 计算社区参与
        community_score = self._calc_community_score(interaction_records)
        
        # 综合评分
        trust_score = (
            fulfillment_rate * self.weights['fulfillment_rate'] +
            quality_score * self.weights['quality_score'] +
            contribution_score * self.weights['contribution_score'] +
            stability_score * self.weights['stability_score'] +
            community_score * self.weights['community_score']
        )
        
        # 确定信任等级
        trust_level = self._get_trust_level(trust_score)
        
        # 检测风险标记
        risk_flags = self._detect_risk_flags(
            node_id, task_history, interaction_records,
            trust_score, fulfillment_rate
        )
        
        # 生成建议
        recommendations = self._generate_recommendations(
            trust_score, trust_level, risk_flags,
            fulfillment_rate, quality_score
        )
        
        report = {
            'node_id': node_id,
            'trust_score': round(trust_score, 2),
            'trust_level': trust_level,
            'trust_label': self.trust_levels[trust_level]['label'],
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                'fulfillment_rate': round(fulfillment_rate, 2),
                'quality_score': round(quality_score, 2),
                'contribution_score': round(contribution_score, 2),
                'stability_score': round(stability_score, 2),
                'community_score': round(community_score, 2)
            },
            'risk_flags': risk_flags,
            'recommendations': recommendations,
            'next_evaluation': (datetime.now() + timedelta(days=7)).isoformat()
        }
        
        # 缓存结果
        self.trust_cache[node_id] = {
            'data': report,
            'expires': time.time() + self.cache_ttl
        }
        
        return report
    
    def _calc_fulfillment_rate(self, task_history: List[Dict]) -> float:
        """计算履约率"""
        if not task_history:
            return 50.0  # 默认中等
        
        completed = sum(1 for t in task_history if t.get('status') == 'completed')
        total = len(task_history)
        
        return (completed / total) * 100 if total > 0 else 50.0
    
    def _calc_quality_score(self, task_history: List[Dict]) -> float:
        """计算质量分"""
        if not task_history:
            return 50.0
        
        quality_scores = []
        for task in task_history:
            if task.get('status') == 'completed':
                # 基于任务复杂度、按时交付、反馈评分
                complexity = task.get('complexity', 5)
                on_time = 1.0 if task.get('on_time', True) else 0.5
                feedback = task.get('feedback_score', 5)
                
                score = (complexity * 10 + on_time * 20 + feedback * 10) / 3
                quality_scores.append(min(score, 100))
        
        return sum(quality_scores) / len(quality_scores) if quality_scores else 50.0
    
    def _calc_contribution_score(self, task_history: List[Dict], 
                                interaction_records: List[Dict]) -> float:
        """计算贡献度"""
        task_contribution = len(task_history) * 2  # 每个任务2分
        interaction_contribution = len(interaction_records) * 0.5
        
        score = min(task_contribution + interaction_contribution, 100)
        return score
    
    def _calc_stability_score(self, task_history: List[Dict]) -> float:
        """计算稳定性"""
        if not task_history:
            return 50.0
        
        # 计算任务完成时间的标准差
        completion_times = []
        for task in task_history:
            if task.get('completed_at') and task.get('assigned_at'):
                try:
                    completed = datetime.fromisoformat(task['completed_at'])
                    assigned = datetime.fromisoformat(task['assigned_at'])
                    duration = (completed - assigned).total_seconds() / 3600  # hours
                    completion_times.append(duration)
                except:
                    pass
        
        if not completion_times or len(completion_times) < 2:
            return 70.0  # 默认良好
        
        # 计算变异系数 (CV = std/mean)
        mean_time = sum(completion_times) / len(completion_times)
        variance = sum((t - mean_time) ** 2 for t in completion_times) / len(completion_times)
        std = variance ** 0.5
        cv = std / mean_time if mean_time > 0 else 1
        
        # CV越小越稳定 (CV < 0.3 = 优秀, CV > 1.0 = 差)
        stability = max(0, 100 - cv * 50)
        return min(stability, 100)
    
    def _calc_community_score(self, interaction_records: List[Dict]) -> float:
        """计算社区参与分"""
        if not interaction_records:
            return 30.0  # 默认较低
        
        # 基于交互频率、帮助次数、反馈质量
        interactions = len(interaction_records)
        helps = sum(1 for r in interaction_records if r.get('type') == 'help')
        feedbacks = sum(1 for r in interaction_records if r.get('type') == 'feedback')
        
        score = interactions * 1 + helps * 3 + feedbacks * 2
        return min(score, 100)
    
    def _get_trust_level(self, score: float) -> str:
        """根据分数确定信任等级"""
        for level in ['S', 'A', 'B', 'C', 'D']:
            if score >= self.trust_levels[level]['min_score']:
                return level
        return 'D'
    
    def _detect_risk_flags(self, node_id: str, 
                          task_history: List[Dict],
                          interaction_records: List[Dict],
                          trust_score: float,
                          fulfillment_rate: float) -> List[Dict]:
        """检测风险标记"""
        flags = []
        
        # 风险1：信任分数过低
        if trust_score < 40:
            flags.append({
                'type': 'low_trust',
                'severity': 'high',
                'description': f'信任分数过低 ({trust_score:.1f})',
                'action': '限制任务分配，要求整改'
            })
        
        # 风险2：履约率下降
        if fulfillment_rate < 50:
            flags.append({
                'type': 'low_fulfillment',
                'severity': 'high',
                'description': f'履约率过低 ({fulfillment_rate:.1f}%)',
                'action': '审查任务执行情况'
            })
        
        # 风险3：长时间无活动
        if task_history:
            last_activity = max(
                (t.get('completed_at') or t.get('updated_at') for t in task_history),
                default=None
            )
            if last_activity:
                try:
                    last = datetime.fromisoformat(last_activity)
                    days_inactive = (datetime.now() - last).days
                    if days_inactive > 30:
                        flags.append({
                            'type': 'inactive',
                            'severity': 'medium',
                            'description': f'节点 inactive {days_inactive} 天',
                            'action': '发送唤醒通知'
                        })
                except:
                    pass
        
        # 风险4：异常交互模式
        if interaction_records:
            recent_complaints = sum(
                1 for r in interaction_records[-10:]
                if r.get('type') == 'complaint'
            )
            if recent_complaints >= 3:
                flags.append({
                    'type': 'complaints',
                    'severity': 'high',
                    'description': f'近期收到 {recent_complaints} 次投诉',
                    'action': '人工审查节点行为'
                })
        
        return flags
    
    def _generate_recommendations(self, trust_score: float,
                                 trust_level: str,
                                 risk_flags: List[Dict],
                                 fulfillment_rate: float,
                                 quality_score: float) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        if trust_score < 60:
            recommendations.append('提高任务完成率，确保按时交付')
        
        if fulfillment_rate < 70:
            recommendations.append('改善履约记录，减少任务放弃')
        
        if quality_score < 60:
            recommendations.append('提升任务质量，关注细节和完整性')
        
        if not risk_flags:
            recommendations.append('保持良好表现，争取提升信任等级')
        
        for flag in risk_flags:
            if flag['type'] == 'inactive':
                recommendations.append('恢复活跃参与，领取并完成任务')
            elif flag['type'] == 'complaints':
                recommendations.append('改善协作方式，减少冲突和投诉')
        
        return recommendations
    
    def get_trust_report(self, node_id: str) -> Optional[Dict]:
        """获取信任报告（带缓存）"""
        cached = self.trust_cache.get(node_id)
        if cached and time.time() < cached['expires']:
            return cached['data']
        return None
    
    def invalidate_cache(self, node_id: str):
        """使缓存失效"""
        if node_id in self.trust_cache:
            del self.trust_cache[node_id]


class SecurityAuditor:
    """
    安全审计系统 - 玄武核心组件
    
    职责：
    1. 审计操作日志
    2. 检测异常行为
    3. 合规性检查
    4. 生成审计报告
    """
    
    def __init__(self):
        self.audit_rules = self._load_audit_rules()
        self.alert_threshold = {
            'failed_login': 5,      # 5分钟内失败登录次数
            'privilege_escalation': 1,  # 权限提升
            'data_access_anomaly': 10   # 异常数据访问
        }
    
    def _load_audit_rules(self) -> List[Dict]:
        """加载审计规则"""
        return [
            {
                'id': 'AUDIT-001',
                'name': '异常登录检测',
                'description': '检测短时间内多次失败登录',
                'severity': 'high',
                'check': self._check_login_anomaly
            },
            {
                'id': 'AUDIT-002',
                'name': '权限滥用检测',
                'description': '检测越权访问和权限提升',
                'severity': 'critical',
                'check': self._check_privilege_abuse
            },
            {
                'id': 'AUDIT-003',
                'name': '数据泄露风险',
                'description': '检测异常数据访问模式',
                'severity': 'high',
                'check': self._check_data_leak
            },
            {
                'id': 'AUDIT-004',
                'name': '操作合规性',
                'description': '检查操作是否符合规范',
                'severity': 'medium',
                'check': self._check_compliance
            }
        ]
    
    def audit(self, operations: List[Dict]) -> Dict:
        """
        执行安全审计
        
        Args:
            operations: 操作日志列表
            
        Returns:
            审计报告
        """
        findings = []
        
        for rule in self.audit_rules:
            result = rule['check'](operations)
            if result:
                findings.append({
                    'rule_id': rule['id'],
                    'rule_name': rule['name'],
                    'severity': rule['severity'],
                    'description': result['description'],
                    'evidence': result.get('evidence', []),
                    'recommendation': result.get('recommendation', '立即调查')
                })
        
        # 计算合规分数
        compliance_score = self._calc_compliance_score(findings, len(operations))
        
        # 确定合规状态
        compliance_status = self._get_compliance_status(compliance_score, findings)
        
        # 生成行动项
        action_items = self._generate_action_items(findings)
        
        return {
            'audit_id': self._generate_audit_id(),
            'timestamp': datetime.now().isoformat(),
            'operations_count': len(operations),
            'findings_count': len(findings),
            'compliance_score': compliance_score,
            'compliance_status': compliance_status,
            'findings': findings,
            'action_items': action_items,
            'next_audit': (datetime.now() + timedelta(days=1)).isoformat()
        }
    
    def _check_login_anomaly(self, operations: List[Dict]) -> Optional[Dict]:
        """检查登录异常"""
        failed_logins = [
            op for op in operations[-50:]  # 最近50条
            if op.get('type') == 'login' and op.get('status') == 'failed'
        ]
        
        if len(failed_logins) >= self.alert_threshold['failed_login']:
            return {
                'description': f'检测到 {len(failed_logins)} 次失败登录',
                'evidence': [f"{op.get('timestamp')}: {op.get('details', '')}" 
                           for op in failed_logins[-5:]],
                'recommendation': '检查是否存在暴力破解攻击，考虑临时锁定账户'
            }
        return None
    
    def _check_privilege_abuse(self, operations: List[Dict]) -> Optional[Dict]:
        """检查权限滥用"""
        privilege_ops = [
            op for op in operations
            if op.get('type') in ['privilege_escalation', 'unauthorized_access']
        ]
        
        if privilege_ops:
            return {
                'description': f'检测到 {len(privilege_ops)} 次权限异常操作',
                'evidence': [f"{op.get('timestamp')}: {op.get('type')}" 
                           for op in privilege_ops],
                'recommendation': '立即审查权限配置，撤销异常权限'
            }
        return None
    
    def _check_data_leak(self, operations: List[Dict]) -> Optional[Dict]:
        """检查数据泄露风险"""
        # 检测大量数据访问
        data_access = {}
        for op in operations:
            if op.get('type') == 'data_access':
                user = op.get('user_id', 'unknown')
                data_access[user] = data_access.get(user, 0) + 1
        
        anomalies = [
            (user, count) for user, count in data_access.items()
            if count > self.alert_threshold['data_access_anomaly']
        ]
        
        if anomalies:
            return {
                'description': f'检测到异常数据访问: {len(anomalies)} 个用户',
                'evidence': [f"用户 {user}: {count} 次访问" for user, count in anomalies],
                'recommendation': '审查数据访问日志，确认是否为正常业务需求'
            }
        return None
    
    def _check_compliance(self, operations: List[Dict]) -> Optional[Dict]:
        """检查操作合规性"""
        violations = []
        
        for op in operations:
            # 检查是否缺少必要字段
            if not op.get('user_id') or not op.get('timestamp'):
                violations.append(op)
            
            # 检查时间戳是否合理
            try:
                op_time = datetime.fromisoformat(op.get('timestamp', ''))
                if op_time > datetime.now() + timedelta(minutes=5):
                    violations.append(op)
            except:
                pass
        
        if violations:
            return {
                'description': f'发现 {len(violations)} 条不合规操作记录',
                'evidence': [f"缺少字段: {op}" for op in violations[:5]],
                'recommendation': '完善操作日志规范，确保所有记录完整'
            }
        return None
    
    def _calc_compliance_score(self, findings: List[Dict], total_ops: int) -> float:
        """计算合规分数"""
        if not total_ops:
            return 100.0
        
        # 根据发现的问题严重程度扣分
        deductions = {
            'critical': 20,
            'high': 10,
            'medium': 5,
            'low': 2
        }
        
        total_deduction = sum(
            deductions.get(f['severity'], 5) for f in findings
        )
        
        return max(0, 100 - total_deduction)
    
    def _get_compliance_status(self, score: float, findings: List[Dict]) -> str:
        """确定合规状态"""
        if score >= 90 and not any(f['severity'] == 'critical' for f in findings):
            return 'compliant'
        elif score >= 70:
            return 'partial'
        else:
            return 'non_compliant'
    
    def _generate_action_items(self, findings: List[Dict]) -> List[str]:
        """生成行动项"""
        items = []
        
        for finding in findings:
            if finding['severity'] == 'critical':
                items.append(f"[紧急] {finding['rule_name']}: {finding['recommendation']}")
            elif finding['severity'] == 'high':
                items.append(f"[高优] {finding['rule_name']}: {finding['recommendation']}")
            else:
                items.append(f"[中优] {finding['rule_name']}: {finding['recommendation']}")
        
        return items
    
    def _generate_audit_id(self) -> str:
        """生成审计ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_str = hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
        return f"AUDIT-{timestamp}-{random_str}"


# 演示
if __name__ == '__main__':
    print("=== 玄武防御层 v2.0 演示 ===\n")
    
    # 信任评分演示
    print("🐢 信任评分引擎")
    trust_engine = TrustScoringEngine()
    
    sample_tasks = [
        {'status': 'completed', 'complexity': 8, 'on_time': True, 'feedback_score': 9,
         'completed_at': '2026-04-26T10:00:00', 'assigned_at': '2026-04-25T10:00:00'},
        {'status': 'completed', 'complexity': 6, 'on_time': True, 'feedback_score': 8,
         'completed_at': '2026-04-25T15:00:00', 'assigned_at': '2026-04-24T15:00:00'},
        {'status': 'completed', 'complexity': 9, 'on_time': False, 'feedback_score': 7,
         'completed_at': '2026-04-24T20:00:00', 'assigned_at': '2026-04-23T10:00:00'},
    ]
    
    sample_interactions = [
        {'type': 'help', 'timestamp': '2026-04-26T08:00:00'},
        {'type': 'feedback', 'timestamp': '2026-04-25T14:00:00'},
        {'type': 'help', 'timestamp': '2026-04-24T16:00:00'},
    ]
    
    report = trust_engine.calculate_trust_score(
        'node_lucas_001', sample_tasks, sample_interactions
    )
    
    print(f"节点: {report['node_id']}")
    print(f"信任分数: {report['trust_score']}")
    print(f"信任等级: {report['trust_level']} ({report['trust_label']})")
    print(f"指标: {json.dumps(report['metrics'], ensure_ascii=False, indent=2)}")
    print(f"风险标记: {len(report['risk_flags'])} 个")
    print(f"建议: {report['recommendations']}\n")
    
    # 安全审计演示
    print("🛡️ 安全审计系统")
    auditor = SecurityAuditor()
    
    sample_ops = [
        {'type': 'login', 'status': 'failed', 'user_id': 'user1', 
         'timestamp': '2026-04-27T06:30:00', 'details': '密码错误'},
        {'type': 'login', 'status': 'failed', 'user_id': 'user1',
         'timestamp': '2026-04-27T06:31:00', 'details': '密码错误'},
        {'type': 'login', 'status': 'failed', 'user_id': 'user1',
         'timestamp': '2026-04-27T06:32:00', 'details': '密码错误'},
        {'type': 'data_access', 'user_id': 'user2', 'timestamp': '2026-04-27T06:30:00'},
        {'type': 'data_access', 'user_id': 'user2', 'timestamp': '2026-04-27T06:31:00'},
        {'type': 'normal_op', 'user_id': 'user3', 'timestamp': '2026-04-27T06:30:00'},
    ]
    
    audit_report = auditor.audit(sample_ops)
    
    print(f"审计ID: {audit_report['audit_id']}")
    print(f"合规分数: {audit_report['compliance_score']}")
    print(f"合规状态: {audit_report['compliance_status']}")
    print(f"发现问题: {audit_report['findings_count']} 个")
    for finding in audit_report['findings']:
        print(f"  [{finding['severity']}] {finding['rule_name']}: {finding['description']}")
    print(f"行动项: {audit_report['action_items']}")
    
    print("\n✅ 玄武防御层 v2.0 演示完成")
