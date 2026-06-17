# -*- coding: utf-8 -*-
"""
eval_agents.py - Multi-Agent Evaluation Engine (merged from V1 Baihu)
Part of Wuxing Flywheel 2.0

Four evaluation agents provide independent dimensional assessments:
  1. Quality Agent - content depth, accuracy, completeness
  2. Risk Agent - identifies gaps, risks, blind spots  
  3. Innovation Agent - novelty, differentiation, insight value
  4. Integration Agent - cross-flywheel coherence, system fit

Each agent scores 0-10 and provides structured feedback.
Used by Metal phase for comprehensive multi-perspective validation.
"""
import json, re
from collections import defaultdict

VERSION = "2.0.0"


class QualityAgent:
    """Evaluates content depth, accuracy, completeness."""
    name = "quality"
    
    def evaluate(self, analysis_text, topic="", metadata=None):
        score = 5.0
        feedback = []
        metadata = metadata or {}
        
        # Length/depth scoring
        length = len(analysis_text)
        if length > 3000:
            score += 1.5
            feedback.append("Comprehensive depth (>3000 chars)")
        elif length > 1500:
            score += 0.8
            feedback.append("Good depth")
        elif length < 500:
            score -= 1.5
            feedback.append("Insufficient depth (<500 chars)")
        
        # Data point density
        numbers = re.findall(r'\d+\.?\d*[%％]|\$[\d.]+[BMK]?|\d+\.\d+[BMK]', analysis_text)
        if len(numbers) >= 5:
            score += 1.0
            feedback.append(f"Strong quantitative backing ({len(numbers)} data points)")
        elif len(numbers) == 0:
            score -= 1.0
            feedback.append("No quantitative data")
        
        # Structure indicators
        structure_markers = ['findings', 'recommendation', 'conclusion', 'summary',
                           '发现', '建议', '结论', '摘要', 'P0', 'P1', 'high', 'medium']
        found = sum(1 for m in structure_markers if m.lower() in analysis_text.lower())
        if found >= 3:
            score += 0.5
            feedback.append("Well-structured output")
        
        # Specificity (named entities)
        entity_patterns = [r'[A-Z][a-z]+(?:\s[A-Z][a-z]+)+', r'[A-Z]{2,}']
        entities = set()
        for p in entity_patterns:
            entities.update(re.findall(p, analysis_text[:2000]))
        if len(entities) >= 5:
            score += 0.5
            feedback.append(f"Good specificity ({len(entities)} named entities)")
        
        return {
            "agent": self.name,
            "score": round(min(max(score, 1.0), 10.0), 1),
            "feedback": feedback,
            "details": {"length": length, "data_points": len(numbers), "entities": len(entities)}
        }


class RiskAgent:
    """Identifies gaps, risks, blind spots."""
    name = "risk"
    
    def evaluate(self, analysis_text, topic="", metadata=None):
        score = 6.0
        risks = []
        
        # Risk awareness keywords (bilingual)
        risk_kw = ['risk', 'challenge', 'threat', 'limitation', 'constraint', 'barrier',
                   '风险', '挑战', '威胁', '限制', '约束', '壁垒', '不确定', '困难']
        risk_count = sum(1 for k in risk_kw if k in analysis_text.lower())
        
        if risk_count >= 4:
            score += 1.0
            risks.append(f"Strong risk awareness ({risk_count} risk indicators)")
        elif risk_count == 0:
            score -= 2.0
            risks.append("CRITICAL: No risk awareness detected")
        else:
            score += 0.3
            risks.append(f"Some risk awareness ({risk_count} indicators)")
        
        # Edge case / contingency thinking
        contingency_kw = ['if', 'unless', 'however', 'although', 'despite', 'scenario',
                         '如果', '除非', '然而', '尽管', '场景', '假设']
        contingency = sum(1 for k in contingency_kw if k in analysis_text.lower())
        if contingency >= 3:
            score += 0.5
            risks.append("Good contingency thinking")
        elif contingency == 0:
            score -= 0.5
            risks.append("Lacks contingency/scenario analysis")
        
        # Competition awareness
        comp_kw = ['competitor', 'competition', 'alternative', 'substitute', 'rival',
                  '竞争', '替代', '对手', '竞品']
        if any(k in analysis_text.lower() for k in comp_kw):
            score += 0.5
            risks.append("Competition awareness present")
        else:
            risks.append("Missing competitive analysis")
        
        # Timeline / temporal awareness
        time_kw = ['2025', '2026', '2027', '2028', '2030', 'Q1', 'Q2', 'H1', 'H2',
                  'year', 'month', 'quarter', '年', '月', '季度']
        time_count = sum(1 for k in time_kw if k in analysis_text)
        if time_count >= 2:
            score += 0.3
            risks.append("Good temporal grounding")
        
        return {
            "agent": self.name,
            "score": round(min(max(score, 1.0), 10.0), 1),
            "risks": risks,
            "details": {"risk_indicators": risk_count, "contingency": contingency, "temporal": time_count}
        }


class InnovationAgent:
    """Evaluates novelty, differentiation, insight value."""
    name = "innovation"
    
    def evaluate(self, analysis_text, topic="", metadata=None):
        score = 5.5
        insights = []
        
        # Novel concepts
        novel_kw = ['novel', 'new', 'first', 'unique', 'innovative', 'breakthrough', 'emerging',
                    '创新', '首次', '独特', '突破', '新发现', '新方法', '前沿', '领先']
        novel_count = sum(1 for k in novel_kw if k in analysis_text.lower())
        
        if novel_count >= 3:
            score += 1.5
            insights.append(f"Strong innovation signals ({novel_count})")
        elif novel_count >= 1:
            score += 0.5
            insights.append("Some novelty present")
        else:
            insights.append("Lacks novel insights")
        
        # Cross-domain thinking
        cross_kw = ['cross', 'interdisciplinary', 'analogy', 'convergence', 'synergy',
                   '跨', '类比', '融合', '交叉', '协同', '跨界']
        if any(k in analysis_text.lower() for k in cross_kw):
            score += 1.0
            insights.append("Cross-domain thinking detected")
        
        # Contrarian / non-obvious insights
        contrarian_kw = ['surprisingly', 'counter-intuitive', 'paradox', 'contrary',
                        '出人意料', '反直觉', '悖论', '相反']
        if any(k in analysis_text.lower() for k in contrarian_kw):
            score += 1.0
            insights.append("Contains contrarian/non-obvious insight")
        
        # Forward-looking
        forward_kw = ['predict', 'forecast', 'future', 'will', 'expect', 'project',
                     '预测', '预期', '未来', '展望', '趋势']
        forward_count = sum(1 for k in forward_kw if k in analysis_text.lower())
        if forward_count >= 2:
            score += 0.5
            insights.append("Good forward-looking analysis")
        
        return {
            "agent": self.name,
            "score": round(min(max(score, 1.0), 10.0), 1),
            "insights": insights,
            "details": {"novel_signals": novel_count, "forward_signals": forward_count}
        }


class IntegrationAgent:
    """Evaluates cross-flywheel coherence and system fit."""
    name = "integration"
    
    def evaluate(self, analysis_text, topic="", metadata=None):
        score = 6.0
        coherence = []
        metadata = metadata or {}
        
        # Flywheel references
        flywheel_refs = {
            'wood': ['seed', 'angle', 'diverge', '种子', '发散', '研究角度'],
            'fire': ['analysis', 'deep', 'execution', '分析', '深度', '执行'],
            'earth': ['synthesis', 'finding', 'ground truth', '合成', '发现', '土'],
            'metal': ['validate', 'adversarial', 'audit', '验证', '对抗', '审查'],
            'water': ['residual', 'knowledge', 'distill', '残差', '知识', '蒸馏'],
        }
        
        refs_found = []
        for phase, keywords in flywheel_refs.items():
            if any(k in analysis_text.lower() for k in keywords):
                refs_found.append(phase)
        
        if len(refs_found) >= 4:
            score += 1.5
            coherence.append(f"Excellent flywheel integration ({len(refs_found)}/5)")
        elif len(refs_found) >= 2:
            score += 0.5
            coherence.append(f"Partial integration ({len(refs_found)}/5)")
        else:
            score -= 0.5
            coherence.append("Low flywheel integration")
        
        # Actionability
        action_kw = ['deploy', 'build', 'implement', 'launch', 'create',
                    '部署', '建设', '实现', '上线', '发布', 'P0', 'P1']
        if sum(1 for k in action_kw if k in analysis_text.lower()) >= 2:
            score += 0.5
            coherence.append("Produces actionable output")
        
        # Multi-source evidence
        source_kw = ['according to', 'research shows', 'data indicates', 'study',
                    '研究表明', '数据显示', '根据', '报告']
        if any(k in analysis_text.lower() for k in source_kw):
            score += 0.5
            coherence.append("References external evidence")
        
        # Seed coverage check
        seed_count = metadata.get("seed_count", 0)
        if seed_count >= 3:
            score += 0.3
            coherence.append(f"Good seed utilization ({seed_count} seeds)")
        
        return {
            "agent": self.name,
            "score": round(min(max(score, 1.0), 10.0), 1),
            "coherence": coherence,
            "details": {"flywheel_refs": refs_found, "seed_count": seed_count}
        }


def run_evaluation(analysis_text, topic="", metadata=None):
    """Run all 4 agents and produce unified evaluation."""
    agents = [QualityAgent(), RiskAgent(), InnovationAgent(), IntegrationAgent()]
    
    evaluations = []
    total_score = 0
    
    for agent in agents:
        try:
            result = agent.evaluate(analysis_text, topic, metadata)
            evaluations.append(result)
            total_score += result['score']
        except Exception as e:
            evaluations.append({
                "agent": agent.name,
                "score": 5.0,
                "error": str(e)
            })
            total_score += 5.0
    
    avg_score = round(total_score / len(agents), 2)
    
    # Grade
    if avg_score >= 8.0: grade, label = "S", "卓越"
    elif avg_score >= 7.0: grade, label = "A", "优秀"
    elif avg_score >= 6.0: grade, label = "B", "良好"
    elif avg_score >= 5.0: grade, label = "C", "合格"
    else: grade, label = "D", "需改进"
    
    return {
        "agents": evaluations,
        "overall_score": avg_score,
        "grade": grade,
        "grade_label": label,
        "agent_scores": {e["agent"]: e["score"] for e in evaluations},
    }


def self_test():
    """Self-test with sample analysis."""
    sample = """The lithium battery recycling market is projected to reach $18-22B by 2026 (CAGR 20-25%).
    Key players include Redwood Materials, Li-Cycle, and Brunp Recycling. 
    Direct cathode regeneration achieves >95% capacity retention at ~40% lower cost.
    Risk: regulatory fragmentation across regions creates compliance challenges.
    Innovation: emerging solid-state battery chemistry will change recycling approaches by 2028.
    The synthesis of these findings suggests a paradigm shift from pyrometallurgical to hydrometallurgical methods."""
    
    result = run_evaluation(sample, "lithium battery recycling", {"seed_count": 4})
    print(f"eval_agents.py v{VERSION} self-test")
    print(f"  Overall: {result['overall_score']}/10 (Grade: {result['grade']}/{result['grade_label']})")
    for e in result["agents"]:
        print(f"  {e['agent']:12s}: {e['score']}/10")
        for key in ['feedback', 'risks', 'insights', 'coherence']:
            if key in e:
                for item in e[key]:
                    print(f"    - {item}")
    return True


if __name__ == "__main__":
    self_test()
