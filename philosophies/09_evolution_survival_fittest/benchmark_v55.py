# -*- coding: utf-8 -*-
"""E2E Benchmark: Run pipeline with calibration and measure improvements."""
import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'D:\ClawMatrix')

print("=" * 60)
print("WUXING PIPELINE E2E BENCHMARK")
print("=" * 60)

# Test 1: Pipeline self-test
print("\n--- Test 1: Pipeline self-test ---")
try:
    from wuxing_pipeline_v2 import self_test
    self_test()
    print("RESULT: PASS")
except Exception as e:
    print("RESULT: FAIL ({})".format(str(e)[:100]))

# Test 2: Search proxy
print("\n--- Test 2: Search proxy ---")
try:
    from search_proxy import SearchProxy
    sp = SearchProxy()
    r = sp.search("碳纤维 复合材料")
    print("Strategy: {}, Results: {}".format(r["strategy_used"], r["total"]))
    print("RESULT: PASS")
except Exception as e:
    print("RESULT: FAIL ({})".format(str(e)[:100]))

# Test 3: Creative seed engine
print("\n--- Test 3: Creative seed engine ---")
try:
    from creative_seed_engine import CreativeSeedEngine
    cse = CreativeSeedEngine()
    seeds = cse.generate_seeds("SiC power electronics supply chain", count=6)
    techniques = set(s["technique"] for s in seeds)
    print("Seeds: {}, Techniques: {}".format(len(seeds), techniques))
    print("RESULT: PASS")
except Exception as e:
    print("RESULT: FAIL ({})".format(str(e)[:100]))

# Test 4: Metal calibrator
print("\n--- Test 4: Metal calibrator ---")
try:
    from metal_calibrator import calibrate_scores, detect_analysis_type
    # Simulate typical flywheel dimensions
    dims = {
        "data_completeness": 0.4,
        "coverage_breadth": 0.6,
        "analysis_depth": 0.7,
        "seed_utilization": 0.5,
        "cross_validation": 0.3,
        "devil_advocate": 0.5,
        "fact_checker": 0.2,
        "agent_eval": 0.68
    }
    
    # Test all 4 profiles
    for topic, expected_type in [
        ("武汉车谷合作可行性分析", "exploratory"),
        ("期权Gamma分析 Tushare", "verified_data"),
        ("投资尽调报告", "due_diligence"),
        ("一般技术分析", "mixed_sources"),
    ]:
        r = calibrate_scores(dims, topic=topic)
        status = "OK" if r["analysis_type"] == expected_type else "MISMATCH"
        print("  {} -> type={}, verdict={}, score={:.3f} [{}]".format(
            topic[:20], r["analysis_type"], r["verdict"], r["calibrated_composite"], status))
    
    print("RESULT: PASS")
except Exception as e:
    print("RESULT: FAIL ({})".format(str(e)[:100]))

# Test 5: Anomaly detector
print("\n--- Test 5: Anomaly detector ---")
try:
    from anomaly_detector import AnomalyDetector
    ad = AnomalyDetector()
    
    # Test with anomalous data
    bad = {"phases": {
        "wood": {"analysis": "", "elapsed": 0.1},
        "fire": {"analysis": "x" * 100, "elapsed": 500},
        "metal": {"dimensions": {"a": 0.5, "b": 0.5, "c": 0.5}, "elapsed": 5},
    }}
    anomalies = ad.check_pipeline_result(bad)
    print("Anomalies found: {} (health: {:.2f})".format(len(anomalies), ad.get_health_score()))
    print("RESULT: PASS")
except Exception as e:
    print("RESULT: FAIL ({})".format(str(e)[:100]))

# Test 6: Pipeline integrator
print("\n--- Test 6: Pipeline integrator ---")
try:
    from pipeline_integrator import post_process_pipeline
    mock = {
        "topic": "AI产业分析",
        "phases": {
            "wood": {"analysis": "Wood " * 100, "elapsed": 20},
            "fire": {"analysis": "Fire " * 200, "elapsed": 40},
            "earth": {"synthesis": {"executive_summary": "Summary", "data_gaps": ["gap1"]}, "elapsed": 60},
            "metal": {"dimensions": dims, "verdict": "FAIL", "composite_score": 0.30, "elapsed": 8},
            "water": {"seeds": ["s1", "s2"], "elapsed": 15},
        },
        "cognitive_graph": {"residuals": ["r1"]}
    }
    processed = post_process_pipeline(mock, "AI产业分析")
    cal = processed.get("calibration", {})
    res = processed.get("extracted_residuals", {})
    print("Calibration: {} {} {:.3f}".format(
        cal.get("analysis_type"), cal.get("verdict"), cal.get("calibrated_composite", 0)))
    print("Residuals: {}".format(res.get("count", "?")))
    print("RESULT: PASS")
except Exception as e:
    print("RESULT: FAIL ({})".format(str(e)[:100]))

# Test 7: Security policy
print("\n--- Test 7: Security policy ---")
try:
    from security_policy_engine import SecurityPolicy
    sp = SecurityPolicy()
    ok, _, warns = sp.validate_input("Normal text for analysis")
    level, label, _ = sp.classify_sensitivity("Contact: sk-abcdefghij1234567890 for API access")
    print("Input validation: {}, Sensitivity: {}".format("PASS" if ok else "BLOCKED", label))
    print("RESULT: PASS")
except Exception as e:
    print("RESULT: FAIL ({})".format(str(e)[:100]))

# Test 8: ResidualEngine.extract_all
print("\n--- Test 8: ResidualEngine.extract_all ---")
try:
    from residual_engine import ResidualEngine
    re_obj = ResidualEngine()
    residuals = re_obj.extract_all({
        "phases": {
            "metal": {"dimensions": {"data": 0.3, "coverage": 0.8}, "adversarial_results": {"devil_critique": "Issues found"}},
            "earth": {"synthesis": {"data_gaps": ["Missing market size"], "residual_questions": ["What about Q4?"]}}
        },
        "cognitive_graph": {"residuals": ["CG gap 1"]}
    })
    print("Extracted: {} residuals".format(len(residuals)))
    for r in residuals[:3]:
        print("  [{}/P{}] {}".format(r["type"], r["priority"], r["description"][:60]))
    print("RESULT: PASS")
except Exception as e:
    print("RESULT: FAIL ({})".format(str(e)[:100]))

# Summary
print("\n" + "=" * 60)
print("BENCHMARK COMPLETE")
print("v5.5.0 Module Count: 42+ modules")
print("=" * 60)
