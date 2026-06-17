#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
白虎异常行为检测引擎 v2.0
Baihu Anomaly Detection Engine v2.0

功能：
1. 行为基线学习 - 学习正常行为模式
2. 实时异常检测 - 检测偏离基线的行为
3. 多维度分析 - 时间/频率/模式/关联
4. 自适应阈值 - 根据环境动态调整
5. 误报过滤 - 减少误报率
"""
import sys
import json
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, deque

sys.stdout.reconfigure(encoding='utf-8')

class AnomalyDetectionEngine:
    """
    异常行为检测引擎 - 白虎核心组件 v2.0
    """
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.baselines = {}  # 行为基线
        self.behavior_history = defaultdict(lambda: deque(maxlen=window_size))
        self.anomaly_scores = deque(maxlen=window_size)
        self.adaptive_threshold = 0.75  # 自适应阈值
        self.false_positive_rate = 0.05  # 目标误报率
        
    def learn_baseline(self, entity_id: str, behaviors: List[Dict]) -> Dict:
        """
        学习行为基线
        """
        if not behaviors:
            return {'error': 'No behaviors provided'}
        
        # 统计特征
        metrics = defaultdict(list)
        for b in behaviors:
            for key, value in b.get('metrics', {}).items():
                if isinstance(value, (int, float)):
                    metrics[key].append(value)
        
        baseline = {}
        for key, values in metrics.items():
            if values:
                baseline[key] = {
                    'mean': sum(values) / len(values),
                    'std': self._calculate_std(values),
                    'min': min(values),
                    'max': max(values),
                    'median': self._calculate_median(values),
                    'count': len(values)
                }
        
        # 时间模式
        time_patterns = self._extract_time_patterns(behaviors)
        
        # 频率模式
        freq_patterns = self._extract_frequency_patterns(behaviors)
        
        self.baselines[entity_id] = {
            'metrics': baseline,
            'time_patterns': time_patterns,
            'frequency_patterns': freq_patterns,
            'learned_at': datetime.now().isoformat(),
            'sample_count': len(behaviors)
        }
        
        return {
            'entity_id': entity_id,
            'baseline': baseline,
            'time_patterns': time_patterns,
            'frequency_patterns': freq_patterns,
            'status': 'learned'
        }
    
    def detect_anomaly(self, entity_id: str, behavior: Dict) -> Dict:
        """
        检测异常行为
        """
        baseline = self.baselines.get(entity_id)
        if not baseline:
            return {'error': f'No baseline for entity {entity_id}'}
        
        # 计算各维度异常分数
        metric_scores = self._check_metrics(behavior, baseline)
        time_score = self._check_time_pattern(behavior, baseline)
        freq_score = self._check_frequency_pattern(behavior, baseline)
        
        # 综合异常分数
        anomaly_score = self._calculate_composite_score(
            metric_scores, time_score, freq_score
        )
        
        # 自适应阈值调整
        is_anomaly = anomaly_score > self.adaptive_threshold
        
        # 更新历史
        self.anomaly_scores.append(anomaly_score)
        self.behavior_history[entity_id].append(behavior)
        
        # 动态调整阈值
        self._adjust_threshold()
        
        result = {
            'entity_id': entity_id,
            'timestamp': datetime.now().isoformat(),
            'anomaly_score': round(anomaly_score, 4),
            'threshold': round(self.adaptive_threshold, 4),
            'is_anomaly': is_anomaly,
            'details': {
                'metric_scores': metric_scores,
                'time_score': round(time_score, 4),
                'frequency_score': round(freq_score, 4)
            },
            'severity': self._get_severity(anomaly_score)
        }
        
        return result
    
    def _check_metrics(self, behavior: Dict, baseline: Dict) -> Dict:
        """检查指标异常"""
        scores = {}
        metrics = behavior.get('metrics', {})
        baseline_metrics = baseline.get('metrics', {})
        
        for key, value in metrics.items():
            if key in baseline_metrics and isinstance(value, (int, float)):
                b = baseline_metrics[key]
                mean = b['mean']
                std = b['std'] if b['std'] > 0 else 1
                
                # Z-score
                z_score = abs(value - mean) / std
                scores[key] = {
                    'value': value,
                    'expected': round(mean, 2),
                    'z_score': round(z_score, 4),
                    'anomaly': z_score > 3  # 3-sigma rule
                }
        
        return scores
    
    def _check_time_pattern(self, behavior: Dict, baseline: Dict) -> float:
        """检查时间模式异常"""
        timestamp = behavior.get('timestamp')
        if not timestamp:
            return 0.0
        
        time_patterns = baseline.get('time_patterns', {})
        if not time_patterns:
            return 0.0
        
        try:
            dt = datetime.fromisoformat(timestamp)
            hour = dt.hour
            
            # 检查是否在活跃时段
            active_hours = time_patterns.get('active_hours', [])
            if active_hours and hour not in active_hours:
                return 0.5  # 非活跃时段
            
            return 0.0
        except:
            return 0.0
    
    def _check_frequency_pattern(self, behavior: Dict, baseline: Dict) -> float:
        """检查频率模式异常"""
        freq_patterns = baseline.get('frequency_patterns', {})
        if not freq_patterns:
            return 0.0
        
        # 检查当前频率是否异常
        current_freq = behavior.get('frequency', 0)
        expected_freq = freq_patterns.get('mean_frequency', 0)
        
        if expected_freq > 0:
            ratio = current_freq / expected_freq
            if ratio > 3:  # 频率是正常3倍以上
                return min(1.0, (ratio - 1) / 2)
        
        return 0.0
    
    def _calculate_composite_score(self, metric_scores: Dict, time_score: float, freq_score: float) -> float:
        """计算综合异常分数"""
        # 指标分数平均
        metric_values = [s['z_score'] for s in metric_scores.values() if 'z_score' in s]
        metric_avg = sum(metric_values) / len(metric_values) if metric_values else 0
        
        # 加权综合 (指标60%, 时间20%, 频率20%)
        composite = (metric_avg * 0.6 + time_score * 0.2 + freq_score * 0.2)
        
        # 归一化到0-1
        return min(1.0, composite / 3)
    
    def _get_severity(self, score: float) -> str:
        """获取严重等级"""
        if score >= 0.9:
            return 'critical'
        elif score >= 0.7:
            return 'high'
        elif score >= 0.5:
            return 'medium'
        elif score >= 0.3:
            return 'low'
        return 'none'
    
    def _adjust_threshold(self):
        """自适应阈值调整"""
        if len(self.anomaly_scores) < 10:
            return
        
        # 计算近期误报率
        recent_scores = list(self.anomaly_scores)[-50:]
        flagged = sum(1 for s in recent_scores if s > self.adaptive_threshold)
        actual_anomalies = sum(1 for s in recent_scores if s > 0.8)  # 假设>0.8为真异常
        
        if actual_anomalies > 0:
            fp_rate = (flagged - actual_anomalies) / len(recent_scores)
            
            # 调整阈值
            if fp_rate > self.false_positive_rate:
                self.adaptive_threshold = min(0.95, self.adaptive_threshold + 0.05)
            elif fp_rate < self.false_positive_rate / 2:
                self.adaptive_threshold = max(0.5, self.adaptive_threshold - 0.02)
    
    def _extract_time_patterns(self, behaviors: List[Dict]) -> Dict:
        """提取时间模式"""
        hours = []
        for b in behaviors:
            ts = b.get('timestamp')
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    hours.append(dt.hour)
                except:
                    pass
        
        if hours:
            hour_counts = defaultdict(int)
            for h in hours:
                hour_counts[h] += 1
            
            # 找出活跃时段（出现频率>平均的时段）
            avg_count = len(hours) / 24
            active_hours = [h for h, c in hour_counts.items() if c > avg_count]
            
            return {
                'active_hours': sorted(active_hours),
                'peak_hour': max(hour_counts, key=hour_counts.get) if hour_counts else None
            }
        
        return {}
    
    def _extract_frequency_patterns(self, behaviors: List[Dict]) -> Dict:
        """提取频率模式"""
        if len(behaviors) < 2:
            return {}
        
        # 计算平均频率
        timestamps = []
        for b in behaviors:
            ts = b.get('timestamp')
            if ts:
                try:
                    timestamps.append(datetime.fromisoformat(ts))
                except:
                    pass
        
        if len(timestamps) > 1:
            timestamps.sort()
            intervals = [(timestamps[i+1] - timestamps[i]).total_seconds() 
                        for i in range(len(timestamps)-1)]
            
            if intervals:
                mean_interval = sum(intervals) / len(intervals)
                mean_freq = 3600 / mean_interval if mean_interval > 0 else 0  # 每小时频率
                
                return {
                    'mean_frequency': round(mean_freq, 2),
                    'mean_interval_seconds': round(mean_interval, 2)
                }
        
        return {}
    
    def _calculate_std(self, values: List[float]) -> float:
        """计算标准差"""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)
    
    def _calculate_median(self, values: List[float]) -> float:
        """计算中位数"""
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        if n == 0:
            return 0.0
        if n % 2 == 1:
            return sorted_vals[n // 2]
        return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
    
    def get_stats(self) -> Dict:
        """获取引擎统计"""
        return {
            'entities_monitored': len(self.baselines),
            'total_behaviors': sum(len(h) for h in self.behavior_history.values()),
            'anomalies_detected': sum(1 for s in self.anomaly_scores if s > self.adaptive_threshold),
            'current_threshold': round(self.adaptive_threshold, 4),
            'false_positive_target': self.false_positive_rate
        }


# 演示
if __name__ == '__main__':
    print("=== 白虎异常行为检测引擎 v2.0 ===\n")
    
    engine = AnomalyDetectionEngine(window_size=100)
    
    # 模拟学习阶段 - 正常行为
    print("🧠 学习正常行为基线...")
    normal_behaviors = []
    import random
    random.seed(42)
    
    for i in range(50):
        normal_behaviors.append({
            'timestamp': (datetime.now() - timedelta(hours=i)).isoformat(),
            'metrics': {
                'cpu_usage': random.gauss(50, 10),
                'memory_usage': random.gauss(60, 15),
                'request_count': random.gauss(100, 20),
                'error_rate': random.gauss(0.02, 0.01)
            },
            'frequency': random.gauss(10, 2)
        })
    
    result = engine.learn_baseline('node1', normal_behaviors)
    print(f"  实体: {result['entity_id']}")
    print(f"  样本数: {result.get('sample_count', 0)}")
    print(f"  基线指标: {list(result.get('baseline', {}).keys())}")
    
    # 检测正常行为
    print("\n✅ 检测正常行为...")
    normal_behavior = {
        'timestamp': datetime.now().isoformat(),
        'metrics': {
            'cpu_usage': 55,
            'memory_usage': 65,
            'request_count': 110,
            'error_rate': 0.03
        },
        'frequency': 12
    }
    
    result = engine.detect_anomaly('node1', normal_behavior)
    print(f"  异常分数: {result['anomaly_score']}")
    print(f"  是否异常: {result['is_anomaly']}")
    print(f"  严重等级: {result['severity']}")
    
    # 检测异常行为
    print("\n🚨 检测异常行为...")
    anomaly_behavior = {
        'timestamp': datetime.now().isoformat(),
        'metrics': {
            'cpu_usage': 95,  # 异常高
            'memory_usage': 90,  # 异常高
            'request_count': 300,  # 异常高
            'error_rate': 0.25  # 异常高
        },
        'frequency': 35  # 异常高
    }
    
    result = engine.detect_anomaly('node1', anomaly_behavior)
    print(f"  异常分数: {result['anomaly_score']}")
    print(f"  是否异常: {result['is_anomaly']}")
    print(f"  严重等级: {result['severity']}")
    print(f"  详情:")
    for metric, detail in result['details']['metric_scores'].items():
        print(f"    {metric}: z_score={detail['z_score']}, 异常={detail['anomaly']}")
    
    # 统计
    print("\n📊 引擎统计:")
    stats = engine.get_stats()
    print(f"  监控实体: {stats['entities_monitored']}")
    print(f"  总行为数: {stats['total_behaviors']}")
    print(f"  检测异常: {stats['anomalies_detected']}")
    print(f"  当前阈值: {stats['current_threshold']}")
    
    print("\n✅ 白虎异常行为检测引擎 v2.0 演示完成")
