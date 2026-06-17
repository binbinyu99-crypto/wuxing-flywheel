# -*- coding: utf-8 -*-
"""
飞轮易读版发布器 v1.0 — "珑珠格式"
将飞轮原始输出重组为主题化易读报告。

结构：一句话结论 → 鲲鹏推演 → 三象分析 → 五行收敛 → 方向评估 → 数据缺口 → 行动建议
"""
import json, re

def parse_element_json(raw_text):
    """Extract JSON from element output (handles ```json blocks)."""
    if not raw_text:
        return {}
    # Try direct JSON parse
    try:
        return json.loads(raw_text)
    except:
        pass
    # Try extracting from code block
    m = re.search(r'```json\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except:
            pass
    # Try extracting from array block
    m = re.search(r'```json\s*(\[.*?\])\s*```', raw_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except:
            pass
    return {"raw": raw_text[:2000]}


def generate_readable_report(flywheel_result, company_name=None):
    """
    Generate readable report from flywheel result.
    
    Args:
        flywheel_result: Full flywheel result dict
        company_name: Optional company name (None = anonymized)
    
    Returns:
        dict with 'markdown' and 'sections' keys
    """
    result = flywheel_result.get('result', flywheel_result)
    rounds = result.get('rounds', [])
    topic = flywheel_result.get('topic', '')
    
    if not rounds:
        return {"markdown": "无分析数据", "sections": []}
    
    # Collect all element data across rounds
    all_qinglong = []  # Seeds
    all_zhuque = []     # Analysis
    all_diting = []     # Verification
    all_baihu = []      # Attacks
    all_xuanwu = []     # Convergence
    
    for i, r in enumerate(rounds):
        elements = r.get('elements', {})
        for name, raw in elements.items():
            parsed = parse_element_json(raw)
            entry = {"round": i+1, "data": parsed, "raw": raw[:3000] if isinstance(raw, str) else ""}
            
            if 'qinglong' in name:
                all_qinglong.append(entry)
            elif 'zhuque' in name:
                all_zhuque.append(entry)
            elif 'diting' in name:
                all_diting.append(entry)
            elif 'baihu' in name:
                all_baihu.append(entry)
            elif 'xuanwu' in name:
                all_xuanwu.append(entry)
    
    # Build readable report sections
    sections = []
    display_name = company_name or "目标企业"
    
    # ============================================================
    # Section 1: 一句话结论 (from final xuanwu)
    # ============================================================
    final_xw = all_xuanwu[-1]['data'] if all_xuanwu else {}
    conclusion = final_xw.get('conclusion', '')
    confidence = final_xw.get('confidence', 0)
    
    # Adjust confidence if data gaps are significant
    diting_issues = []
    for d in all_diting:
        vlist = d['data'].get('verifications', [])
        for v in vlist:
            issues = v.get('issues', [])
            missing = v.get('missing_data', v.get('missing', []))
            diting_issues.extend(issues)
            diting_issues.extend(missing)
    
    adjusted_confidence = confidence
    if len(diting_issues) > 5:
        adjusted_confidence = min(confidence, 0.65)
    
    sections.append({
        "title": "一句话结论",
        "icon": "🎯",
        "content": conclusion,
        "meta": f"置信度: {adjusted_confidence:.2f} | 基于 {len(rounds)} 轮对抗分析"
    })
    
    # ============================================================
    # Section 2: 鲲鹏推演 (from xuanwu kun/peng)
    # ============================================================
    kunpeng_content = []
    
    for xw in all_xuanwu:
        kun = xw['data'].get('kun_dive', xw['data'].get('kunpeng', {}).get('kun_dive', {}))
        peng = xw['data'].get('peng_soar', xw['data'].get('kunpeng', {}).get('peng_soar', {}))
        dao = xw['data'].get('dao_merge', xw['data'].get('kunpeng', {}).get('dao_merge', {}))
        
        if kun:
            kunpeng_content.append(f"**🐟 鲲潜（R{xw['round']}约束推演）**\n{kun.get('conclusion', json.dumps(kun, ensure_ascii=False)[:500])}")
        if peng:
            kunpeng_content.append(f"**🦅 鹏举（R{xw['round']}极限推演）**\n{peng.get('limit_form', json.dumps(peng, ensure_ascii=False)[:500])}")
        if dao:
            one_sentence = dao.get('one_sentence_dao', '')
            rules = dao.get('rules', [])
            rule_text = '\n'.join([f"- {r.get('rule', str(r))}" for r in rules]) if rules else ''
            kunpeng_content.append(f"**☯ 合流（R{xw['round']}底层规律）**\n{one_sentence}\n{rule_text}")
    
    if kunpeng_content:
        sections.append({
            "title": "鲲鹏推演",
            "icon": "🌊",
            "content": '\n\n'.join(kunpeng_content)
        })
    
    # ============================================================
    # Section 3: 方向评估 (from qinglong seeds + zhuque analysis + baihu attacks)
    # ============================================================
    # Collect all seeds and their evaluations
    seed_evaluations = {}
    
    for q in all_qinglong:
        seeds = q['data'].get('seeds', [])
        for s in seeds:
            sid = s.get('id', s.get('title', f"s{len(seed_evaluations)+1}"))
            if sid not in seed_evaluations:
                seed_evaluations[sid] = {
                    "title": s.get('title', sid),
                    "hypothesis": s.get('hypothesis', ''),
                    "first_principle": s.get('first_principle', ''),
                    "analyses": [],
                    "verifications": [],
                    "attacks": [],
                    "final_verdict": "未评估"
                }
    
    for z in all_zhuque:
        analyses = z['data'].get('analyses', [])
        for a in analyses:
            sid = a.get('seed_id', '')
            if sid in seed_evaluations:
                seed_evaluations[sid]['analyses'].append({
                    "round": z['round'],
                    "confidence": a.get('confidence', 0),
                    "analysis": a.get('analysis', ''),
                    "risks": a.get('risks', [])
                })
    
    for b in all_baihu:
        attacks = b['data'].get('attacks', [])
        for a in attacks:
            sid = a.get('seed_id', '')
            if sid in seed_evaluations:
                seed_evaluations[sid]['attacks'].append({
                    "round": b['round'],
                    "severity": a.get('severity', 0),
                    "attack": a.get('attack', '')
                })
    
    for d in all_diting:
        verifications = d['data'].get('verifications', [])
        for v in verifications:
            sid = v.get('seed_id', '')
            if sid in seed_evaluations:
                seed_evaluations[sid]['verifications'].append({
                    "round": d['round'],
                    "verdict": v.get('verdict', ''),
                    "grade": v.get('evidence_grade', 'C'),
                    "issues": v.get('issues', []),
                    "missing": v.get('missing_data', v.get('missing', []))
                })
    
    # Determine final verdict for each seed
    for sid, s in seed_evaluations.items():
        max_severity = max([a['severity'] for a in s['attacks']], default=0)
        avg_confidence = sum([a['confidence'] for a in s['analyses']]) / max(len(s['analyses']), 1)
        
        if max_severity >= 0.8:
            s['final_verdict'] = "🔴 剔除"
            s['verdict_reason'] = f"致命攻击(严重度{max_severity})"
        elif avg_confidence >= 0.7 and max_severity < 0.6:
            s['final_verdict'] = "🟢 推荐"
            s['verdict_reason'] = f"置信度{avg_confidence:.2f}"
        elif avg_confidence >= 0.5:
            s['final_verdict'] = "🟡 需验证"
            s['verdict_reason'] = f"置信度{avg_confidence:.2f}，需补充数据"
        else:
            s['final_verdict'] = "⚪ 证据不足"
            s['verdict_reason'] = f"置信度{avg_confidence:.2f}"
    
    direction_lines = []
    for sid, s in seed_evaluations.items():
        line = f"**{s['final_verdict']} {s['title']}**\n"
        if s['hypothesis']:
            line += f"假设：{s['hypothesis']}\n"
        
        # Add key attack
        if s['attacks']:
            top_attack = max(s['attacks'], key=lambda x: x['severity'])
            line += f"⚠️ 主要攻击：{top_attack['attack'][:200]}\n"
        
        # Add missing data
        all_missing = []
        for v in s['verifications']:
            all_missing.extend(v.get('missing', []))
        if all_missing:
            line += f"📋 缺失数据：{'、'.join(all_missing[:5])}\n"
        
        direction_lines.append(line)
    
    if direction_lines:
        sections.append({
            "title": "方向评估",
            "icon": "🧭",
            "content": '\n\n'.join(direction_lines)
        })
    
    # ============================================================
    # Section 4: 数据缺口 (from diting verifications)
    # ============================================================
    all_missing_data = set()
    all_issues = []
    for d in all_diting:
        for v in d['data'].get('verifications', []):
            for m in v.get('missing_data', v.get('missing', [])):
                all_missing_data.add(m)
            for issue in v.get('issues', []):
                all_issues.append(issue)
    
    if all_missing_data or all_issues:
        gap_content = ""
        if all_missing_data:
            gap_content += "**需补充的关键数据：**\n"
            for m in sorted(all_missing_data):
                gap_content += f"- {m}\n"
        if all_issues:
            gap_content += "\n**已发现的数据矛盾：**\n"
            for issue in all_issues[:10]:
                gap_content += f"- {issue}\n"
        
        sections.append({
            "title": "数据缺口",
            "icon": "🔍",
            "content": gap_content,
            "meta": f"补数据优先于定战略 — 当前 {len(all_missing_data)} 项关键数据缺失"
        })
    
    # ============================================================
    # Section 5: 行动建议 (from xuanwu recommendations)
    # ============================================================
    recommendations = []
    for xw in all_xuanwu:
        recs = xw['data'].get('recommendations', xw['data'].get('action_path', []))
        if isinstance(recs, list):
            recommendations.extend(recs)
        elif isinstance(recs, dict):
            recommendations.append(recs)
    
    if recommendations:
        rec_content = ""
        for r in recommendations:
            if isinstance(r, dict):
                action = r.get('action', r.get('description', json.dumps(r, ensure_ascii=False)[:200]))
                priority = r.get('priority', r.get('phase', ''))
                rec_content += f"- **[{priority}]** {action}\n"
            else:
                rec_content += f"- {r}\n"
        
        sections.append({
            "title": "行动建议",
            "icon": "🚀",
            "content": rec_content
        })
    
    # ============================================================
    # Section 6: 飞轮演进 (brief round summary)
    # ============================================================
    evolution = ""
    for i, xw in enumerate(all_xuanwu):
        round_conclusion = xw['data'].get('conclusion', '')[:200]
        evolution += f"**R{xw['round']}：** {round_conclusion}\n\n"
    
    if evolution:
        sections.append({
            "title": "飞轮演进",
            "icon": "🔄",
            "content": evolution
        })
    
    # Build full markdown
    md_lines = [f"# {display_name}转型战略分析 | 易读版\n"]
    
    for s in sections:
        md_lines.append(f"\n## {s['icon']} {s['title']}")
        if s.get('meta'):
            md_lines.append(f"*{s['meta']}*\n")
        md_lines.append(s['content'])
    
    md_lines.append(f"\n---\n*分析引擎：五行飞轮 v5.3 | {len(rounds)}轮对抗 | 置信度 {adjusted_confidence:.2f}*")
    
    return {
        "markdown": '\n'.join(md_lines),
        "sections": sections,
        "confidence": adjusted_confidence,
        "rounds": len(rounds),
        "seed_evaluations": seed_evaluations
    }


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    # Test with V2 result
    with open(r'D:\tmp\jj_v2_result2.txt', 'r', encoding='utf-8-sig') as f:
        data = json.loads(f.read())
    
    report = generate_readable_report(data, "深圳市建匠工程有限公司")
    
    print(report['markdown'][:5000])
    print(f"\n\n=== Stats ===")
    print(f"Sections: {len(report['sections'])}")
    print(f"Seeds evaluated: {len(report['seed_evaluations'])}")
    print(f"Confidence: {report['confidence']}")
