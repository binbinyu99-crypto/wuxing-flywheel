# -*- coding: utf-8 -*-
"""
xiangke_engine.py - 五行相克约束引擎 v1.0
实现五行相克的动态平衡机制

相克五对（五角星）：
  金克木 — 验证约束发散（验证分数低 → 限制种子数量）
  木克土 — 创新挑战现实（种子新颖度高 → 提高土的校验标准）
  土克水 — 现实约束收敛（校验残差高 → 水不能轻易收敛）
  水克火 — 认知约束执行（未知领域多 → 降低执行置信度）
  火克金 — 执行压制对抗（执行分数高 → 降低验证权重，防止过度质疑）

核心原则：相克不是消灭，是约束。任何一极过强都会被克制。
"""

import json, time

# ===== 相克规则引擎 =====

class XiangkeEngine:
    """五行相克动态平衡引擎"""
    
    # 相克关系表：{克者: 被克者}
    RELATIONS = {
        "metal": "wood",   # 金克木
        "wood": "earth",   # 木克土
        "earth": "water",  # 土克水
        "water": "fire",   # 水克火
        "fire": "metal",   # 火克金
    }
    
    # 默认参数
    DEFAULT_PARAMS = {
        "wood": {"seed_count": 15, "divergence_temp": 0.9, "weight": 1.0},
        "fire": {"execution_confidence": 1.0, "detail_level": "full", "weight": 1.0},
        "earth": {"validation_threshold": 0.5, "strictness": "normal", "weight": 1.0},
        "metal": {"validation_weight": 0.25, "challenge_depth": "standard", "weight": 1.0},
        "water": {"convergence_threshold": 0.3, "min_evidence": 2, "weight": 1.0},
    }
    
    def __init__(self):
        self.params = json.loads(json.dumps(self.DEFAULT_PARAMS))
        self.adjustments = []  # log of all adjustments
    
    def apply_constraints(self, phase_results):
        """
        Given results from completed phases, apply 相克 constraints to downstream phases.
        
        Args:
            phase_results: dict of {phase_name: {score: float, output: dict, ...}}
        
        Returns:
            dict of adjusted parameters for remaining phases
        """
        adjustments = []
        
        for attacker, defender in self.RELATIONS.items():
            if attacker not in phase_results:
                continue
            
            score = self._extract_score(phase_results[attacker])
            
            if attacker == "metal" and defender == "wood":
                adjustments.extend(self._metal_ke_wood(score, phase_results.get("metal", {})))
            
            elif attacker == "wood" and defender == "earth":
                adjustments.extend(self._wood_ke_earth(score, phase_results.get("wood", {})))
            
            elif attacker == "earth" and defender == "water":
                adjustments.extend(self._earth_ke_water(score, phase_results.get("earth", {})))
            
            elif attacker == "water" and defender == "fire":
                adjustments.extend(self._water_ke_fire(score, phase_results.get("water", {})))
            
            elif attacker == "fire" and defender == "metal":
                adjustments.extend(self._fire_ke_metal(score, phase_results.get("fire", {})))
        
        self.adjustments.extend(adjustments)
        return {
            "adjusted_params": self.params,
            "adjustments": adjustments
        }
    
    def _extract_score(self, result):
        """Extract normalized score from phase result"""
        if isinstance(result, dict):
            output = result.get("output", result)
            if isinstance(output, dict):
                for key in ["overall_score", "divergence_score", "execution_score", 
                           "grounding_score", "convergence_score", "integrity_score"]:
                    if key in output:
                        return float(output[key])
                # metal_validator format
                if "dimension_scores" in output:
                    scores = output["dimension_scores"].values()
                    if scores:
                        return sum(scores) / len(scores)
        return 0.5  # default
    
    # ===== 五对相克具体实现 =====
    
    def _metal_ke_wood(self, metal_score, metal_result):
        """金克木：验证分数低 → 约束种子发散"""
        adjustments = []
        
        if metal_score < 0.4:
            # 验证严重不通过 → 大幅限制种子
            self.params["wood"]["seed_count"] = 5
            self.params["wood"]["divergence_temp"] = 0.5
            adjustments.append({
                "rule": "金克木（强约束）",
                "trigger": f"验证分数={metal_score:.2f} < 0.4",
                "action": "种子数15→5，发散温度0.9→0.5",
                "reason": "验证器发现严重问题，需收敛种子方向避免无效发散"
            })
        elif metal_score < 0.6:
            # 有条件通过 → 适度限制
            self.params["wood"]["seed_count"] = 10
            self.params["wood"]["divergence_temp"] = 0.7
            adjustments.append({
                "rule": "金克木（适度约束）",
                "trigger": f"验证分数={metal_score:.2f} < 0.6",
                "action": "种子数15→10，发散温度0.9→0.7",
                "reason": "验证发现部分问题，适度约束发散范围"
            })
        
        # 如果有具体红旗，进一步约束
        output = metal_result.get("output", {})
        if isinstance(output, dict):
            red_flags = output.get("red_flags", [])
            if len(red_flags) > 5:
                self.params["wood"]["seed_count"] = max(3, self.params["wood"]["seed_count"] - 3)
                adjustments.append({
                    "rule": "金克木（红旗加码）",
                    "trigger": f"{len(red_flags)}个红旗",
                    "action": f"种子数再减3→{self.params['wood']['seed_count']}",
                    "reason": "红旗过多，进一步收敛"
                })
        
        return adjustments
    
    def _wood_ke_earth(self, wood_score, wood_result):
        """木克土：种子新颖度高 → 提高土的校验标准"""
        adjustments = []
        
        if wood_score > 0.8:
            self.params["earth"]["validation_threshold"] = 0.7
            self.params["earth"]["strictness"] = "strict"
            adjustments.append({
                "rule": "木克土（高标准校验）",
                "trigger": f"发散分数={wood_score:.2f} > 0.8",
                "action": "校验阈值0.5→0.7，严格模式",
                "reason": "种子高度发散，需要更严格的现实校验防止空想"
            })
        elif wood_score > 0.6:
            self.params["earth"]["validation_threshold"] = 0.6
            adjustments.append({
                "rule": "木克土（适度校验）",
                "trigger": f"发散分数={wood_score:.2f} > 0.6",
                "action": "校验阈值0.5→0.6",
                "reason": "种子较发散，适度提高校验标准"
            })
        
        return adjustments
    
    def _earth_ke_water(self, earth_score, earth_result):
        """土克水：现实校验残差高 → 水不能轻易收敛"""
        adjustments = []
        
        output = earth_result.get("output", {})
        residual = output.get("residual", 0.5) if isinstance(output, dict) else 0.5
        
        if residual > 0.7:
            self.params["water"]["convergence_threshold"] = 0.15
            self.params["water"]["min_evidence"] = 4
            adjustments.append({
                "rule": "土克水（禁止轻率收敛）",
                "trigger": f"土阶段残差={residual:.2f} > 0.7",
                "action": "收敛阈值0.3→0.15，最少证据2→4",
                "reason": "现实校验发现大量未验证信息，禁止水阶段过早下结论"
            })
        elif residual > 0.5:
            self.params["water"]["convergence_threshold"] = 0.2
            self.params["water"]["min_evidence"] = 3
            adjustments.append({
                "rule": "土克水（谨慎收敛）",
                "trigger": f"土阶段残差={residual:.2f} > 0.5",
                "action": "收敛阈值0.3→0.2，最少证据2→3",
                "reason": "现实校验有较多不确定性，水阶段需更多证据才能收敛"
            })
        
        return adjustments
    
    def _water_ke_fire(self, water_score, water_result):
        """水克火：未知领域多 → 降低执行置信度"""
        adjustments = []
        
        output = water_result.get("output", {})
        unknowns = output.get("unknown", []) if isinstance(output, dict) else []
        
        if len(unknowns) > 5 or water_score < 0.4:
            self.params["fire"]["execution_confidence"] = 0.5
            self.params["fire"]["detail_level"] = "cautious"
            adjustments.append({
                "rule": "水克火（降低执行信心）",
                "trigger": f"未知项={len(unknowns)}，收敛分={water_score:.2f}",
                "action": "执行置信度1.0→0.5，模式→谨慎",
                "reason": "认知未收敛，执行层必须标注不确定性，避免过度自信"
            })
        elif len(unknowns) > 3 or water_score < 0.6:
            self.params["fire"]["execution_confidence"] = 0.7
            adjustments.append({
                "rule": "水克火（适度降低执行信心）",
                "trigger": f"未知项={len(unknowns)}，收敛分={water_score:.2f}",
                "action": "执行置信度1.0→0.7",
                "reason": "部分领域认知不足，执行建议需标注局限"
            })
        
        return adjustments
    
    def _fire_ke_metal(self, fire_score, fire_result):
        """火克金：执行分数高 → 降低验证权重，防止过度质疑"""
        adjustments = []
        
        if fire_score > 0.8:
            self.params["metal"]["validation_weight"] = 0.15
            self.params["metal"]["challenge_depth"] = "light"
            adjustments.append({
                "rule": "火克金（压制过度质疑）",
                "trigger": f"执行分数={fire_score:.2f} > 0.8",
                "action": "验证权重0.25→0.15，质疑深度→轻度",
                "reason": "执行层数据充分、逻辑严密，验证层不应过度质疑阻碍推进"
            })
        elif fire_score > 0.7:
            self.params["metal"]["validation_weight"] = 0.20
            adjustments.append({
                "rule": "火克金（适度压制）",
                "trigger": f"执行分数={fire_score:.2f} > 0.7",
                "action": "验证权重0.25→0.20",
                "reason": "执行层质量较高，适度降低验证权重"
            })
        
        return adjustments
    
    # ===== 辅助方法 =====
    
    def get_prompt_modifiers(self, phase):
        """Generate prompt modifier string based on current constraints"""
        p = self.params.get(phase, {})
        mods = []
        
        if phase == "wood":
            if p.get("seed_count", 15) < 15:
                mods.append(f"注意：本轮种子数量限制为{p['seed_count']}个（相克约束）")
            if p.get("divergence_temp", 0.9) < 0.9:
                mods.append("注意：需要更聚焦的发散，避免天马行空")
        
        elif phase == "earth":
            if p.get("strictness") == "strict":
                mods.append("注意：严格校验模式 — 每个结论必须有2个以上数据支撑")
            if p.get("validation_threshold", 0.5) > 0.5:
                mods.append(f"注意：校验阈值提高到{p['validation_threshold']}（相克约束）")
        
        elif phase == "metal":
            if p.get("challenge_depth") == "light":
                mods.append("注意：轻度质疑模式 — 聚焦关键风险，不做全面质疑")
            if p.get("validation_weight", 0.25) < 0.25:
                mods.append(f"注意：验证权重降至{p['validation_weight']}（火克金约束）")
        
        elif phase == "fire":
            if p.get("execution_confidence", 1.0) < 1.0:
                mods.append(f"注意：执行置信度={p['execution_confidence']}，需标注不确定性")
            if p.get("detail_level") == "cautious":
                mods.append("注意：谨慎执行模式 — 每个建议需标注局限和风险")
        
        elif phase == "water":
            if p.get("convergence_threshold", 0.3) < 0.3:
                mods.append(f"注意：收敛阈值={p['convergence_threshold']}，需更多证据才能下结论")
            if p.get("min_evidence", 2) > 2:
                mods.append(f"注意：每个结论至少需要{p['min_evidence']}个独立证据支撑")
        
        return "\n".join(mods) if mods else ""
    
    def reset(self):
        """Reset to default parameters"""
        self.params = json.loads(json.dumps(self.DEFAULT_PARAMS))
        self.adjustments = []
    
    def get_balance_report(self):
        """Generate a balance report showing current state of all five phases"""
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "phases": {},
            "total_adjustments": len(self.adjustments),
            "active_constraints": []
        }
        
        for phase, params in self.params.items():
            defaults = self.DEFAULT_PARAMS[phase]
            deviations = {}
            for k, v in params.items():
                if v != defaults.get(k):
                    deviations[k] = {"current": v, "default": defaults[k]}
            
            report["phases"][phase] = {
                "params": params,
                "constrained": len(deviations) > 0,
                "deviations": deviations
            }
            
            if deviations:
                report["active_constraints"].append(phase)
        
        return report
    
    def to_dict(self):
        return {
            "params": self.params,
            "adjustments": self.adjustments,
            "balance": self.get_balance_report()
        }


# ===== Standalone test =====
if __name__ == "__main__":
    engine = XiangkeEngine()
    
    # Simulate: metal found issues → constrain wood
    test_results = {
        "metal": {
            "output": {
                "overall_score": 0.35,
                "red_flags": ["数据来源不明", "自相矛盾", "缺乏对比", "时间线不现实", "忽略竞争", "成本低估"]
            }
        },
        "fire": {
            "output": {
                "execution_score": 0.85
            }
        },
        "earth": {
            "output": {
                "residual": 0.65,
                "grounding_score": 0.55
            }
        }
    }
    
    result = engine.apply_constraints(test_results)
    
    print("=== 相克约束测试 ===\n")
    for adj in result["adjustments"]:
        print(f"[{adj['rule']}]")
        print(f"  触发: {adj['trigger']}")
        print(f"  动作: {adj['action']}")
        print(f"  原因: {adj['reason']}")
        print()
    
    print("=== Prompt修饰语 ===\n")
    for phase in ["wood", "fire", "earth", "metal", "water"]:
        mod = engine.get_prompt_modifiers(phase)
        if mod:
            print(f"[{phase}] {mod}")
    
    print(f"\n=== 平衡报告 ===")
    report = engine.get_balance_report()
    print(f"活跃约束: {report['active_constraints']}")
    print(f"总调整数: {report['total_adjustments']}")
