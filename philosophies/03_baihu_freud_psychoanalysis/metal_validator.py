# -*- coding: utf-8 -*-
"""
metal_validator.py - 金飞轮·白虎对抗验证器 v1.0
五行飞轮核心组件：对分析结论进行多维度对抗性验证

相克关系：金克木（对抗发散）、火克金（执行压制对抗）
输入：任意飞轮阶段的分析输出
输出：验证报告 + 风险标记 + 置信度评分
"""

import json, re, subprocess, sys, time, os

# ===== LLM调用（复用CaaS的curl方式，解决Windows SSL问题）=====
MINIMAX_KEY = "sk-cp-wBP8BgBJbLsGCUshk0x5oYKbiydygx-RMk0iJDhANE6epg6gMnRBRg5hPN1eioB3PURgoeEiv7o2kLE7vOqibkLG1_3daWsmo-7kkkVxS4t7guHj7exDGwo"
MINIMAX_URL = "https://api.minimaxi.com/anthropic/v1/messages"
MINIMAX_MODEL = "MiniMax-M2.7"

def call_llm(prompt, max_tokens=3000, temperature=0.7):
    """Call MiniMax via curl subprocess (Windows SSL workaround)"""
    payload = {
        "model": MINIMAX_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "thinking": {"type": "enabled", "budget_tokens": 300},
        "messages": [{"role": "user", "content": prompt}]
    }
    
    payload_file = os.path.join(os.environ.get("TEMP", "C:\\tmp"), "_metal_payload.json")
    with open(payload_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    
    cmd = [
        "curl", "-s", "-X", "POST", MINIMAX_URL,
        "-H", f"Authorization: Bearer {MINIMAX_KEY}",
        "-H", "Content-Type: application/json",
        "-d", f"@{payload_file}",
        "--max-time", "120"
    ]
    
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=130, encoding="utf-8")
        if r.returncode != 0:
            return f"[LLM_ERROR] curl failed: {r.stderr[:200]}"
        
        resp = json.loads(r.stdout)
        for block in resp.get("content", []):
            if block.get("type") == "text":
                return block["text"]
        return "[LLM_ERROR] No text block in response"
    except Exception as e:
        return f"[LLM_ERROR] {str(e)[:200]}"
    finally:
        try:
            os.remove(payload_file)
        except:
            pass


# ===== 验证维度 =====

VALIDATION_DIMENSIONS = {
    "data_integrity": {
        "name": "数据完整性",
        "weight": 0.25,
        "prompt": """你是白虎·数据审计官。严格审查以下分析中的数据引用：

分析内容：
{content}

审查要求：
1. 找出所有具体数据点（数字、百分比、金额、日期）
2. 判断每个数据点的来源可靠性（A=官方/学术/上市公司公告, B=行业报告/媒体, C=推测/无来源, D=明显错误）
3. 标记任何自相矛盾的数据
4. 标记任何"看起来像编造"的精确数字

输出纯JSON：
{{"data_points": [{{"value": "...", "context": "...", "reliability": "A/B/C/D", "issue": "..."}}], "integrity_score": 0.0-1.0, "red_flags": ["..."]}}"""
    },
    
    "logic_consistency": {
        "name": "逻辑一致性",
        "weight": 0.25,
        "prompt": """你是白虎·逻辑审判官。检查以下分析的推理链条：

分析内容：
{content}

审查要求：
1. 提取核心论证链（前提→推理→结论）
2. 找出逻辑跳跃（结论不从前提得出）
3. 找出循环论证
4. 找出幸存者偏差或确认偏差
5. 检查"相关性≠因果性"的错误

输出纯JSON：
{{"argument_chains": [{{"premise": "...", "conclusion": "...", "valid": true/false, "fallacy": "..."}}], "consistency_score": 0.0-1.0, "logical_gaps": ["..."]}}"""
    },
    
    "counter_evidence": {
        "name": "反面证据",
        "weight": 0.25,
        "prompt": """你是白虎·魔鬼代言人。对以下分析提出最强有力的反驳：

分析内容：
{content}

要求：
1. 找出3-5个最可能推翻核心结论的反面论据
2. 提出"如果X发生，整个分析就崩塌"的黑天鹅场景
3. 列举历史上类似乐观分析最终失败的案例
4. 标记"作者可能故意忽略"的不利信息

输出纯JSON：
{{"counter_arguments": [{{"point": "...", "strength": "强/中/弱", "if_true_impact": "..."}}], "black_swans": ["..."], "historical_failures": ["..."], "counter_score": 0.0-1.0}}"""
    },
    
    "actionability": {
        "name": "可执行性",
        "weight": 0.25,
        "prompt": """你是白虎·执行审计官。评估以下分析的建议是否真的能执行：

分析内容：
{content}

审查要求：
1. 每个建议需要多少资源（人/钱/时间/技术）？
2. 有没有"正确的废话"（听起来对但无法操作的建议）？
3. 时间线是否现实？
4. 是否考虑了执行中的摩擦成本？
5. 谁来执行？执行路径是否清晰？

输出纯JSON：
{{"recommendations": [{{"action": "...", "feasibility": "高/中/低", "missing": "...", "is_platitude": true/false}}], "actionability_score": 0.0-1.0, "platitudes": ["..."]}}"""
    }
}


def validate_single_dimension(dim_key, content):
    """Run a single validation dimension"""
    dim = VALIDATION_DIMENSIONS[dim_key]
    prompt = dim["prompt"].format(content=content[:4000])
    
    raw = call_llm(prompt, max_tokens=2000, temperature=0.3)
    
    parsed = None
    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
        json_match = re.search(r'\{[\s\S]*\}', clean)
        if json_match:
            parsed = json.loads(json_match.group())
    except:
        pass
    
    return {
        "dimension": dim["name"],
        "weight": dim["weight"],
        "output": parsed if parsed else raw,
        "raw": parsed is None
    }


def validate(content, dimensions=None):
    """
    Run adversarial validation on analysis content.
    
    Args:
        content: str or dict - the analysis to validate
        dimensions: list of dimension keys, or None for all
    
    Returns:
        dict with validation results, overall score, and recommendations
    """
    if isinstance(content, dict):
        content = json.dumps(content, ensure_ascii=False, indent=2)
    
    dims = dimensions or list(VALIDATION_DIMENSIONS.keys())
    results = {}
    scores = {}
    
    for dim_key in dims:
        if dim_key not in VALIDATION_DIMENSIONS:
            continue
        
        result = validate_single_dimension(dim_key, content)
        results[dim_key] = result
        
        # Extract score
        if isinstance(result["output"], dict):
            for k, v in result["output"].items():
                if "score" in k and isinstance(v, (int, float)):
                    scores[dim_key] = v
                    break
        
        if dim_key not in scores:
            scores[dim_key] = 0.5  # default if parsing failed
    
    # Calculate weighted overall score
    total_weight = sum(VALIDATION_DIMENSIONS[d]["weight"] for d in dims if d in VALIDATION_DIMENSIONS)
    overall = sum(
        scores.get(d, 0.5) * VALIDATION_DIMENSIONS[d]["weight"] 
        for d in dims if d in VALIDATION_DIMENSIONS
    ) / total_weight if total_weight > 0 else 0.5
    
    # Determine verdict
    if overall >= 0.8:
        verdict = "PASS"
        verdict_cn = "通过 — 分析质量高，可直接使用"
    elif overall >= 0.6:
        verdict = "CONDITIONAL"
        verdict_cn = "有条件通过 — 需修正标记问题后使用"
    elif overall >= 0.4:
        verdict = "WEAK"
        verdict_cn = "薄弱 — 核心结论需要补充证据"
    else:
        verdict = "FAIL"
        verdict_cn = "不通过 — 分析存在严重缺陷，需重做"
    
    # Collect all red flags
    all_flags = []
    for dim_key, result in results.items():
        if isinstance(result["output"], dict):
            for k in ["red_flags", "logical_gaps", "black_swans", "platitudes"]:
                flags = result["output"].get(k, [])
                if isinstance(flags, list):
                    all_flags.extend(flags)
    
    return {
        "overall_score": round(overall, 3),
        "verdict": verdict,
        "verdict_cn": verdict_cn,
        "dimension_scores": {k: round(v, 3) for k, v in scores.items()},
        "dimensions": results,
        "red_flags": all_flags[:10],  # top 10
        "validated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }


def validate_caas_output(caas_result):
    """
    Validate a CaaS analyze response.
    Extracts earth phase output (most substantive) for validation.
    """
    phases = caas_result.get("phases", {})
    
    # Prioritize earth > fire > wood for validation
    content = ""
    for phase_key in ["earth", "fire", "wood", "metal", "water"]:
        phase = phases.get(phase_key, {})
        output = phase.get("output", "")
        if output:
            if isinstance(output, dict):
                content += json.dumps(output, ensure_ascii=False) + "\n\n"
            else:
                content += str(output) + "\n\n"
    
    if not content.strip():
        return {"error": "No content to validate", "overall_score": 0}
    
    return validate(content)


# ===== CLI =====
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python metal_validator.py <input.json> [dimensions]")
        print("  dimensions: data_integrity,logic_consistency,counter_evidence,actionability")
        print("  or: python metal_validator.py --test")
        sys.exit(1)
    
    if sys.argv[1] == "--test":
        test_content = """
        碳化硅(SiC)市场分析：
        2025年全球SiC市场规模达到98亿美元，年增速15%。
        天岳先进占国内衬底市场35%份额。
        预计2030年市场将达到300亿美元。
        建议：立即投资SiC外延片产线，预计18个月回本。
        """
        print("Running test validation on SiC analysis...")
        result = validate(test_content, ["data_integrity", "logic_consistency"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        input_file = sys.argv[1]
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        dims = sys.argv[2].split(",") if len(sys.argv) > 2 else None
        
        if "phases" in data:
            result = validate_caas_output(data)
        else:
            content = data.get("content", json.dumps(data, ensure_ascii=False))
            result = validate(content, dims)
        
        print(json.dumps(result, ensure_ascii=False, indent=2))
