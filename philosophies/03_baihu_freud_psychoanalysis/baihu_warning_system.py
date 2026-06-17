#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
白虎预警系统 - 异常检测引擎
Baihu Warning System - Anomaly Detection Engine

功能：
1. 节点异常检测（心跳超时、性能下降）
2. 任务异常检测（执行超时、失败率上升）
3. 资源异常检测（内存、CPU、磁盘）
4. 安全异常检测（异常访问、权限提升）
"""
import sys
import json
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional

sys.stdout.reconfigure(encoding='utf-8')

class AnomalyDetector:
    """
    异常检测器 - 白虎核心组件
    """
    
    def __init__(self):
        self.baseline = {}
        self.alerts = []
        self.thresholds = {
            'cpu_percent': 80,
            'memory_percent': 85,
            'disk_percent': 90,
            'node_timeout': 300,  # 5分钟
            'task_timeout': 3600,  # 1小时
            'failure_rate': 0.3   # 30%
        }
    
    def check_system_resources(self) -> List[Dict]:
        """检查系统资源"""
        alerts = []
        
        # CPU
        cpu = psutil.cpu_percent(interval=1)
        if cpu > self.thresholds['cpu_percent']:
            alerts.append({
                'type': 'resource',
                'subtype': 'cpu_high',
                'severity': 'warning' if cpu < 90 else 'critical',
                'value': cpu,
                'threshold': self.thresholds['cpu_percent'],
                'timestamp': datetime.now().isoformat()
            })
        
        # Memory
        memory = psutil.virtual_memory()
        if memory.percent > self.thresholds['memory_percent']:
            alerts.append({
                'type': 'resource',
                'subtype': 'memory_high',
                'severity': 'warning' if memory.percent < 95 else 'critical',
                'value': memory.percent,
                'threshold': self.thresholds['memory_percent'],
                'timestamp': datetime.now().isoformat()
            })
        
        # Disk
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        if disk_percent > self.thresholds['disk_percent']:
            alerts.append({
                'type': 'resource',
                'subtype': 'disk_full',
                'severity': 'critical',
                'value': disk_percent,
                'threshold': self.thresholds['disk_percent'],
                'timestamp': datetime.now().isoformat()
            })
        
        return alerts
    
    def check_nodes(self, nodes: List[Dict]) -> List[Dict]:
        """检查节点状态"""
        alerts = []
        now = datetime.now()
        
        for node in nodes:
            last_seen = node.get('last_seen')
            if last_seen:
                if isinstance(last_seen, str):
                    last_seen = datetime.fromisoformat(last_seen)
                
                elapsed = (now - last_seen).total_seconds()
                if elapsed > self.thresholds['node_timeout']:
                    alerts.append({
                        'type': 'node',
                        'subtype': 'node_timeout',
                        'severity': 'critical',
                        'node_id': node.get('id'),
                        'value': elapsed,
                        'threshold': self.thresholds['node_timeout'],
                        'timestamp': now.isoformat()
                    })
        
        return alerts
    
    def check_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """检查任务状态"""
        alerts = []
        now = datetime.now()
        
        # 检查执行超时
        for task in tasks:
            if task.get('status') == 'running':
                assigned_at = task.get('assigned_at')
                if assigned_at:
                    if isinstance(assigned_at, str):
                        assigned_at = datetime.fromisoformat(assigned_at)
                    
                    elapsed = (now - assigned_at).total_seconds()
                    if elapsed > self.thresholds['task_timeout']:
                        alerts.append({
                            'type': 'task',
                            'subtype': 'task_timeout',
                            'severity': 'warning',
                            'task_id': task.get('id'),
                            'value': elapsed,
                            'threshold': self.thresholds['task_timeout'],
                            'timestamp': now.isoformat()
                        })
        
        # 检查失败率
        recent_tasks = [t for t in tasks if t.get('completed_at')]
        if len(recent_tasks) > 10:
            failed = sum(1 for t in recent_tasks if t.get('status') == 'failed')
            failure_rate = failed / len(recent_tasks)
            
            if failure_rate > self.thresholds['failure_rate']:
                alerts.append({
                    'type': 'task',
                    'subtype': 'high_failure_rate',
                    'severity': 'critical',
                    'value': failure_rate,
                    'threshold': self.thresholds['failure_rate'],
                    'timestamp': now.isoformat()
                })
        
        return alerts
    
    def generate_report(self) -> Dict:
        """生成异常报告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'total_alerts': len(self.alerts),
            'critical': sum(1 for a in self.alerts if a['severity'] == 'critical'),
            'warning': sum(1 for a in self.alerts if a['severity'] == 'warning'),
            'alerts': self.alerts,
            'recommendations': self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """生成建议"""
        recommendations = []
        
        for alert in self.alerts:
            if alert['type'] == 'resource':
                if alert['subtype'] == 'cpu_high':
                    recommendations.append('建议扩容CPU或优化任务分配')
                elif alert['subtype'] == 'memory_high':
                    recommendations.append('建议清理内存或增加内存容量')
                elif alert['subtype'] == 'disk_full':
                    recommendations.append('紧急：清理磁盘空间或扩容存储')
            
            elif alert['type'] == 'node':
                recommendations.append(f"节点{alert.get('node_id')}失联，建议检查网络或重启节点")
            
            elif alert['type'] == 'task':
                if alert['subtype'] == 'task_timeout':
                    recommendations.append(f"任务{alert.get('task_id')}超时，建议重新分配或优化执行")
                elif alert['subtype'] == 'high_failure_rate':
                    recommendations.append('失败率过高，建议检查系统稳定性或任务难度')
        
        return recommendations


# 演示
if __name__ == '__main__':
    print("=== 白虎预警系统 - 异常检测引擎 ===\n")
    
    detector = AnomalyDetector()
    
    # 检查系统资源
    print("🔍 检查系统资源...")
    resource_alerts = detector.check_system_resources()
    print(f"  发现 {len(resource_alerts)} 个资源告警")
    for alert in resource_alerts:
        print(f"  [{alert['severity']}] {alert['subtype']}: {alert['value']:.1f}%")
    
    # 模拟节点检查
    print("\n🔍 检查节点状态...")
    test_nodes = [
        {'id': 'node1', 'last_seen': (datetime.now() - timedelta(minutes=10)).isoformat()},
        {'id': 'node2', 'last_seen': datetime.now().isoformat()}
    ]
    node_alerts = detector.check_nodes(test_nodes)
    print(f"  发现 {len(node_alerts)} 个节点告警")
    for alert in node_alerts:
        print(f"  [{alert['severity']}] {alert['subtype']}: {alert['value']:.0f}s")
    
    # 收集所有告警
    detector.alerts = resource_alerts + node_alerts
    
    # 生成报告
    print("\n📊 生成异常报告...")
    report = detector.generate_report()
    print(f"  总告警: {report['total_alerts']}")
    print(f"  严重: {report['critical']}")
    print(f"  警告: {report['warning']}")
    
    if report['recommendations']:
        print("\n💡 建议:")
        for rec in report['recommendations']:
            print(f"  - {rec}")
    
    print("\n✅ 白虎预警系统演示完成")
