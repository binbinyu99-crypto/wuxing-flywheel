# -*- coding: utf-8 -*-
"""
edge_agents.py — 10 Edge Agents for Wuxing Flywheel v2
=====================================================
5 相生 (generating) edges + 5 相克 (controlling) edges = 10 intelligent transition agents.

Instead of raw text passthrough, each edge agent processes the source element's output
and produces focused, transformed input for the target element.

Architecture: 5 nodes + 10 edges + 天鲸 kernel = 16-agent cognitive system.

Usage:
    from edge_agents import EdgeAgentRegistry
    registry = EdgeAgentRegistry(call_llm_fn)
    transformed = registry.process_generation("qinglong", "zhuque", source_output, topic, round_num)
    constraint = registry.process_control("diting", "qinglong", source_output, topic, round_num)
"""

import json
import time
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor

# ─────────────────────────────────────────────────────────────
# Edge Agent Definitions
# ─────────────────────────────────────────────────────────────

SHENG_EDGES = {
    ("qinglong", "zhuque"): {
        "name": "木生火·种子激活",
        "role": "将青龙的探索种子转化为朱雀可执行的分析任务",
        "prompt": """你是「木生火」边缘智能体。
青龙（木）刚生成了一批探索种子，你需要将它们转化为朱雀（火）可以直接执行的分析任务。

你的工作：
1. 筛选最有价值的种子（去除重复、模糊、不可验证的）
2. 为每个保留种子附加执行指令（分析角度、所需证据、预期产出格式）
3. 标注优先级和依赖关系
4. 将发散思维聚焦为可执行计划

输出JSON：
{{"activated_seeds": [{{"seed_id": "s1", "title": "...", "execution_plan": "...", "priority": "high/medium/low", "evidence_needed": "..."}}],
  "dropped_seeds": [{{"seed_id": "...", "reason": "..."}}],
  "focus_recommendation": "本轮最应深入的1-2个方向"}}"""
    },
    ("zhuque", "diting"): {
        "name": "火生土·执行沉淀",
        "role": "将朱雀的分析结果整理为谛听可校验的结构化命题",
        "prompt": """你是「火生土」边缘智能体。
朱雀（火）刚完成深度分析，你需要将分析结果沉淀为谛听（土）可以校验的结构化命题。

你的工作：
1. 从朱雀的分析中提取核心论断（每个论断必须可证伪）
2. 标注每个论断的证据强度（强证据/弱证据/推测）
3. 识别隐含假设和逻辑跳跃
4. 构建校验清单

输出JSON：
{{"propositions": [{{"id": "p1", "claim": "...", "evidence_strength": "strong/weak/speculative", "hidden_assumptions": ["..."], "falsifiable_test": "如何证伪此论断"}}],
  "logic_gaps": ["..."],
  "verification_checklist": ["..."]}}"""
    },
    ("diting", "baihu"): {
        "name": "土生金·校验锻造",
        "role": "将谛听的校验结论转化为白虎的攻击靶标",
        "prompt": """你是「土生金」边缘智能体。
谛听（土）刚完成校验，你需要将校验结论转化为白虎（金）可以发起对抗攻击的靶标。

你的工作：
1. 识别谛听标记为"弱证据"或"推测"的论断——这些是最佳攻击目标
2. 找出自洽但可能错误的论断（一致性陷阱）
3. 构建反例假设
4. 标注哪些攻击最可能揭示深层问题

输出JSON：
{{"attack_targets": [{{"target_id": "t1", "proposition": "...", "weakness_type": "evidence_gap/logic_flaw/assumption_error/consensus_trap", "suggested_attack": "...", "expected_impact": "high/medium/low"}}],
  "strongest_conclusions": ["这些结论经受住了校验，不建议攻击"],
  "meta_observation": "整体分析的系统性盲点"}}"""
    },
    ("baihu", "xuanwu"): {
        "name": "金生水·对抗收敛",
        "role": "将白虎的攻击结果整理为玄武可收敛的材料",
        "prompt": """你是「金生水」边缘智能体。
白虎（金）刚完成对抗攻击，你需要将攻击结果整理为玄武（水）可以收敛的材料。

你的工作：
1. 分类攻击结果：成功攻破（需修正结论）vs 防御成功（结论更坚固）
2. 提取新发现的信息和视角
3. 识别需要下一轮深入的残差问题
4. 评估整轮认知增量

输出JSON：
{{"breached": [{{"proposition": "...", "attack_result": "...", "correction_needed": "..."}}],
  "defended": [{{"proposition": "...", "defense_summary": "..."}}],
  "new_discoveries": ["..."],
  "residual_questions": ["..."],
  "cognitive_delta": "本轮认知增量总结"}}"""
    },
    ("xuanwu", "qinglong"): {
        "name": "水生木·收敛播种",
        "role": "将玄武的收敛结论转化为下一轮青龙的种子方向",
        "prompt": """你是「水生木」边缘智能体。
玄武（水）刚完成收敛，你需要将收敛结论转化为下一轮青龙（木）的探索方向。

你的工作：
1. 从残差中提取最有价值的未解问题
2. 将已收敛结论标记为"已验证基础"——下一轮不需要重复
3. 识别需要换角度探索的方向
4. 生成下一轮种子建议

输出JSON：
{{"verified_base": ["已确认的结论，下一轮不需要重复验证"],
  "seed_directions": [{{"direction": "...", "reason": "为什么需要探索", "angle": "从什么新角度"}}],
  "priority_residuals": ["最需要解决的残差问题"],
  "round_summary": "一句话总结本轮认知进展"}}"""
    },
}

KE_EDGES = {
    ("qinglong", "diting"): {
        "name": "木克土·种子挑战",
        "role": "青龙的新种子挑战谛听的现有校验标准",
        "prompt": """你是「木克土」相克智能体。
青龙（木）的新种子可能挑战谛听（土）的现有校验框架。

你的工作：生成约束信号，提醒谛听：
1. 新种子是否引入了现有校验标准无法覆盖的维度？
2. 谛听的校验是否过于保守，可能扼杀创新种子？
3. 是否需要更新校验标准来适应新的探索方向？

输出简洁约束信号（<200字）。"""
    },
    ("zhuque", "baihu"): {
        "name": "火克金·执行约束攻击",
        "role": "朱雀的深度分析约束白虎的攻击方向",
        "prompt": """你是「火克金」相克智能体。
朱雀（火）的深度分析应约束白虎（金）的攻击方向和力度。

你的工作：生成约束信号，提醒白虎：
1. 朱雀分析中哪些结论证据充分，不应浪费攻击资源？
2. 哪些分析路径的假设最脆弱，应优先攻击？
3. 攻击应聚焦揭示盲点，而非否定已验证的分析
4. 避免过度攻击导致有价值的结论被误杀

输出简洁约束信号（<200字）。"""
    },
    ("diting", "xuanwu"): {
        "name": "土克水·校验限收敛",
        "role": "谛听的校验结论约束玄武的收敛方向",
        "prompt": """你是「土克水」相克智能体。
谛听（土）的校验结果应约束玄武（水）的收敛方向。

你的工作：生成约束信号，提醒玄武：
1. 哪些论断未通过校验，收敛时应降权或排除？
2. 哪些校验缺口意味着不应在该维度过早下结论？
3. 是否存在看似收敛但实际证据不足的方向？
4. 收敛结论的置信度应与校验结果匹配

输出简洁约束信号（<200字）。"""
    },
    ("baihu", "qinglong"): {
        "name": "金克木·攻击约束发散",
        "role": "白虎的对抗结果约束青龙下一轮的种子生成",
        "prompt": """你是「金克木」相克智能体。
白虎（金）的攻击揭示了分析弱点，应约束下一轮青龙（木）的种子生成。

你的工作：生成约束信号，提醒青龙：
1. 哪些方向已被攻破，不应继续沿此方向生成种子？
2. 哪些攻击揭示了新的盲区，应优先生成探索种子？
3. 种子生成应避免重复已被否定的假设
4. 应增加哪些防御性种子以弥补暴露的弱点？

输出简洁约束信号（<200字）。"""
    },
    ("xuanwu", "zhuque"): {
        "name": "水克火·收敛限执行",
        "role": "玄武的收敛结论约束朱雀下一轮的执行方向",
        "prompt": """你是「水克火」相克智能体。
玄武（水）的收敛结论应约束下一轮朱雀（火）的执行方向。

你的工作：生成约束信号，提醒朱雀：
1. 哪些方向已收敛为共识，不需要重复分析？
2. 哪些残差问题需要朱雀在下一轮重点攻克？
3. 执行分析的深度应聚焦在未收敛的分歧上
4. 避免在已确认的方向上浪费执行资源

输出简洁约束信号（<200字）。"""
    },
}


class EdgeAgentRegistry:
    """Registry of all 10 edge agents with execution methods."""

    def __init__(self, call_llm_fn: Callable, model_key: str = "qwen"):
        """
        call_llm_fn: function(system_prompt, user_prompt, temperature, model_key) -> {"text": str, ...}
        model_key: which model to use for edge agents (lightweight, fast)
        """
        self.call_llm = call_llm_fn
        self.model_key = model_key
        self.stats = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "errors": 0}

    def process_generation(self, source: str, target: str, source_output: str,
                           topic: str, round_num: int) -> str:
        """Process a 相生 (generating) edge: transform source output for target."""
        key = (source, target)
        if key not in SHENG_EDGES:
            return source_output  # No edge agent, pass through

        edge = SHENG_EDGES[key]
        system = edge["prompt"]
        user = f"主题：{topic}\n轮次：{round_num}\n\n=== {source} 原始输出 ===\n{source_output[:4000]}"

        result = self._call(edge["name"], system, user)
        if result:
            return result
        return source_output  # Fallback to raw passthrough

    def process_control(self, source: str, target: str, source_output: str,
                        topic: str, round_num: int) -> str:
        """Process a 相克 (controlling) edge: generate constraint signal."""
        key = (source, target)
        if key not in KE_EDGES:
            return ""

        edge = KE_EDGES[key]
        system = edge["prompt"]
        user = f"主题：{topic}\n轮次：{round_num}\n\n=== {source} 输出 ===\n{source_output[:3000]}"

        result = self._call(edge["name"], system, user)
        return result or ""

    def process_all_controls_parallel(self, element_outputs: dict,
                                      topic: str, round_num: int) -> dict:
        """Run all applicable 相克 edges in parallel, return {target: combined_signal}."""
        ke_signals = {}
        tasks = []

        for (src, tgt), edge in KE_EDGES.items():
            if src in element_outputs:
                tasks.append((src, tgt, element_outputs[src]))

        if not tasks:
            return ke_signals

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {}
            for src, tgt, output in tasks:
                f = pool.submit(self.process_control, src, tgt, output, topic, round_num)
                futures[f] = tgt

            for f in futures:
                tgt = futures[f]
                try:
                    signal = f.result(timeout=30)
                    if signal:
                        if tgt in ke_signals:
                            ke_signals[tgt] += f"\n\n{signal}"
                        else:
                            ke_signals[tgt] = signal
                except Exception:
                    self.stats["errors"] += 1

        return ke_signals

    def _call(self, edge_name: str, system: str, user: str) -> Optional[str]:
        """Make an LLM call for an edge agent."""
        try:
            t0 = time.time()
            result = self.call_llm(system, user, temperature=0.2, model_key=self.model_key)
            elapsed = int((time.time() - t0) * 1000)

            self.stats["calls"] += 1
            self.stats["tokens_in"] += result.get("tokens_in", 0)
            self.stats["tokens_out"] += result.get("tokens_out", 0)

            text = result.get("text", "")
            if text:
                preview = text[:80].replace("\n", " ")
                print(f"      [edge] {edge_name}: {result.get('tokens_out', '?')} tok, {elapsed}ms | {preview}...")
                return text
            else:
                self.stats["errors"] += 1
                print(f"      [edge] {edge_name}: FAILED ({result.get('error', 'empty')})")
                return None
        except Exception as e:
            self.stats["errors"] += 1
            print(f"      [edge] {edge_name}: ERROR ({e})")
            return None

    def get_stats(self) -> dict:
        return dict(self.stats)


# ─────────────────────────────────────────────────────────────
# Integration helper
# ─────────────────────────────────────────────────────────────

def create_edge_registry(call_llm_fn, model_key="deepseek"):
    """Factory function for engine integration."""
    return EdgeAgentRegistry(call_llm_fn, model_key=model_key)


if __name__ == "__main__":
    print(f"Edge Agents Module")
    print(f"  相生 edges: {len(SHENG_EDGES)}")
    print(f"  相克 edges: {len(KE_EDGES)}")
    print(f"  Total: {len(SHENG_EDGES) + len(KE_EDGES)}")
    print()
    for (s, t), e in SHENG_EDGES.items():
        print(f"  相生 {s} → {t}: {e['name']}")
    print()
    for (s, t), e in KE_EDGES.items():
        print(f"  相克 {s} → {t}: {e['name']}")
