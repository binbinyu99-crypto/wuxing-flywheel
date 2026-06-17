# -*- coding: utf-8 -*-
"""
V6.2 Benchmark Suite: Comprehensive performance testing.
"""
import time, json, os, sys
sys.path.insert(0, '.')

class BenchmarkSuite:
    """Run comprehensive benchmarks on pipeline components"""
    
    def __init__(self):
        self.results = []
    
    def bench(self, name, func, *args, **kwargs):
        """Benchmark a function"""
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            self.results.append({"name": name, "time": elapsed, "pass": True})
            return elapsed, result
        except Exception as e:
            elapsed = time.time() - start
            self.results.append({"name": name, "time": elapsed, "pass": False, "error": str(e)})
            return elapsed, None
    
    def run_all(self):
        """Run all benchmarks"""
        print("Benchmark Suite v6.2")
        print("=" * 50)
        
        # B1: Module imports
        t, _ = self.bench("import_all", self._import_all)
        print(f"  [B1] Import all modules: {t:.2f}s")
        
        # B2: Defense init
        t, _ = self.bench("defense_init", self._defense_init)
        print(f"  [B2] Defense initialization: {t:.2f}s")
        
        # B3: Semantic filter
        t, _ = self.bench("semantic_scan", self._semantic_scan)
        print(f"  [B3] Semantic scan (1000 texts): {t:.2f}s")
        
        # B4: Domain detection
        t, _ = self.bench("domain_detect", self._domain_detect)
        print(f"  [B4] Domain detection (100 topics): {t:.2f}s")
        
        # B5: Profiler throughput
        t, _ = self.bench("profiler_throughput", self._profiler_throughput)
        print(f"  [B5] Profiler (500 events): {t:.2f}s")
        
        # B6: Cascade limiter stress
        t, _ = self.bench("cascade_stress", self._cascade_stress)
        print(f"  [B6] Cascade limiter (100 cascades): {t:.2f}s")
        
        # B7: Sandbox creation
        t, _ = self.bench("sandbox_create", self._sandbox_create)
        print(f"  [B7] Sandbox creation (50 agents): {t:.2f}s")
        
        # B8: CI runner
        t, _ = self.bench("ci_quick", self._ci_quick)
        print(f"  [B8] CI quick test: {t:.2f}s")
        
        passed = sum(1 for r in self.results if r["pass"])
        total_time = sum(r["time"] for r in self.results)
        
        print(f"\n  Results: {passed}/{len(self.results)} passed")
        print(f"  Total time: {total_time:.2f}s")
        
        # Save
        with open("reports/benchmark_v62.json", "w", encoding="utf-8") as f:
            json.dump({"results": self.results, "total_time": total_time, "passed": passed}, f, indent=2, default=str)
        
        return passed == len(self.results)
    
    def _import_all(self):
        import wuxing_pipeline_v2, verification, residual_engine, iteration_loop
        import agent_sandbox, cascade_limiter, behavioral_profiler, adaptive_thresholds
        import adversarial_training, redblue_ci, domain_keywords_v2, pipeline_monitor
        import semantic_filter, module_docs
        return True
    
    def _defense_init(self):
        from wuxing_pipeline_v2 import init_defense_context
        ctx = init_defense_context()
        return ctx.get("enabled", False)
    
    def _semantic_scan(self):
        from semantic_filter import SemanticFilter
        sf = SemanticFilter()
        for i in range(1000):
            sf.scan(f"Test content {i} with some data about semiconductors and AI", f"test_{i}")
        return sf.get_stats()
    
    def _domain_detect(self):
        from domain_keywords_v2 import detect_domain
        topics = ["AI chip", "bank risk", "car factory", "city plan", "gene therapy"] * 20
        return [detect_domain(t) for t in topics]
    
    def _profiler_throughput(self):
        from behavioral_profiler import BehavioralProfiler
        bp = BehavioralProfiler(quarantine_threshold=0.5, min_events_for_classification=3)
        for i in range(50):
            bp.register_agent(f"a_{i}")
        for i in range(500):
            bp.record_event(f"a_{i % 50}", "query", {"query": f"q_{i}"})
        return bp.get_threat_assessment()
    
    def _cascade_stress(self):
        from cascade_limiter import CascadeLimiter
        cl = CascadeLimiter(max_depth=5, max_concurrent=20)
        for i in range(100):
            cl.start_cascade(f"c_{i}", f"agent_{i}")
        return cl.metrics
    
    def _sandbox_create(self):
        from agent_sandbox import SandboxManager
        sm = SandboxManager()
        for i in range(50):
            sm.create_sandbox(f"s_{i}")
        return sm.get_isolation_report()
    
    def _ci_quick(self):
        from redblue_ci import RedBlueCIRunner
        return RedBlueCIRunner().run_quick_test()

def self_test():
    suite = BenchmarkSuite()
    return suite.run_all()

if __name__ == "__main__":
    self_test()
