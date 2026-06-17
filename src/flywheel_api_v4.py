# -*- coding: utf-8 -*-
"""
flywheel_api_v4.py - High-Concurrency Wuxing Flywheel API
v4.0.0 - FastAPI + uvicorn + ThreadPoolExecutor + Rate Limiting

Upgrade from v3.0.0 (BaseHTTPRequestHandler, ~3-5 concurrent)
Target: 50+ concurrent analyses

Architecture:
- FastAPI + uvicorn (async HTTP, multi-worker ready)
- ThreadPoolExecutor for pipeline runs (configurable max_workers)
- Semaphore-based LLM rate limiting
- API key rotation for LLM providers
- PG connection pooling
- Auto-publish to Feishu on completion
"""

import sys, os, json, time, hashlib, traceback, datetime
from concurrent.futures import ThreadPoolExecutor, Future
from threading import Semaphore, Lock
from typing import Optional, Dict, Any

# Redis queue integration
try:
    from redis_queue import RedisTaskQueue
    USE_REDIS_QUEUE = True
except ImportError:
    USE_REDIS_QUEUE = False

sys.path.insert(0, r'D:\ClawMatrix')
sys.path.insert(0, r'D:\ClawMatrix\engine')
print("[INIT] sys.path includes engine_v2 dir")
os.chdir(r'D:\ClawMatrix')

from result_enrichment import maybe_enrich_result as _maybe_enrich_result
from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
import socket as _socket

VERSION = "6.1.0-auto-resume"
PORT = 8100
API_TOKEN = "<YOUR_AUTH_TOKEN>"

# ---- Concurrency Config ----
MAX_WORKERS = 10          # Max concurrent pipeline runs
LLM_SEMAPHORE_LIMIT = 16  # Max concurrent LLM API calls across all runs (upgraded from 8)
QUEUE_LIMIT = 50          # Max queued jobs before rejecting

_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="flywheel")
_llm_semaphore = Semaphore(LLM_SEMAPHORE_LIMIT)
_active_runs: Dict[str, Future] = {}
_active_lock = Lock()

# ---- V5.4-STABILITY: Graceful Shutdown ----
import signal
import atexit

# Auto-deploy pipeline
try:
    from auto_deploy_pipeline import auto_deploy
    HAS_AUTO_DEPLOY = True
except ImportError:
    HAS_AUTO_DEPLOY = False


_shutdown_requested = False

def _graceful_shutdown(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    print(f"[SHUTDOWN] Signal {signum} received, graceful shutdown...")
    with _active_lock:
        active_ids = list(_active_runs.keys())
    if active_ids:
        print(f"[SHUTDOWN] {len(active_ids)} active runs -> interrupted")
        try:
            from pg_storage import get_conn
            with get_conn() as conn:
                cur = conn.cursor()
                for rid in active_ids:
                    cur.execute(
                        "UPDATE flywheel_api_runs SET status='interrupted', "
                        "error='Graceful shutdown - can be resumed', finished_at=NOW() "
                        "WHERE run_id=%s AND status='running'", (rid,))
                conn.commit()
        except Exception as e:
            print(f"[SHUTDOWN] DB error: {e}")

for _sig in [signal.SIGINT, signal.SIGTERM]:
    try:
        signal.signal(_sig, _graceful_shutdown)
    except (OSError, ValueError):
        pass
try:
    signal.signal(signal.SIGBREAK, _graceful_shutdown)
except (AttributeError, OSError, ValueError):
    pass


# ---- Redis Queue (P2-1) ----
redis_queue = None
if USE_REDIS_QUEUE:
    try:
        redis_queue = RedisTaskQueue()
        print("[Redis] Queue initialized")
    except Exception as e:
        print(f"[Redis] Queue init failed: {e}")
        USE_REDIS_QUEUE = False

# ---- Priority Queue & Backpressure ----
_priority_queue = []  # [(priority, timestamp, topic, domain, depth, max_rounds), ...]
_priority_lock = Lock()
PRIORITY_LEVELS = {'paid': 0, 'free': 1}  # Lower = higher priority
MAX_QUEUE_DEPTH = 100  # Hard limit before 503
ESTIMATED_TIME_PER_RUN = 60  # seconds, average

# ---- Auto-publish ----
try:
    from feishu_publisher import auto_publish
    HAS_PUBLISHER = True
    print("[INIT] feishu_publisher loaded")
except Exception as e:
    HAS_PUBLISHER = False
    print(f"[INIT] feishu_publisher not available: {e}")

# ---- Grand Cycle Integration (V7.0) ----
try:
    from grand_cycle import get_grand_cycle
    HAS_GRAND_CYCLE = True
    print('[INIT] grand_cycle loaded')
except Exception as _gc_err:
    HAS_GRAND_CYCLE = False
    print(f'[INIT] grand_cycle not available: {_gc_err}')

# ---- Readable Publisher (v5.5) ----
def publish_readable_to_feishu(readable, topic, run_id):
    """Disabled by P7-004."""
    return None

def _wait_for_port(port, max_wait=15):
    for i in range(max_wait):
        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            s.settimeout(1)
            s.bind(('0.0.0.0', port))
            s.close()
            if i > 0:
                print(f"[STARTUP] Port {port} available after {i}s")
            return True
        except OSError:
            if i == 0:
                print(f"[STARTUP] Port {port} in use, waiting...")
            import time
            time.sleep(1)
            try:
                s.close()
            except:
                pass
    print(f"[STARTUP] Port {port} still in use after {max_wait}s!")
    return False

_wait_for_port(PORT)

# ---- FastAPI App ----
app = FastAPI(
    title="Wuxing Flywheel API",
    version=VERSION,
    description="High-concurrency industry analysis engine"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Auth ----
async def verify_token(authorization: Optional[str] = Header(None), token: Optional[str] = Query(None)):
    if authorization and authorization.startswith("Bearer ") and authorization[7:] == API_TOKEN:
        return True
    if token == API_TOKEN:
        return True
    raise HTTPException(status_code=401, detail="Unauthorized. Use Bearer token or ?token= param.")

# ---- PG Layer ----

def _init_table():
    from pg_storage import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS flywheel_api_runs (
                run_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                domain TEXT DEFAULT 'general',
                depth TEXT DEFAULT 'deep',
                status TEXT DEFAULT 'queued',
                started_at TIMESTAMPTZ DEFAULT NOW(),
                finished_at TIMESTAMPTZ,
                result JSONB,
                error TEXT,
                score REAL,
                verdict TEXT,
                grade TEXT,
                elapsed_sec REAL,
                feishu_doc_url TEXT
            )
        """)
        try:
            cur.execute("ALTER TABLE flywheel_api_runs ADD COLUMN IF NOT EXISTS feishu_doc_url TEXT")
        except:
            pass
        try:
            cur.execute("ALTER TABLE flywheel_api_runs ADD COLUMN IF NOT EXISTS progress JSONB DEFAULT '{}'::jsonb")
        except:
            pass
        conn.commit()
    print("[PG] flywheel_api_runs table ready (V6.0: +progress)")

def _pg_save_run(run_id, topic, domain, depth, status="queued"):
    from pg_storage import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO flywheel_api_runs (run_id, topic, domain, depth, status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (run_id) DO UPDATE SET status=EXCLUDED.status
        """, (run_id, topic, domain, depth, status))
        conn.commit()

def _pg_update_running(run_id):
    from pg_storage import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE flywheel_api_runs SET status='running' WHERE run_id=%s", (run_id,))
        conn.commit()

def _pg_complete(run_id, result, scores, elapsed):
    from pg_storage import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        result_json = json.dumps(result, ensure_ascii=False, default=str) if result else None
        cur.execute("""
            UPDATE flywheel_api_runs 
            SET status='completed', result=%s::jsonb, finished_at=NOW(),
                score=%s, verdict=%s, grade=%s, elapsed_sec=%s
            WHERE run_id=%s
        """, (result_json, scores.get("score"), scores.get("verdict"), 
              scores.get("grade"), elapsed, run_id))
        conn.commit()

def _pg_save_feishu_url(run_id, url):
    from pg_storage import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE flywheel_api_runs SET feishu_doc_url=%s WHERE run_id=%s", (url, run_id))
        conn.commit()

def _pg_error(run_id, error_msg):
    from pg_storage import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE flywheel_api_runs 
            SET status='error', error=%s, finished_at=NOW()
            WHERE run_id=%s
        """, (error_msg, run_id))
        conn.commit()


def _pg_update_progress(run_id, progress_data):
    """V6.0: Update real-time progress for a running analysis."""
    from pg_storage import get_conn
    try:
        import json as _json
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE flywheel_api_runs SET progress = %s::jsonb WHERE run_id = %s",
                (_json.dumps(progress_data, ensure_ascii=False, default=str), run_id)
            )
            conn.commit()
    except Exception as e:
        print(f"[V6.0] Progress update error: {e}")


def _pg_get_run(run_id):
    from pg_storage import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""SELECT run_id, topic, domain, depth, status, started_at, finished_at, 
                       result, error, score, verdict, grade, elapsed_sec, feishu_doc_url 
                       FROM flywheel_api_runs WHERE run_id=%s""", (run_id,))
        row = cur.fetchone()
        if row:
            return {
                "run_id": row[0], "topic": row[1], "domain": row[2], "depth": row[3],
                "status": row[4], "started_at": str(row[5]), "finished_at": str(row[6]) if row[6] else None,
                "result": row[7], "error": row[8], "score": row[9], "verdict": row[10],
                "grade": row[11], "elapsed_sec": row[12], "feishu_doc_url": row[13]
            }
        return None

def _pg_list_runs(limit=50):
    from pg_storage import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT run_id, topic, status, score, verdict, grade, elapsed_sec, started_at, feishu_doc_url,
       (result->'kunpeng'->>'confidence')::float as confidence
            FROM flywheel_api_runs ORDER BY started_at DESC LIMIT %s
        """, (limit,))
        return [{"run_id": r[0], "topic": r[1], "status": r[2], "score": r[3],
                 "verdict": r[4], "grade": r[5], "elapsed_sec": r[6], "started_at": str(r[7]),
                 "feishu_doc_url": r[8], "confidence": round(r[9], 2) if r[9] is not None else 0.0}
                for r in cur.fetchall()]

def _pg_count_status():
    from pg_storage import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, COUNT(*) FROM flywheel_api_runs GROUP BY status")
        return dict(cur.fetchall())

# ---- Score Extraction ----

def _extract_scores(result):
    """V5.1: Extract scores from engine_v2 result format."""
    if not result or not isinstance(result, dict):
        return {"verdict": None, "score": None, "grade": None}
    # V5.1: engine_v2 format (convergence.final_score)
    conv = result.get("convergence", {})
    if isinstance(conv, dict) and conv.get("final_score") is not None:
        score = conv["final_score"]
        verdict = conv.get("verdict", "conditional")
        grade = "A" if score > 0.8 else "B" if score > 0.6 else "C" if score > 0.4 else "D"
        # V11.5: Calculate grade from score if missing
    if not grade and score is not None:
        grade = "A" if score > 0.8 else "B" if score > 0.6 else "C" if score > 0.4 else "D"
    return {"verdict": verdict, "score": score, "grade": grade}
    # Legacy format fallback
    verdict = result.get("final_verdict")
    score = result.get("final_composite")
    grade = result.get("final_grade")
    if not verdict:
        phases = result.get("phases", {})
        metal = phases.get("metal", {})
        if isinstance(metal, dict):
            verdict = metal.get("verdict")
            score = metal.get("composite_score")
            grade = metal.get("grade")
    if not verdict:
        mr = result.get("metal_raw", {})
        if isinstance(mr, dict):
            verdict = mr.get("verdict")
            score = score or mr.get("score")
    if not score:
        mc = result.get("metal_calibrated", {})
        if isinstance(mc, dict):
            score = mc.get("score")
    # V11.5: Calculate grade from score if missing
    if not grade and score is not None:
        grade = "A" if score > 0.8 else "B" if score > 0.6 else "C" if score > 0.4 else "D"
    return {"verdict": verdict, "score": score, "grade": grade}

# ---- Pipeline Runner (with LLM semaphore) ----


# ---------------------------------------------------------------------------
# V9.0: Kunpeng Enrichment (disabled - handled by pipeline-level enrich_sync)
def _enrich_kunpeng(topic, round_num, element_outputs, kunpeng_data):
    """Pass-through. Enrichment now handled by result_enrichment.enrich_sync in pipeline."""
    return kunpeng_data



# === P7-005: Topic Complexity Assessment ===
def _assess_topic_complexity(topic, depth, edge_mode, max_rounds):
    """Assess topic breadth and auto-downgrade broad topics."""
    breadth_score = 0
    if len(topic) < 15:
        breadth_score += 1
    broad_zh = ["\u53d1\u5c55\u8d8b\u52bf", "\u672a\u6765\u5c55\u671b", "\u5168\u9762\u5206\u6790",
               "\u7efc\u5408\u5206\u6790", "\u884c\u4e1a\u6982\u51b5", "\u5168\u7403",
               "\u4e16\u754c", "\u6240\u6709", "\u5404\u79cd", "\u6574\u4f53",
               "\u603b\u4f53", "\u5b8f\u89c2", "\u5927\u8d8b\u52bf"]
    broad_en = ["overview", "future of", "everything about", "comprehensive",
               "global trends", "all aspects", "general"]
    topic_lower = topic.lower()
    for kw in broad_zh + broad_en:
        if kw in topic_lower:
            breadth_score += 1
            break
    focused = ["vs", "\u5bf9\u6bd4", "\u6bd4\u8f83", "\u5177\u4f53", "\u6848\u4f8b",
              "\u5b9e\u8bc1", "\u6570\u636e", "\u65b9\u6848", "\u7b56\u7565",
              "\u6280\u672f\u8def\u7ebf", "\u7ade\u4e89\u683c\u5c40"]
    for fm in focused:
        if fm in topic_lower:
            breadth_score -= 1
    breadth_score = max(0, breadth_score)
    if breadth_score >= 3:
        return "sheng", 1, f"broad topic (score={breadth_score}), downgraded"
    elif breadth_score >= 2:
        return edge_mode, min(max_rounds, 2), f"moderate breadth (score={breadth_score})"
    return edge_mode, max_rounds, f"focused topic (score={breadth_score})"

def _run_pipeline(run_id, topic, domain, depth, max_rounds, edge_mode="full"):
    """V5.0 Thin Proxy: delegates to engine_v2 with kunpeng support."""
    try:
        _pg_update_running(run_id)
        # V11.0: Depth-based performance tiers (2026-05-10 Robin: 国产模型为主)
        if depth == "quick":
            edge_mode = "none"       # No edge agents → 5x faster
            max_rounds = min(max_rounds, 1)
            print(f"[V11.0] Quick mode: edge=none, rounds={max_rounds}")
        elif depth == "standard":
            edge_mode = "sheng"      # Generation edges only, no ke
            max_rounds = min(max_rounds, 2)
            print(f"[V11.0] Standard mode: edge=sheng, rounds={max_rounds}")
        else:
            print(f"[V11.0] Deep mode: edge={edge_mode}, rounds={max_rounds}")
        # V10.2: P7-005 Smart topic downgrade
        edge_mode, max_rounds, _topic_note = _assess_topic_complexity(topic, depth, edge_mode, max_rounds)
        print(f"[V10.2-ASSESS] {run_id}: {_topic_note}")
        t0 = time.time()
        
        # V5.0: Delegate to engine_v2
        try:
            import importlib
            import engine_v2 as _engine_mod
            # importlib.reload(_engine_mod)  # DISABLED V5.4-STABILITY: hot-reload crashes production
            _run_engine_v2 = _engine_mod.run_flywheel
            print(f"[V5.0 PROXY] {run_id} -> engine_v2 (edge_mode={edge_mode})")
            # V9.0: Set trading domain via module attribute (avoids kwarg compat issues)
            _engine_mod._TRADING_DOMAIN = (domain == "trading")
            # V6.0: Progress callback
            def _progress_cb(**kwargs):
                _pg_update_progress(run_id, {
                    "round": kwargs.get("round_num"),
                    "max_rounds": kwargs.get("max_rounds"),
                    "phase": kwargs.get("phase", ""),
                    "score": kwargs.get("score"),
                    "verdict": kwargs.get("verdict"),
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
            _run_engine_v2(topic, max_rounds=max_rounds, interactive=False, run_id=run_id, edge_mode=edge_mode, progress_callback=_progress_cb)
            
            # V5.1: Read ALL rounds from engine DB (full fidelity)
            _edb = _engine_mod.init_db; _pjs = _engine_mod.parse_json_safe
            _econn = _edb()
            
            # Read all rounds
            _all_rounds = _econn.execute(
                'SELECT id, round_num FROM rounds WHERE run_id = ? ORDER BY round_num',
                (run_id,)
            ).fetchall()
            
            # Read all ledger entries
            _all_ledger = _econn.execute(
                "SELECT round_num, overall_score, consistency_score, novelty_score, "
                "depth_score, actionability_score, residuals, notes "
                "FROM ledger WHERE run_id = ? ORDER BY round_num",
                (run_id,)
            ).fetchall()
            
            # Build rounds array with per-element outputs
            rounds_data = []
            last_kp = {}
            last_score = 0.5
            scores_trend = []
            
            for _rd in _all_rounds:
                rid = _rd['id'] if isinstance(_rd, dict) else _rd[0]
                rnum = _rd['round_num'] if isinstance(_rd, dict) else _rd[1]
                
                # Get element outputs for this round
                _eo_round = {}
                for _row in _econn.execute('SELECT element, output_text FROM elements WHERE round_id = ?', (rid,)).fetchall():
                    elem = _row['element'] if isinstance(_row, dict) else _row[0]
                    text = (_row['output_text'] if isinstance(_row, dict) else _row[1]) or ""
                    _eo_round[elem] = text[:32000]
                
                # Get ledger for this round
                _ldg = None
                for _l in _all_ledger:
                    _lnum = _l['round_num'] if isinstance(_l, dict) else _l[0]
                    if _lnum == rnum:
                        _ldg = _l
                        break
                
                round_score = 0.5
                round_kp = {}
                round_residuals = ""
                if _ldg:
                    round_score = (_ldg['overall_score'] if isinstance(_ldg, dict) else _ldg[1]) or 0.5
                    _res_text = (_ldg['residuals'] if isinstance(_ldg, dict) else _ldg[6]) or ""
                    round_residuals = _res_text
                    try:
                        _parsed_res = json.loads(_res_text)
                        # V9.0: kunpeng fields are at top level of _parsed_res, not nested
                        # Try nested 'kunpeng' first (backward compat), then use top-level
                        _nested_kp = _parsed_res.get('kunpeng', {})
                        if _nested_kp and isinstance(_nested_kp, dict) and any(_nested_kp.values()):
                            round_kp = _nested_kp
                        else:
                            # Use top-level fields directly
                            round_kp = {k: v for k, v in _parsed_res.items() 
                                       if k in ('kun_dive','peng_soar','dao_merge','buddhist_three',
                                               'freudian_layers','data_gaps','strategic_recommendations',
                                               'core_contradiction','round_conclusion','confidence',
                                               'ke_signal_to_baihu','residuals','next_seeds')}
                    except:
                        pass
                
                scores_trend.append(round_score)
                last_score = round_score
                if round_kp:
                    last_kp = round_kp
                
                rounds_data.append({
                    'round': rnum,
                    'score': round_score,
                    'elements': _eo_round,
                    'kunpeng': _enrich_kunpeng(topic, rnum, _eo_round, round_kp),
                    'residuals_preview': round_residuals[:2000],
                })
            
            # Use last round's element outputs as top-level
            _eo = rounds_data[-1]['elements'] if rounds_data else {}
            
            # Determine verdict
            if last_score > 0.7:
                _verdict = 'converged'
            elif last_score > 0.5:
                _verdict = 'conditional'
            else:
                _verdict = 'diverging'
            
            # Check convergence trend
            _convergence_trend = 'unknown'
            if len(scores_trend) >= 2:
                if scores_trend[-1] > scores_trend[-2]:
                    _convergence_trend = 'improving'
                elif scores_trend[-1] < scores_trend[-2]:
                    _convergence_trend = 'degrading'
                else:
                    _convergence_trend = 'stable'
            
            _econn.close()
            result = {
                'topic': topic, 'domain': domain,
                'element_outputs': _eo,
                'convergence': {
                    'final_score': last_score,
                    'verdict': _verdict,
                    'scores_trend': scores_trend,
                    'trend': _convergence_trend,
                    'rounds_completed': len(rounds_data),
                },
                'kunpeng': last_kp,
                'rounds': rounds_data,
            }
        except ImportError:
            print(f"[V5.0 PROXY] engine_v2 unavailable, fallback to wuxing_pipeline_v2")
            from wuxing_pipeline_v2 import analyze
            result = analyze(topic, domain=domain, depth=depth, max_rounds=max_rounds)
        
        elapsed = time.time() - t0
        scores = _extract_scores(result)

        # V9.0: Synchronous enrichment before publish
        try:
            from result_enrichment import enrich_sync
            result = enrich_sync(run_id, topic, result)
            print(f"[V9.0-PIPELINE] Enrichment complete for {run_id}")
        except Exception as _enrich_err:
            print(f"[V9.0-PIPELINE] Enrichment failed (non-fatal): {_enrich_err}")

        # P7-009: Quality grading
        try:
            from engine_v2 import _assess_report_quality
            quality_meta = _assess_report_quality(result)
            result["quality"] = quality_meta
            _qg = quality_meta.get("overall_grade", "?")
            _qs = quality_meta.get("overall_score", 0)
            _qf = quality_meta.get("flags", [])
            print(f"[P7-009] Quality: {_qg} ({_qs}) flags={_qf}")
        except Exception as _qe:
            print(f"[P7-009] Quality assessment error: {_qe}")
            _qg = "?"

        _pg_complete(run_id, result, scores, elapsed)

        doc_url = None
        if HAS_PUBLISHER and _qg != "?":
            for _pub_attempt in range(3):
                try:
                    pub_result = auto_publish(result, run_id)
                    if pub_result and pub_result.get("doc_url"):
                        doc_url = pub_result["doc_url"]
                        print(f"[PUBLISH] OK: {doc_url}")

                        break
                    else:
                        print(f"[PUBLISH] No doc_url returned (attempt {_pub_attempt+1}/3)")
                except Exception as pub_err:
                    print(f"[PUBLISH] Failed attempt {_pub_attempt+1}/3: {pub_err}")
                    if _pub_attempt < 2:
                        import time as _t; _t.sleep(3 * (2 ** _pub_attempt))
        

        # V11.4: Auto-deploy to website (AFTER pg_complete so DB has the result)
        try:
            import subprocess as _sp
            _tmpl = r"D:\deploy\template_v5.py"
            _wd = _sp.run(["python", _tmpl, run_id], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            if _wd.returncode == 0:
                print(f"[WEBSITE] OK: https://skycetus.cn/flywheel/analysis-{run_id.replace('run-','')}.html")
            else:
                print(f"[WEBSITE] FAIL: {_wd.stderr[:200] if _wd.stderr else 'no stderr'}")
        except Exception as _we:
            print(f"[WEBSITE] ERROR: {_we}")

        # V11.0: Knowledge Tree auto-extraction
        try:
            from kt_extractor import extract_and_store
            _score = scores[-1] if isinstance(scores, list) and scores else 0
            _kt_ok = extract_and_store(run_id, topic, _score, result)
            print(f"[KT] {'OK' if _kt_ok else 'SKIP'} for {run_id}")
        except Exception as _kt_err:
            print(f"[KT] Error (non-fatal): {_kt_err}")

        # V7.0: Grand Cycle Integration
        if HAS_GRAND_CYCLE:
            try:
                gc = get_grand_cycle()
                _gc_score = scores[-1] if isinstance(scores, list) and scores else 0
                _gc_result_data = result if isinstance(result, dict) else {}
                gc_result = gc.on_run_complete(run_id, topic, _gc_result_data, _gc_score)
                gc_meta = gc_result.get('meta', {}).get('alignment', '?')
                gc_actions = gc_result.get('improvements', {}).get('actions_taken', 0)
                print(f'[GRAND_CYCLE] Cycle #{gc_result.get("cycle",0)}: meta={gc_meta}, improvements={gc_actions}')
            except Exception as gc_err:
                print(f'[GRAND_CYCLE] Error: {gc_err}')
                import traceback as _tb; _tb.print_exc()
        if doc_url:
            _pg_save_feishu_url(run_id, doc_url)
        # V5.4: Auto-deploy to website
        deploy_url = None
        if HAS_AUTO_DEPLOY:
            try:
                deploy_result = auto_deploy_report(result, run_id)
                if deploy_result and deploy_result.get("deployed"):
                    deploy_url = deploy_result.get("url")
                    print(f"[AUTO-DEPLOY] {deploy_url}")
            except Exception as deploy_err:
                print(f"[AUTO-DEPLOY] Failed: {deploy_err}")
        
        # V5.5: Readable publisher DISABLED (P7-004: avoid double-publish)
        # Re-enable when readable format is needed as a separate product
        readable_doc_url = None
        # try:
        #     from readable_publisher import generate_readable_report
        #     readable = generate_readable_report(result, topic[:20])
        #     if readable and readable.get('markdown'):
        #         readable_doc_url = publish_readable_to_feishu(readable, topic, run_id)
        #         if readable_doc_url:
        #             print(f"[READABLE] {readable_doc_url}")
        # except Exception as re_err:
        #     print(f"[READABLE] Failed: {re_err}")

        print(f"[OK] {run_id} completed in {elapsed:.0f}s | {scores['verdict']} {scores['score']}")
                
    except Exception as e:
        _pg_error(run_id, f"{e}\n{traceback.format_exc()}")
        print(f"[ERR] {run_id}: {e}")
    finally:
        with _active_lock:
            _active_runs.pop(run_id, None)

# ---- Request Models ----

class AnalyzeRequest(BaseModel):
    topic: str
    domain: str = "general"
    depth: str = "deep"
    max_rounds: int = 3  # V5.4: increased from 2 to match engine default
    sync: bool = False
    edge_mode: str = "sheng"  # V11.0: default sheng (国产模型+快速), full only for paid/deep

# ---- Endpoints ----


# ---- Startup Cleanup (V5.1) ----
@app.on_event("startup")
async def cleanup_orphaned_runs():
    """Mark orphaned runs as interrupted and auto-resume them. V6.1 auto-resume."""
    try:
        from pg_storage import get_conn
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT run_id, topic, domain, depth, progress
                FROM public.flywheel_api_runs
                WHERE status IN ('running', 'interrupted') AND status != 'converged'
            """)
            orphaned = cur.fetchall()
            if not orphaned:
                print("[STARTUP] No orphaned runs to resume")
                return

            cur.execute("""
                UPDATE public.flywheel_api_runs
                SET status = 'interrupted',
                    error = 'Interrupted: API restarted, queued for auto-resume'
                WHERE status IN ('running', 'interrupted') AND status != 'converged'
            """)
            conn.commit()
            print(f"[STARTUP] Found {len(orphaned)} interrupted runs, queuing auto-resume...")

            import asyncio
            asyncio.get_event_loop().call_later(15.0, _schedule_auto_resumes, orphaned)
    except Exception as e:
        print(f"[STARTUP] Cleanup error: {e}")


def _schedule_auto_resumes(orphaned_runs):
    """Schedule auto-resume for interrupted runs (called 15s after startup)."""
    for run_row in orphaned_runs:
        run_id = run_row[0]
        topic = run_row[1] or ""
        domain = run_row[2] or ""
        depth = run_row[3] or "standard"
        progress = run_row[4] or {}

        completed_rounds = 0
        if isinstance(progress, dict):
            completed_rounds = progress.get("round", 0)

        print(f"[AUTO-RESUME] Resuming {run_id} (completed {completed_rounds} rounds)")

        try:
            from pg_storage import get_conn
            with get_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE public.flywheel_api_runs
                    SET status = 'running',
                        error = NULL
                    WHERE run_id = %s AND status = 'interrupted'
                """, (run_id,))
                if cur.rowcount == 0:
                    print(f"[AUTO-RESUME] {run_id} already handled, skipping")
                    conn.rollback()
                    continue
                conn.commit()

            max_rounds = 3
            output_format = "full"
            future = _executor.submit(
                _run_pipeline, run_id, topic, domain, depth, max_rounds, output_format
            )
            with _active_lock:
                _active_runs[run_id] = future
            print(f"[AUTO-RESUME] {run_id} resubmitted to executor")
        except Exception as e:
            print(f"[AUTO-RESUME] Failed to resume {run_id}: {e}")
            try:
                from pg_storage import get_conn
                with get_conn() as conn2:
                    cur2 = conn2.cursor()
                    cur2.execute("""
                        UPDATE public.flywheel_api_runs
                        SET status = 'error',
                            error = %s,
                            finished_at = NOW()
                        WHERE run_id = %s
                    """, (f"Auto-resume failed: {e}", run_id))
                    conn2.commit()
            except:
                pass


@app.get("/queue")
async def queue_status():
    """Queue and backpressure status"""
    # Redis queue status
    if USE_REDIS_QUEUE and redis_queue:
        redis_status = redis_queue.get_status()
        return {
            "queue_type": "redis",
            **redis_status,
            "max_workers": MAX_WORKERS,
            "queue_limit": QUEUE_LIMIT,
            "max_queue_depth": MAX_QUEUE_DEPTH
        }
    
    # Fallback to local
    with _priority_lock:
        q_depth = len(_priority_queue)
        q_paid = sum(1 for p in _priority_queue if p[0] == 0)
        q_free = q_depth - q_paid
    with _active_lock:
        active = len(_active_runs)
    wait_time = q_depth * ESTIMATED_TIME_PER_RUN // max(MAX_WORKERS, 1)
    return {
        "queue_type": "local",
        "queue_depth": q_depth,
        "active_runs": active,
        "paid_in_queue": q_paid,
        "free_in_queue": q_free,
        "max_workers": MAX_WORKERS,
        "queue_limit": QUEUE_LIMIT,
        "max_queue_depth": MAX_QUEUE_DEPTH,
        "estimated_wait_seconds": wait_time,
        "backpressure": "high" if q_depth > QUEUE_LIMIT * 0.8 else "medium" if q_depth > QUEUE_LIMIT * 0.5 else "low"
    }

@app.get("/health")
async def health():
    with _active_lock:
        active = len(_active_runs)
    return {
        "status": "ok",
        "version": VERSION,
        "port": PORT,
        "storage": "postgresql",
        "auto_publish": HAS_PUBLISHER,
        "concurrency": {
            "max_workers": MAX_WORKERS,
            "active_runs": active,
            "llm_semaphore_limit": LLM_SEMAPHORE_LIMIT,
            "queue_limit": QUEUE_LIMIT
        }
    }

@app.get("/mode")
async def get_mode():
    """Get current flywheel mode (standard/flagship/local)."""
    from engine_v2 import FLYWHEEL_MODE, ELEMENT_MODEL_ROUTE
    mode_names = {
        "standard": "标准模式（国产模型：Qwen+Kimi+MiniMax 包月）",
        "flagship": "旗舰模式（国际模型：GPT-5.5+Claude Opus+Grok-4）",
        "local": "本地模式（单模型快速分析）",
    }
    return {
        "mode": FLYWHEEL_MODE,
        "mode_name": mode_names.get(FLYWHEEL_MODE, FLYWHEEL_MODE),
        "routing": ELEMENT_MODEL_ROUTE,
        "cost_estimate": {
            "standard": "~¥0.5-2/次（包月免费）",
            "flagship": "~$5-10/次（按量付费）",
            "local": "~¥0（包月免费）",
        }
    }

@app.post("/mode")
async def set_mode(req: dict, _auth: bool = Depends(verify_token)):
    """Switch flywheel mode: standard/flagship/local."""
    import engine_v2
    mode = req.get("mode", "standard")
    if mode not in ("standard", "flagship", "local"):
        return {"error": "mode must be one of: standard, flagship, local"}

    # Update module-level variable
    engine_v2.FLYWHEEL_MODE = mode

    # Rebuild routing
    if mode == "flagship":
        engine_v2.ELEMENT_MODEL_ROUTE = engine_v2.ELEMENT_MODEL_ROUTE_FLAGSHIP.copy()
    elif mode == "local":
        local_model = req.get("local_model", "qwen")
        engine_v2.ELEMENT_MODEL_ROUTE = {
            "qinglong": local_model, "zhuque": local_model,
            "diting": local_model, "baihu": local_model,
            "xuanwu": local_model, "verifier": local_model,
        }
    else:
        engine_v2.ELEMENT_MODEL_ROUTE = engine_v2.ELEMENT_MODEL_ROUTE_STANDARD.copy()

    mode_names = {
        "standard": "标准模式（国产模型：Qwen+Kimi+MiniMax 包月）",
        "flagship": "旗舰模式（国际模型：GPT-5.5+Claude Opus+Grok-4）",
        "local": "本地模式（单模型快速分析）",
    }
    return {
        "mode": mode,
        "mode_name": mode_names[mode],
        "routing": engine_v2.ELEMENT_MODEL_ROUTE,
        "message": f"已切换到{mode_names[mode]}",
    }

@app.get("/status")
async def status():
    counts = _pg_count_status()
    with _active_lock:
        active = len(_active_runs)
    return {
        "version": VERSION,
        "storage": "postgresql",
        "auto_publish": HAS_PUBLISHER,
        "active_runs": active,
        "max_workers": MAX_WORKERS,
        "runs": counts
    }


@app.get("/metrics")
async def metrics():
    from llm_router import get_metrics
    from fastapi.responses import PlainTextResponse
    llm = get_metrics()
    counts = _pg_count_status()
    with _active_lock:
        active = len(_active_runs)
    prom = []
    prom.append(f'flywheel_active_runs {active}')
    for s, c in counts.items():
        prom.append(f'flywheel_total_runs{{status="{s}"}} {c}')
    prom.append(f'llm_calls_total {llm.get("total_calls", 0)}')
    prom.append(f'llm_calls_successful {llm.get("successful", 0)}')
    prom.append(f'llm_calls_failed {llm.get("failed", 0)}')
    prom.append(f'llm_calls_retried {llm.get("retries", 0)}')
    prom.append(f'llm_calls_rate_limited {llm.get("rate_limited", 0)}')
    for prov, stats in llm.get("by_provider", {}).items():
        prom.append(f'llm_provider_calls{{provider="{prov}"}} {stats["calls"]}')
        prom.append(f'llm_provider_success{{provider="{prov}"}} {stats["success"]}')
    nl = chr(10)
    return PlainTextResponse(nl.join(prom) + nl, media_type="text/plain")

@app.get("/runs")
async def list_runs(limit: int = 50):
    runs = _pg_list_runs(limit)
    return {"runs": runs, "count": len(runs)}

@app.get("/result/{run_id}")
async def get_result(run_id: str):
    entry = _pg_get_run(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="run_id not found")
    
    # V6.0: Include progress + resumable flag
    _progress = {}
    try:
        from pg_storage import get_conn as _gc
        with _gc() as _pconn:
            _pcur = _pconn.cursor()
            _pcur.execute("SELECT progress FROM flywheel_api_runs WHERE run_id = %s", (run_id,))
            _prow = _pcur.fetchone()
            if _prow and _prow[0]:
                _progress = _prow[0] if isinstance(_prow[0], dict) else json.loads(_prow[0])
    except: pass
    resp = {
        "run_id": entry["run_id"],
        "status": entry["status"],
        "topic": entry["topic"],
        "started": entry["started_at"],
        "finished": entry["finished_at"],
        "verdict": entry["verdict"],
        "score": entry["score"],
        "grade": entry["grade"],
        "elapsed": entry["elapsed_sec"],
        "feishu_doc_url": entry.get("feishu_doc_url"),
        "progress": _progress,
        "resumable": entry["status"] in ("error", "interrupted"),
    }
    if entry["status"] == "completed":
        result_data = entry["result"] or {}
        # V9.0: Enrich kunpeng fields if missing
        result_data = _maybe_enrich_result(run_id, entry["topic"], result_data)
        resp["result"] = result_data
        # V5.1: Promote key fields to top level for convenience
        conv = result_data.get("convergence", {})
        resp["scores_trend"] = conv.get("scores_trend", [])
        resp["convergence_trend"] = conv.get("trend", "unknown")
        resp["rounds_completed"] = conv.get("rounds_completed", 0)
        resp["kunpeng"] = result_data.get("kunpeng", {})
        resp["rounds"] = result_data.get("rounds", [])
    elif entry["status"] == "error":
        resp["error"] = entry["error"]
    return resp

@app.post("/analyze")
async def analyze(req: AnalyzeRequest, _auth: bool = Depends(verify_token)):
    # Check queue limit
    with _active_lock:
        active = len(_active_runs)
    if active >= QUEUE_LIMIT:
        raise HTTPException(status_code=429, detail=f"Queue full ({active}/{QUEUE_LIMIT}). Try again later.")
    
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")
    
    run_id = f"run-{hashlib.md5(f'{topic}{time.time()}'.encode()).hexdigest()[:12]}"
    _pg_save_run(run_id, topic, req.domain, req.depth)
    
    if req.sync:
        _run_pipeline(run_id, topic, req.domain, req.depth, req.max_rounds, req.edge_mode)
        entry = _pg_get_run(run_id)
        return entry
    else:
        future = _executor.submit(_run_pipeline, run_id, topic, req.domain, req.depth, req.max_rounds, req.edge_mode)
        with _active_lock:
            _active_runs[run_id] = future
        return JSONResponse(
            status_code=202,
            content={
                "run_id": run_id,
                "status": "queued",
                "topic": topic,
                "domain": req.domain,
                "depth": req.depth,
                "edge_mode": req.edge_mode,
                "active_runs": active + 1,
                "max_workers": MAX_WORKERS,
                "message": f"Analysis started. Poll GET /result/{run_id}"
            }
        )

@app.post("/batch")
async def batch_analyze(topics: list[str], domain: str = "general", _auth: bool = Depends(verify_token)):
    """Submit multiple topics at once"""
    if len(topics) > 20:
        raise HTTPException(status_code=400, detail="Max 20 topics per batch")
    
    results = []
    for topic in topics:
        topic = topic.strip()
        if not topic:
            continue
        run_id = f"run-{hashlib.md5(f'{topic}{time.time()}'.encode()).hexdigest()[:12]}"
        _pg_save_run(run_id, topic, domain, "deep")
        future = _executor.submit(_run_pipeline, run_id, topic, domain, "deep", 2)
        with _active_lock:
            _active_runs[run_id] = future
        results.append({"run_id": run_id, "topic": topic})
        time.sleep(0.1)  # Slight stagger
    
    return {"submitted": len(results), "runs": results}

@app.get("/")
async def root():
    return {
        "name": "Wuxing Flywheel API",
        "version": VERSION,
        "storage": "postgresql",
        "auto_publish": HAS_PUBLISHER,
        "concurrency": f"{MAX_WORKERS} workers, {LLM_SEMAPHORE_LIMIT} LLM slots",
        "auth": "Bearer token required for POST",
        "endpoints": {
            "POST /analyze": "Start single analysis (requires auth)",
            "POST /batch": "Submit multiple topics (requires auth)",
            "GET /status": "Pipeline status counts + active workers",
            "GET /runs": "List recent runs",
            "GET /result/<run_id>": "Get full result",
            "GET /health": "Health check with concurrency info"
        }
    }

# ---- Startup ----

@app.on_event("startup")
async def startup():
    _init_table()
    print(f"Wuxing Flywheel API v{VERSION}")
    print(f"Workers: {MAX_WORKERS} | LLM slots: {LLM_SEMAPHORE_LIMIT} | Queue: {QUEUE_LIMIT}")
    print(f"Auto-publish: {HAS_PUBLISHER}")


# === Key Rotation Stats (P1-3) ===
@app.get("/key-rotation-stats")
async def key_rotation_stats():
    try:
        sys.path.insert(0, r"D:\ClawMatrix\engine")
        from key_rotation import get_rotation_stats
        return {"status": "ok", "stats": get_rotation_stats()}
    except ImportError:
        return {"status": "not_available", "message": "key_rotation module not loaded"}



# === P3-007 + P7-010: Cost Tracking ===
@app.get("/cost-summary")
async def cost_summary(_auth: bool = Depends(verify_token)):
    """Cost and usage tracking with cognitive efficiency metrics."""
    try:
        from pg_storage import get_conn
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*), COUNT(*) FILTER (WHERE status = 'completed'),
                    COUNT(*) FILTER (WHERE status = 'error'),
                    COALESCE(AVG(elapsed_sec) FILTER (WHERE status = 'completed'), 0),
                    COALESCE(SUM(elapsed_sec) FILTER (WHERE status = 'completed'), 0),
                    COALESCE(AVG(score) FILTER (WHERE status = 'completed'), 0)
                FROM flywheel_api_runs
            """)
            row = cur.fetchone()
            # Efficiency = score * 100 / elapsed_sec (higher = more efficient)
            cur.execute("""
                SELECT COUNT(*), 
                    COALESCE(AVG(score * 100.0 / NULLIF(elapsed_sec, 0)) FILTER (WHERE status = 'completed' AND elapsed_sec > 0), 0)
                FROM flywheel_api_runs
            """)
            eff_row = cur.fetchone()
            cur.execute("""
                SELECT DATE(started_at), COUNT(*),
                    COUNT(*) FILTER (WHERE status = 'completed'),
                    COALESCE(AVG(score) FILTER (WHERE status = 'completed'), 0),
                    COALESCE(SUM(elapsed_sec) FILTER (WHERE status = 'completed'), 0),
                    COALESCE(AVG(score * 100.0 / NULLIF(elapsed_sec, 0)) FILTER (WHERE status = 'completed' AND elapsed_sec > 0), 0)
                FROM flywheel_api_runs
                WHERE started_at > NOW() - INTERVAL '30 days'
                GROUP BY DATE(started_at) ORDER BY DATE(started_at) DESC LIMIT 30
            """)
            daily = [{"date": str(d[0]), "runs": d[1], "completed": d[2],
                      "avg_score": round(float(d[3]), 3), "total_seconds": round(float(d[4]), 1),
                      "efficiency": round(float(d[5]), 3) if d[5] else 0}
                     for d in cur.fetchall()]
            cur.execute("""SELECT grade, COUNT(*) FROM flywheel_api_runs
                WHERE status = 'completed' AND grade IS NOT NULL GROUP BY grade""")
            grades = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute("""SELECT domain, COUNT(*),
                COALESCE(AVG(score) FILTER (WHERE status = 'completed'), 0),
                COALESCE(AVG(score * 100.0 / NULLIF(elapsed_sec, 0)) FILTER (WHERE status = 'completed' AND elapsed_sec > 0), 0)
                FROM flywheel_api_runs GROUP BY domain ORDER BY COUNT(*) DESC""")
            domains = [{"domain": r[0], "runs": r[1], "avg_score": round(float(r[2]), 3),
                        "efficiency": round(float(r[3]), 3) if r[3] else 0}
                       for r in cur.fetchall()]
            return {"summary": {"total_runs": row[0], "completed": row[1], "errors": row[2],
                "success_rate": round(row[1]/max(row[0],1)*100, 1),
                "avg_elapsed_sec": round(float(row[3]), 1),
                "total_compute_sec": round(float(row[4]), 1),
                "total_compute_hours": round(float(row[4])/3600, 2),
                "avg_score": round(float(row[5]), 3),
                "avg_efficiency": round(float(eff_row[1]), 3),
                "efficiency_unit": "score-points-per-100sec"},
                "grade_distribution": grades, "by_domain": domains, "daily": daily}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cost summary error: {str(e)}")



# ---- Main Entry ----


# ---------------------------------------------------------------------------
# V11.0: Conflict Pool API
# ---------------------------------------------------------------------------
from conflict_detector import get_conflict_stats, get_unresolved_conflicts

@app.get("/conflicts")
async def get_conflicts(run_id: str = None, min_score: float = 0.5, limit: int = 20):
    """Get conflict pool entries."""
    try:
        from engine_v2 import DBConn
        conn = DBConn()
        if run_id:
            cur = conn.execute(
                """SELECT id, run_id, round_num, topic, element_a, element_b,
                   claim_a, claim_b, conflict_summary, divergence_score,
                   conflict_type, status, created_at
                FROM conflict_pool 
                WHERE run_id = ? AND divergence_score >= ?
                ORDER BY divergence_score DESC LIMIT ?""",
                (run_id, min_score, limit)
            )
        else:
            cur = conn.execute(
                """SELECT id, run_id, round_num, topic, element_a, element_b,
                   claim_a, claim_b, conflict_summary, divergence_score,
                   conflict_type, status, created_at
                FROM conflict_pool 
                WHERE divergence_score >= ?
                ORDER BY created_at DESC LIMIT ?""",
                (min_score, limit)
            )
        rows = cur.fetchall()
        stats = get_conflict_stats(conn, run_id)
        conn.close()
        return {"conflicts": [dict(r) for r in rows], "stats": stats}
    except Exception as e:
        return {"error": str(e), "conflicts": [], "stats": {}}

@app.get("/conflicts/stats")
async def conflict_stats():
    """Get overall conflict pool statistics."""
    try:
        from engine_v2 import DBConn
        conn = DBConn()
        stats = get_conflict_stats(conn)
        conn.close()
        return stats
    except Exception as e:
        return {"error": str(e)}



# -- V6.0: Progress & Resume Endpoints --

@app.get("/progress/{run_id}")
async def get_progress(run_id: str):
    """V6.0: Get real-time progress for a running analysis."""
    entry = _pg_get_run(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="run_id not found")
    from pg_storage import get_conn
    progress = {}
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT progress FROM flywheel_api_runs WHERE run_id = %s", (run_id,))
            row = cur.fetchone()
            if row and row[0]:
                progress = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    except Exception:
        pass
    return {
        "run_id": run_id,
        "status": entry["status"],
        "topic": entry["topic"],
        "progress": progress,
        "started_at": entry["started_at"],
        "elapsed_sec": entry.get("elapsed_sec"),
    }


@app.post("/resume/{run_id}")
async def resume_run(run_id: str, _auth: bool = Depends(verify_token)):
    """V6.0: Resume an interrupted or errored run from last checkpoint."""
    entry = _pg_get_run(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Run not found")
    # V7.0 hard exit: converged runs cannot be resumed
    if entry["status"] == "converged":
        raise HTTPException(
            status_code=409,
            detail="Run has converged (hard exit). Cannot resume. Submit a new analysis with a deeper scope if needed."
        )
    if entry["status"] not in ("error", "interrupted"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume: status={entry['status']}. Only 'error'/'interrupted' runs can be resumed."
        )
    with _active_lock:
        active = len(_active_runs)
    if active >= QUEUE_LIMIT:
        raise HTTPException(status_code=429, detail=f"Queue full ({active}/{QUEUE_LIMIT})")
    from pg_storage import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE flywheel_api_runs SET status='running', error=NULL, finished_at=NULL, "
            "progress='{}'::jsonb WHERE run_id=%s",
            (run_id,)
        )
        conn.commit()
    topic = entry["topic"]
    domain = entry.get("domain", "general")
    depth = entry.get("depth", "deep")
    future = _executor.submit(_run_pipeline, run_id, topic, domain, depth, 3, "full")
    with _active_lock:
        _active_runs[run_id] = future
    return JSONResponse(
        status_code=202,
        content={
            "run_id": run_id,
            "status": "resumed",
            "topic": topic,
            "message": f"Run resumed. Completed rounds will be skipped. Poll GET /result/{run_id}"
        }
    )


# KNOWLEDGE TREE ENDPOINTS (Auto-patched)

# DEBUG: Verify KT endpoints
@app.get("/kt-debug")
async def kt_debug():
    kt_routes = [r.path for r in app.routes if "knowledge" in r.path.lower() or "kt-" in r.path.lower()]
    return {"KT": HAS_KNOWLEDGE_TREE, "total_routes": len(app.routes), "kt_routes": kt_routes}


# ========================================

try:
    from knowledge_tree_api import (
        get_knowledge_tree_state, analyze_gaps, 
        deploy_report, update_reports_index
    )
    HAS_KNOWLEDGE_TREE = True
    print("[KT] Knowledge Tree API loaded")
except ImportError as e:
    HAS_KNOWLEDGE_TREE = False
    print(f"[KT] Knowledge Tree API not available: {e}")

@app.get("/knowledge-tree")
async def knowledge_tree():
    """Return knowledge tree current state."""
    if not HAS_KNOWLEDGE_TREE:
        return {"error": "Knowledge Tree API not loaded"}
    return get_knowledge_tree_state()

@app.get("/knowledge-tree/gaps")
async def knowledge_tree_gaps():
    """Return knowledge tree gap analysis - flywheel analysis"""
    if not HAS_KNOWLEDGE_TREE:
        return {"error": "Knowledge Tree API not loaded"}
    return analyze_gaps()

@app.post("/auto-deploy")
async def auto_deploy(run_id: str, _auth: bool = Depends(verify_token)):
    """Auto-deploy flywheel report to website after completion"""
    if not HAS_KNOWLEDGE_TREE:
        raise HTTPException(status_code=500, detail="Knowledge Tree API not loaded")
    
    # Get run data from database
    run_data = _pg_get_run(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    result = deploy_report(run_data)
    return result

@app.get("/reports-index")
async def reports_index():
    """List all deployed flywheel reports"""
    if not HAS_KNOWLEDGE_TREE:
        return {"error": "Knowledge Tree API not loaded"}
    return {"reports": update_reports_index()}

# ========================================
# AUTO-ANALYZE: Auto-select next analysis topic
# ========================================

@app.post("/auto-analyze")
async def auto_analyze(_auth: bool = Depends(verify_token)):
    """Auto-select next analysis topic based on knowledge tree gaps and start"""
    if not HAS_KNOWLEDGE_TREE:
        raise HTTPException(status_code=500, detail="Knowledge Tree API not loaded")
    
    gaps = analyze_gaps()
    summary = gaps.get("summary", {})
    
    if not summary.get("recommended_next"):
        return {"status": "no_gaps", "message": "Knowledge tree fully covers all core domains"}
    
    topic = summary["recommended_next"]
    missing = summary.get("recommended_topics", [])
    
    # Build analysis topic
    if missing:
        analysis_topic = f"{topic} domain deep analysis: {', '.join(missing[:3])}"
    else:
        analysis_topic = f"{topic} domain deep analysis"
    
    # Trigger flywheel analysis
    run_id = hashlib.md5(f"{analysis_topic}{time.time()}".encode()).hexdigest()[:12]
    run_id = f"run-{run_id}"
    
    _pg_save_run(run_id, analysis_topic, topic, "deep")
    
    future = _executor.submit(_run_pipeline, run_id, analysis_topic, topic, "deep", 3, "full")
    with _active_lock:
        _active_runs[run_id] = future
    
    return {
        "status": "started",
        "run_id": run_id,
        "topic": analysis_topic,
        "domain": topic,
        "gap_source": summary,
        "message": f"Flywheel auto-started: {analysis_topic}"
    }



@app.post("/kt-update")
async def kt_update(run_id: str, _auth: bool = Depends(verify_token)):
    from knowledge_tree_api import update_knowledge_tree
    run_data = _pg_get_run(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail="Run not found")
    result = run_data.get("result")
    if isinstance(result, str):
        import json
        result = json.loads(result)
    score = run_data.get("score", 0) or 0
    topic = run_data.get("topic", "")
    return update_knowledge_tree(run_id, topic, result, score)

@app.get("/kt-entries")
async def kt_entries():
    from knowledge_tree_api import get_kt_entries
    return get_kt_entries()


# --- Agent Task Board API (v14.1, 2026-05-24) ---
from pydantic import BaseModel
from typing import Optional, List

class TaskCreate(BaseModel):
    task_id: str
    title: str
    description: Optional[str] = None
    created_by: str
    priority: int = 0
    tags: Optional[List[str]] = None

class TaskUpdate(BaseModel):
    status: Optional[str] = None
    claimed_by: Optional[str] = None
    result_summary: Optional[str] = None
    result_path: Optional[str] = None

@app.post("/tasks")
async def api_task_create(t: TaskCreate):
    conn = _get_pg_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO agent_task_board (task_id, title, description, created_by, priority, tags) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (task_id) DO UPDATE SET title=EXCLUDED.title, description=EXCLUDED.description, priority=EXCLUDED.priority, tags=EXCLUDED.tags, updated_at=NOW()",
        (t.task_id, t.title, t.description, t.created_by, t.priority, t.tags or [])
    )
    conn.commit()
    cur.close(); conn.close()
    return {"status": "ok", "task_id": t.task_id}

@app.get("/tasks")
async def api_task_list(status: Optional[str] = None, claimed_by: Optional[str] = None):
    conn = _get_pg_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    q = "SELECT task_id, title, status, claimed_by, created_by, priority, tags, result_summary, result_path, created_at, completed_at FROM agent_task_board WHERE 1=1"
    params = []
    if status:
        q += " AND status=%s"; params.append(status)
    if claimed_by:
        q += " AND claimed_by=%s"; params.append(claimed_by)
    q += " ORDER BY priority DESC, created_at"
    cur.execute(q, params)
    rows = cur.fetchall()
    result = []
    for r in rows:
        row = dict(r)
        for k in ('created_at', 'completed_at'):
            if row.get(k):
                row[k] = row[k].isoformat()
        result.append(row)
    cur.close(); conn.close()
    return {"tasks": result, "count": len(result)}

@app.patch("/tasks/{task_id}")
async def api_task_update(task_id: str, u: TaskUpdate):
    conn = _get_pg_conn()
    cur = conn.cursor()
    sets, vals = [], []
    if u.status is not None:
        sets.append("status=%s"); vals.append(u.status)
        if u.status == "claimed" and u.claimed_by:
            sets.append("claimed_by=%s"); vals.append(u.claimed_by)
            sets.append("claimed_at=NOW()")
        if u.status == "done":
            sets.append("completed_at=NOW()")
    if u.result_summary is not None:
        sets.append("result_summary=%s"); vals.append(u.result_summary)
    if u.result_path is not None:
        sets.append("result_path=%s"); vals.append(u.result_path)
    sets.append("updated_at=NOW()")
    vals.append(task_id)
    cur.execute(f"UPDATE agent_task_board SET {', '.join(sets)} WHERE task_id=%s", vals)
    conn.commit()
    cur.close(); conn.close()
    return {"status": "ok", "task_id": task_id}


# ---- Trinity Engine (P12: WAGI×PMEORT×Flywheel) ----

_trinity_results = {}
_trinity_lock = __import__('threading').Lock()

def _run_trinity_bg(run_id, topic, max_rounds, mode):
    """Background worker for trinity analysis."""
    try:
        from engine_v3 import run_trinity, load_ccp_state
        prior_ccp = load_ccp_state()
        result = run_trinity(topic=topic, max_rounds=int(max_rounds), mode=mode, prior_ccp=prior_ccp)
        with _trinity_lock:
            _trinity_results[run_id] = {
                "status": "completed",
                "engine": "trinity_v3.0",
                "run_id": result["run_id"],
                "topic": result["topic"],
                "elapsed": round(result["elapsed"], 1),
                "pmeort": result.get("pmeort", {}),
                "flywheel_rounds": len(result.get("flywheel", {}).get("rounds", []) if isinstance(result.get("flywheel"), dict) else []),
                "ccp_after": result.get("ccp_after", {}),
                "consciousness_level": result.get("consciousness_level", 0),
                "feedback": result.get("feedback", {}),
            }
    except Exception as e:
        with _trinity_lock:
            _trinity_results[run_id] = {"status": "error", "error": str(e), "run_id": run_id}

@app.post("/trinity")
async def trinity_analyze(request: dict = None, _auth: bool = Depends(verify_token)):
    """Trinity Engine v3.0 — WAGI × PMEORT × 飞轮 三元合一分析 (async queue)"""
    if request is None:
        request = {}
    topic = request.get("topic", request.get("query", ""))
    if not topic:
        raise HTTPException(status_code=400, detail="Missing 'topic' parameter")
    max_rounds = request.get("rounds", request.get("max_rounds", 3))
    mode = request.get("mode", "full")
    
    import hashlib, time as _time
    run_id = f"tri-{hashlib.md5(f'{topic}{_time.time()}'.encode()).hexdigest()[:12]}"
    
    future = _executor.submit(_run_trinity_bg, run_id, topic, max_rounds, mode)
    with _active_lock:
        _active_runs[run_id] = future
    
    return JSONResponse(
        status_code=202,
        content={
            "run_id": run_id,
            "status": "queued",
            "topic": topic,
            "mode": mode,
            "message": f"Trinity analysis started. Poll GET /trinity/result/{run_id}"
        }
    )

@app.get("/trinity/result/{run_id}")
async def trinity_result(run_id: str):
    """Get trinity analysis result by run_id."""
    with _trinity_lock:
        result = _trinity_results.get(run_id)
    if result:
        return result
    
    with _active_lock:
        future = _active_runs.get(run_id)
    if future and not future.done():
        return {"status": "running", "run_id": run_id}
    
    return {"status": "not_found", "run_id": run_id}


if __name__ == "__main__":
    print(f"[STARTUP] Wuxing Flywheel API {VERSION} starting on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

# ========================================
