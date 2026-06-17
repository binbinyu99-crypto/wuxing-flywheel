#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄武认知结构化系统 - Knowledge沉淀引擎
Xuanwu Cognitive Structuring System

职责：
1. 残差提取与结构化
2. 知识沉淀与归档
3. 认知模式识别
4. 经验库建设
"""
import sys
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

sys.stdout.reconfigure(encoding='utf-8')

@dataclass
class CognitivePattern:
    """认知模式"""
    pattern_id: str
    pattern_type: str  # 'success', 'failure', 'insight', 'warning'
    context: str
    trigger: str
    action: str
    result: str
    residual: str  # 残差 = 预期 vs 实际的差异
    confidence: float
    frequency: int
    created_at: str
    last_seen: str

@dataclass
class KnowledgeNode:
    """知识节点"""
    node_id: str
    category: str  # 'tech', 'business', 'process', 'insight'
    title: str
    content: str
    source: str  # 来源任务/项目
    tags: List[str]
    related_patterns: List[str]
    confidence: float
    created_at: str
    updated_at: str

class ResidualExtractor:
    """
    残差提取器 - 玄武核心组件
    
    从执行结果中提取残差（预期与实际的差异），
    形成可学习的认知模式。
    """
    
    def __init__(self):
        self.patterns: Dict[str, CognitivePattern] = {}
        self.knowledge_base: Dict[str, KnowledgeNode] = {}
        self.experience_db = []
    
    def extract_residual(self, 
                        task_id: str,
                        expected: Dict[str, Any],
                        actual: Dict[str, Any],
                        context: str) -> Dict:
        """
        提取残差
        
        Args:
            task_id: 任务ID
            expected: 预期结果
            actual: 实际结果
            context: 执行上下文
            
        Returns:
            残差分析报告
        """
        # 1. 计算差异
        differences = self._calc_differences(expected, actual)
        
        # 2. 识别模式
        pattern = self._identify_pattern(differences, context)
        
        # 3. 评估影响
        impact = self._assess_impact(differences)
        
        # 4. 生成学习点
        learnings = self._extract_learnings(differences, pattern)
        
        # 5. 存储到经验库
        self._store_experience(task_id, expected, actual, differences, pattern)
        
        return {
            'task_id': task_id,
            'timestamp': datetime.now().isoformat(),
            'differences': differences,
            'pattern': pattern,
            'impact': impact,
            'learnings': learnings,
            'confidence': self._calc_confidence(differences)
        }
    
    def _calc_differences(self, expected: Dict, actual: Dict) -> List[Dict]:
        """计算预期与实际的差异"""
        differences = []
        
        all_keys = set(expected.keys()) | set(actual.keys())
        
        for key in all_keys:
            exp_val = expected.get(key)
            act_val = actual.get(key)
            
            if exp_val != act_val:
                diff_type = 'missing' if act_val is None else 'extra' if exp_val is None else 'mismatch'
                
                differences.append({
                    'field': key,
                    'type': diff_type,
                    'expected': exp_val,
                    'actual': act_val,
                    'severity': self._diff_severity(exp_val, act_val)
                })
        
        return differences
    
    def _diff_severity(self, expected, actual) -> str:
        """评估差异严重程度"""
        if expected is None or actual is None:
            return 'high'
        
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            if expected == 0:
                return 'high' if actual != 0 else 'low'
            deviation = abs(actual - expected) / abs(expected)
            if deviation > 0.5:
                return 'high'
            elif deviation > 0.2:
                return 'medium'
            return 'low'
        
        return 'medium'
    
    def _identify_pattern(self, differences: List[Dict], context: str) -> Optional[str]:
        """识别认知模式"""
        if not differences:
            return None
        
        # 基于差异特征识别模式
        severity_counts = {'high': 0, 'medium': 0, 'low': 0}
        for d in differences:
            severity_counts[d['severity']] = severity_counts.get(d['severity'], 0) + 1
        
        if severity_counts['high'] > 2:
            return 'systematic_failure'
        elif severity_counts['medium'] > 3:
            return 'partial_mismatch'
        elif severity_counts['low'] > 5:
            return 'minor_deviation'
        elif any(d['type'] == 'missing' for d in differences):
            return 'incomplete_execution'
        else:
            return 'unexpected_result'
    
    def _assess_impact(self, differences: List[Dict]) -> Dict:
        """评估影响"""
        severity_scores = {'high': 3, 'medium': 2, 'low': 1}
        total_score = sum(severity_scores.get(d['severity'], 1) for d in differences)
        
        if total_score >= 10:
            level = 'critical'
        elif total_score >= 5:
            level = 'significant'
        elif total_score >= 2:
            level = 'moderate'
        else:
            level = 'minor'
        
        return {
            'level': level,
            'score': total_score,
            'affected_areas': list(set(d['field'] for d in differences))
        }
    
    def _extract_learnings(self, differences: List[Dict], pattern: Optional[str]) -> List[str]:
        """提取学习点"""
        learnings = []
        
        if pattern == 'systematic_failure':
            learnings.append('存在系统性问题，需要重新审视基础假设')
            learnings.append('建议进行根因分析，找出失败模式')
        
        elif pattern == 'partial_mismatch':
            learnings.append('部分结果不符合预期，需要调整执行策略')
            learnings.append('建议增加验证步骤')
        
        elif pattern == 'minor_deviation':
            learnings.append('结果在可接受范围内，但仍有优化空间')
        
        elif pattern == 'incomplete_execution':
            learnings.append('执行不完整，需要检查流程覆盖度')
        
        # 针对具体差异的学习点
        for diff in differences:
            if diff['type'] == 'missing':
                learnings.append(f"'{diff['field']}' 未被处理，需要补充")
            elif diff['type'] == 'extra':
                learnings.append(f"出现了未预期的 '{diff['field']}'，需要评估影响")
        
        return learnings
    
    def _calc_confidence(self, differences: List[Dict]) -> float:
        """计算置信度"""
        if not differences:
            return 1.0
        
        severity_weights = {'high': 0.3, 'medium': 0.6, 'low': 0.9}
        weights = [severity_weights.get(d['severity'], 0.5) for d in differences]
        
        return sum(weights) / len(weights) if weights else 0.5
    
    def _store_experience(self, task_id, expected, actual, differences, pattern):
        """存储到经验库"""
        experience = {
            'task_id': task_id,
            'timestamp': datetime.now().isoformat(),
            'pattern': pattern,
            'differences_count': len(differences),
            'severity_distribution': {
                'high': sum(1 for d in differences if d['severity'] == 'high'),
                'medium': sum(1 for d in differences if d['severity'] == 'medium'),
                'low': sum(1 for d in differences if d['severity'] == 'low')
            }
        }
        self.experience_db.append(experience)
    
    def get_pattern_stats(self) -> Dict:
        """获取模式统计"""
        if not self.experience_db:
            return {}
        
        pattern_counts = {}
        for exp in self.experience_db:
            p = exp['pattern'] or 'unknown'
            pattern_counts[p] = pattern_counts.get(p, 0) + 1
        
        total = len(self.experience_db)
        return {
            'total_experiences': total,
            'pattern_distribution': {
                k: {'count': v, 'percentage': round(v/total*100, 1)}
                for k, v in pattern_counts.items()
            },
            'recent_trend': self._calc_trend()
        }
    
    def _calc_trend(self) -> str:
        """计算趋势"""
        if len(self.experience_db) < 10:
            return 'insufficient_data'
        
        recent = self.experience_db[-10:]
        recent_high = sum(e['severity_distribution']['high'] for e in recent)
        
        older = self.experience_db[-20:-10]
        older_high = sum(e['severity_distribution']['high'] for e in older)
        
        if recent_high < older_high:
            return 'improving'
        elif recent_high > older_high:
            return 'degrading'
        return 'stable'


class Knowledge沉淀Engine:
    """
    知识沉淀引擎 - 将认知模式转化为可复用知识
    """
    
    def __init__(self):
        self.knowledge_graph = {}
        self.category_index = {}
    
    def 沉淀_knowledge(self, 
                     source: str,
                     category: str,
                     title: str,
                     content: str,
                     tags: List[str],
                     related_tasks: List[str]) -> KnowledgeNode:
        """
        沉淀知识
        
        Args:
            source: 来源
            category: 类别
            title: 标题
            content: 内容
            tags: 标签
            related_tasks: 相关任务
            
        Returns:
            知识节点
        """
        node_id = self._generate_node_id()
        
        node = KnowledgeNode(
            node_id=node_id,
            category=category,
            title=title,
            content=content,
            source=source,
            tags=tags,
            related_patterns=[],
            confidence=0.8,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        # 存储到知识图谱
        self.knowledge_graph[node_id] = node
        
        # 更新分类索引
        if category not in self.category_index:
            self.category_index[category] = []
        self.category_index[category].append(node_id)
        
        return node
    
    def search_knowledge(self, 
                        query: str,
                        category: Optional[str] = None,
                        tags: Optional[List[str]] = None) -> List[KnowledgeNode]:
        """
        搜索知识
        
        Args:
            query: 搜索关键词
            category: 类别过滤
            tags: 标签过滤
            
        Returns:
            匹配的知识节点列表
        """
        results = []
        query_lower = query.lower()
        
        for node in self.knowledge_graph.values():
            # 类别过滤
            if category and node.category != category:
                continue
            
            # 标签过滤
            if tags and not any(t in node.tags for t in tags):
                continue
            
            # 内容匹配
            if (query_lower in node.title.lower() or 
                query_lower in node.content.lower() or
                any(query_lower in t.lower() for t in node.tags)):
                results.append(node)
        
        # 按置信度排序
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        return results
    
    def get_knowledge_summary(self, category: Optional[str] = None) -> Dict:
        """获取知识摘要"""
        nodes = list(self.knowledge_graph.values())
        
        if category:
            node_ids = self.category_index.get(category, [])
            nodes = [self.knowledge_graph[nid] for nid in node_ids]
        
        if not nodes:
            return {'count': 0, 'categories': []}
        
        # 统计
        categories = {}
        for node in nodes:
            cat = node.category
            if cat not in categories:
                categories[cat] = {'count': 0, 'avg_confidence': 0}
            categories[cat]['count'] += 1
            categories[cat]['avg_confidence'] += node.confidence
        
        for cat in categories:
            categories[cat]['avg_confidence'] /= categories[cat]['count']
            categories[cat]['avg_confidence'] = round(categories[cat]['avg_confidence'], 2)
        
        return {
            'total_nodes': len(nodes),
            'categories': categories,
            'avg_confidence': round(sum(n.confidence for n in nodes) / len(nodes), 2),
            'recent_nodes': [
                {'id': n.node_id, 'title': n.title, 'category': n.category}
                for n in sorted(nodes, key=lambda x: x.created_at, reverse=True)[:5]
            ]
        }
    
    def _generate_node_id(self) -> str:
        """生成节点ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_str = hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
        return f"KN-{timestamp}-{random_str}"


# 演示
if __name__ == '__main__':
    print("=== 玄武认知结构化系统演示 ===\n")
    
    # 残差提取演示
    print("🔍 残差提取器")
    extractor = ResidualExtractor()
    
    # 模拟任务执行结果
    expected = {
        'status': 'completed',
        'quality_score': 85,
        'delivery_time': 24,  # hours
        'bug_count': 0,
        'test_coverage': 80
    }
    
    actual = {
        'status': 'completed',
        'quality_score': 72,
        'delivery_time': 36,
        'bug_count': 3,
        'test_coverage': 65
    }
    
    residual = extractor.extract_residual(
        task_id='task_001',
        expected=expected,
        actual=actual,
        context='API开发任务'
    )
    
    print(f"任务: {residual['task_id']}")
    print(f"模式: {residual['pattern']}")
    print(f"影响: {residual['impact']['level']} (分数: {residual['impact']['score']})")
    print(f"差异数: {len(residual['differences'])}")
    print("差异详情:")
    for diff in residual['differences']:
        print(f"  [{diff['severity']}] {diff['field']}: 预期={diff['expected']}, 实际={diff['actual']}")
    print(f"学习点: {residual['learnings']}")
    print(f"置信度: {residual['confidence']:.2f}\n")
    
    # 模式统计
    stats = extractor.get_pattern_stats()
    print("模式统计:", json.dumps(stats, ensure_ascii=False, indent=2))
    
    # 知识沉淀演示
    print("\n📚 知识沉淀引擎")
    kb = Knowledge沉淀Engine()
    
    # 沉淀几条知识
    kb.沉淀_knowledge(
        source='task_001',
        category='tech',
        title='API开发最佳实践',
        content='API开发需要注意：1. 提前定义接口规范 2. 增加测试覆盖率 3. 预留缓冲时间',
        tags=['api', 'development', 'best-practice'],
        related_tasks=['task_001']
    )
    
    kb.沉淀_knowledge(
        source='task_002',
        category='process',
        title='任务估算方法',
        content='任务估算应采用三点估算法：乐观、悲观、最可能，并增加20%缓冲',
        tags=['estimation', 'planning', 'process'],
        related_tasks=['task_002']
    )
    
    # 搜索知识
    results = kb.search_knowledge('API')
    print(f"\n搜索 'API': 找到 {len(results)} 条知识")
    for r in results:
        print(f"  [{r.category}] {r.title}")
    
    # 知识摘要
    summary = kb.get_knowledge_summary()
    print(f"\n知识库摘要:")
    print(f"  总节点: {summary['total_nodes']}")
    print(f"  分类: {list(summary['categories'].keys())}")
    print(f"  平均置信度: {summary['avg_confidence']}")
    
    print("\n✅ 玄武认知结构化系统演示完成")
