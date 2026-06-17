#!/usr/bin/env python3

# ============================================================
# DATABASE: PostgreSQL ONLY (via pg_storage)
# SQLite permanently disabled. See sqlite_guard.py
# Decision: Robin, 2026-05-02. Commit: 12ee709
# ============================================================
import sqlite_guard  # Blocks accidental sqlite3.connect()


"""

SkyCetus CaaS Gateway v2.0 — 五行飞轮认知即服务

Production gateway with:

- Full 5-phase pipeline (木→火→土→金→水)

- IP-based rate limiting (3/day free)

- Knowledge base integration (Hub residuals + L0 materials)

- Residual inheritance across analyses

- API key support for paid tier

"""



import json, time, os, hashlib, subprocess, sys, re

from datetime import datetime
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from water_engine import extract_residual as water_extract, get_convergence_report as water_convergence, generate_seeds_from_residuals as water_generate_seeds, xiangke_constrain_fire as water_constrain_fire, get_stats as water_stats
    WATER_AVAILABLE = True
    print("[OK] Water engine (Xuanwu/North) loaded")
except ImportError as _we:
    WATER_AVAILABLE = False
    print(f"[WARN] Water engine not available: {_we}")

try:
    from wood_engine import create_seed as wood_create, mutate_seed as wood_mutate, convert_to_task as wood_convert, list_seeds as wood_list, get_stats as wood_stats, xiangke_challenge_earth as wood_challenge_earth
    WOOD_AVAILABLE = True
    print("[OK] Wood engine (Qinglong/East) loaded")
except ImportError as _woe:
    WOOD_AVAILABLE = False
    print(f"[WARN] Wood engine not available: {_woe}")

try:
    from fire_engine import execute_task as fire_execute, decompose_task as fire_decompose, get_stats as fire_stats, xiangke_challenge_metal as fire_challenge_metal
    FIRE_AVAILABLE = True
    print("[OK] Fire engine (Zhuque/South) loaded")
except ImportError as _fe:
    FIRE_AVAILABLE = False
    print(f"[WARN] Fire engine not available: {_fe}")

try:
    from metal_validator_v2 import validate as metal_validate, prune_seeds, get_audit_history, get_audit_stats
    METAL_AVAILABLE = True
    print("[OK] Metal validator v2 loaded")
except ImportError as _e:
    METAL_AVAILABLE = False
    print(f"[WARN] metal_validator_v2 not found: {_e}"), date

from typing import Optional



# Knowledge Store + Xiangke integration

try:

    from knowledge_store import store_result, query_knowledge, get_context_for_pipeline, list_all_keywords

    HAS_KB = True

except ImportError:

    HAS_KB = False

    print("[WARN] knowledge_store.py not found")



try:

    from xiangke_engine import XiangkeEngine

    HAS_XIANGKE = True

except ImportError:

    HAS_XIANGKE = False

    print("[WARN] xiangke_engine.py not found")



try:

    from trust_rate_limiter import register_endpoints as register_rate_endpoints

    HAS_RATE_LIMITER = True

    print("[CaaS] Trust rate limiter loaded")

except ImportError:

    HAS_RATE_LIMITER = False

    print("[WARN] trust_rate_limiter.py not found")



try:

    from quad_model_router_v4 import route as quad_route, MODELS as QUAD_MODELS

    HAS_ROUTER = True

    print(f"[CaaS] Quad router loaded: {len(QUAD_MODELS)} models")

except ImportError:

    HAS_ROUTER = False

    print("[WARN] quad_model_router_v4.py not found, using MiniMax only")

# Wuxing Governance Modules (v2.6)
try:
    from wuxing_balance import analyze_balance, format_balance_report, classify_task, get_rebalance_recommendations
    HAS_BALANCE = True
    print("[CaaS] Wuxing balance monitor loaded")
except ImportError:
    HAS_BALANCE = False
    print("[WARN] wuxing_balance.py not found")

try:
    from phase_affinity import PhaseAffinityEngine
    affinity_engine = PhaseAffinityEngine()
    HAS_AFFINITY = True
    print("[CaaS] Phase affinity engine loaded")
except ImportError:
    HAS_AFFINITY = False
    affinity_engine = None
    print("[WARN] phase_affinity.py not found")

try:
    from bootstrap_graduation import BootstrapGraduation
    graduation_system = BootstrapGraduation()
    HAS_BOOTSTRAP = True
    print("[CaaS] Bootstrap graduation loaded")
except ImportError:
    HAS_BOOTSTRAP = False
    graduation_system = None
    print("[WARN] bootstrap_graduation.py not found")
try:
    from lux_engine import distribute_lux, get_balance, get_leaderboard, get_system_pool_total, get_distribution_stats
    HAS_LUX = True
    print("[CaaS] Lux distribution engine loaded")
except ImportError:
    HAS_LUX = False
    print("[WARN] lux_engine.py not found")

try:
    from xiangsheng_trigger import XiangshengTrigger, CHAIN_NAMES, TRANSITIONS
    xiangsheng = XiangshengTrigger()
    HAS_XIANGSHENG = True
    print("[CaaS] Xiangsheng chain trigger loaded")
except ImportError:
    HAS_XIANGSHENG = False
    xiangsheng = None
    print("[WARN] xiangsheng_trigger.py not found")




# Phase-to-model routing: each phase uses its optimal model

PHASE_MODEL_MAP = {

    "wood": {"beast": "qinglong", "task_type": "creative"},     # creative divergence

    "fire": {"beast": "zhuque", "task_type": "analysis"},       # structured execution

    "earth": {"beast": None, "task_type": "chinese"},           # grounding in Chinese context

    "metal": {"beast": "baihu", "task_type": "reasoning"},      # adversarial challenge

    "water": {"beast": "xuanwu", "task_type": "analysis"},      # convergence analysis

}

from fastapi import FastAPI, HTTPException, Request, Response


# PostgreSQL storage layer
try:
    import pg_storage
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False

try:
    import hub_connector
    HUB_AVAILABLE = True
except ImportError:
    HUB_AVAILABLE = False

try:
    import wuxing_pipeline_v2
    PIPELINE_V2 = True
except ImportError:
    PIPELINE_V2 = False
from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import HTMLResponse

from pydantic import BaseModel

import uvicorn

import uuid

from concurrent.futures import ThreadPoolExecutor



# Async job queue

_job_store = {}  # job_id -> {status, result, started, completed, keyword, domain, depth}

_job_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="caas-job")



# ─── Config ──────────────────────────────────────────────────────────────────



PORT = 19106

HUB_URL = "http://localhost:19104"

L0_DATA = r"D:\ClawMatrix\caas_data\l0_materials.json"

# DB_PATH = r"D:\ClawMatrix\caas_data\caas.db"  # PG only

# RESIDUAL_DB = r"D:\ClawMatrix\caas_data\residuals.db"  # PG only



MINIMAX_KEY = os.environ.get("MINIMAX_KEY",

    "sk-cp-wBP8BgBJbLsGCUshk0x5oYKbiydygx-RMk0iJDhANE6epg6gMnRBRg5hPN1eioB3PURgoeEiv7o2kLE7vOqibkLG1_3daWsmo-7kkkVxS4t7guHj7exDGwo")

MINIMAX_URL = "https://api.minimaxi.com/anthropic/v1/messages"



FREE_LIMIT = 3  # per IP per day

PAID_LIMIT = 100  # per key per day



# ─── App ─────────────────────────────────────────────────────────────────────



VERSION = "3.6-pg-primary"

app = FastAPI(
    title="SkyCetus CaaS — 五行飞轮认知即服务",

    version="2.0",

    description="Industry-cognition-driven execution optimization layer"

)


# Initialize PostgreSQL tables on startup
@app.on_event("startup")
async def startup_pg():
    if PG_AVAILABLE:
        try:
            pg_storage.init_tables()
            print("[CaaS] PostgreSQL storage initialized")
        except Exception as e:
            print(f"[CaaS] PG init warning: {e}")
# Register trust rate limiter endpoints

if HAS_RATE_LIMITER:

    register_rate_endpoints(app)

    print("[CaaS] Rate limiter endpoints registered at /api/v1/rate/*")



app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])



# ─── Database ────────────────────────────────────────────────────────────────



def init_db():
    """Initialize - PostgreSQL only via pg_storage."""
    pass  # All tables managed by pg_storage

def check_rate_limit(ip: str, api_key: str = None) -> tuple:

    # PG primary path
    if PG_AVAILABLE:
        try:
            allowed, remaining, total = pg_storage.rate_limit_check(ip, api_key)
            return allowed, remaining, total
        except Exception:
            raise  # PG is primary

def log_usage(ip: str, api_key: str, keyword: str, domain: str, phases: str, duration_ms: int):

    # PG primary
    if PG_AVAILABLE:
        try:
            pg_storage.usage_log(ip, api_key, keyword, domain, phases, duration_ms)
            pg_storage.rate_limit_record(ip, api_key)
        except Exception:
            raise  # PG is primary

def call_llm(prompt: str, max_tokens: int = 4096, temperature: float = 0.7) -> str:

    """Call MiniMax via curl subprocess (avoids Windows SSL EOF issues)"""

    body = json.dumps({

        "model": "MiniMax-M2.7",

        "max_tokens": max_tokens,

        "temperature": temperature,

        "thinking": {"type": "enabled", "budget_tokens": 1000},

        "messages": [{"role": "user", "content": prompt}]

    })



    try:

        result = subprocess.run(

            ["curl", "-s", "-X", "POST", MINIMAX_URL,

             "-H", "Content-Type: application/json",

             "-H", f"Authorization: Bearer {MINIMAX_KEY}",

             "-d", "@-", "--max-time", "120"],

            input=body.encode(), capture_output=True, timeout=130

        )

        if result.returncode != 0:

            return f"[LLM Error: curl exit {result.returncode}]"



        data = json.loads(result.stdout)

        for block in data.get("content", []):

            if block.get("type") == "text":

                return block.get("text", "")

        return str(data)

    except Exception as e:

        return f"[LLM Error: {e}]"



# ─── Knowledge Base ─────────────────────────────────────────────────────────



def get_related_knowledge(keyword: str, domain: str = None) -> str:

    """Pull related knowledge from L0 materials + Hub residuals + past analyses"""

    context_parts = []



    # 1. L0 Materials

    if os.path.exists(L0_DATA):

        try:

            with open(L0_DATA, "r", encoding="utf-8") as f:

                materials = json.load(f)

            matches = []

            kw_lower = keyword.lower()

            for cat, items in materials.items():

                for m in items:

                    name = m.get("name", "").lower()

                    name_en = m.get("name_en", "").lower()

                    if kw_lower in name or kw_lower in name_en or name in kw_lower:

                        matches.append(m)

            if matches:

                context_parts.append("=== L0 Materials Data ===")

                for m in matches[:3]:

                    context_parts.append(json.dumps(m, ensure_ascii=False, indent=2))

        except:

            pass



    # 2. Past residuals

    try:

        # PostgreSQL status query
        import pg_storage as _pgs
        with _pgs.get_conn() as _conn:
            _cur = _conn.cursor()
            _cur.execute("SELECT COUNT(*) FROM residuals")
            res_count = _cur.fetchone()[0]
            _cur.execute("SELECT COUNT(*) FROM analyses")
            analysis_count = _cur.fetchone()[0]

        if rows:

            context_parts.append("=== Historical Residuals ===")

            for kw, res, conf in rows:

                context_parts.append(f"- [{kw}] (conf:{conf}): {res[:200]}")

    except:

        pass



    # 3. Past analyses

    try:

        # PostgreSQL status query
        import pg_storage as _pgs
        with _pgs.get_conn() as _conn:
            _cur = _conn.cursor()
            _cur.execute("SELECT COUNT(*) FROM residuals")
            res_count = _cur.fetchone()[0]
            _cur.execute("SELECT COUNT(*) FROM analyses")
            analysis_count = _cur.fetchone()[0]

        if rows:

            context_parts.append("=== Prior Analyses ===")

            for kw, res in rows:

                context_parts.append(f"[{kw}]: {str(res)[:500]}")

    except:

        pass



    return "\n".join(context_parts) if context_parts else ""



def save_residuals(keyword: str, domain: str, residuals: list, source: str = "caas"):
    """Save residuals - PostgreSQL only."""
    if PG_AVAILABLE:
        try:
            pg_storage.residual_save(keyword, domain, residuals, source)
        except Exception:
            pass

def save_analysis(keyword: str, domain: str, result: dict, phases: str, duration_ms: int):
    """Save analysis - PostgreSQL only."""
    if PG_AVAILABLE:
        try:
            pg_storage.analysis_save(keyword, domain, result, phases, duration_ms)
        except Exception:
            pass


# === Phase Prompt Templates (restored from v4.3) ===
PHASE_PROMPTS = {

    "wood": """你是五行飞轮·青龙引擎（木/种子发散）。

任务：对「{keyword}」进行广角扫描，生成多样化种子。

{context}

要求：

1. 列出5-8个不同角度的分析种子（含反直觉角度）

2. 每个种子标注信息确定性（高/中/低）

3. 识别关键信息空白

4. 输出纯JSON格式：

{{"seeds": [{{"angle": "...", "rationale": "...", "certainty": "高/中/低"}}], "info_gaps": ["..."]}}""",



    "fire": """你是五行飞轮·朱雀引擎（火/结构化执行）。

任务：基于青龙种子，对「{keyword}」进行结构化分析。

青龙种子：{prev_output}

{context}

要求：

1. 选取最有价值的3-5个种子展开深度分析

2. 每个分析必须包含具体数据、时间线、可执行建议

3. 输出纯JSON格式：

{{"analyses": [{{"seed": "...", "findings": "...", "data_points": ["..."], "actions": ["..."], "timeline": "..."}}], "execution_score": 0.0}}""",



    "earth": """你是五行飞轮·中央引擎（土/现实校验）。

任务：将朱雀分析结果对「{keyword}」接地——连接真实世界。

朱雀分析：{prev_output}

{context}

要求：

1. 每个结论回答：谁是真实用户？能否立即验证？如何知道错了？

2. 识别最高不确定性结论，给出验证方法

3. 输出纯JSON格式：

{{"reality_checks": [{{"conclusion": "...", "user": "...", "verification": "...", "failure_signal": "..."}}], "ground_truth_score": 0.0, "next_actions": ["..."]}}""",



    "metal": """你是五行飞轮·白虎引擎（金/对抗验证）。

任务：对「{keyword}」的分析进行红队攻击。

土校验结果：{prev_output}

{context}

要求：

1. 攻击每个主要结论——找最强反论

2. 标记每个结论：🟢稳固 / 🟡条件性 / 🔴脆弱

3. 找出3个如果错误会推翻整个分析的假设

4. 输出纯JSON格式：

{{"attacks": [{{"target": "...", "counter": "...", "robustness": "green/yellow/red"}}], "fatal_assumptions": ["..."], "adversarial_score": 0.0}}""",



    "water": """你是五行飞轮·玄武引擎（水/认知收敛）。

任务：综合全部五行分析，对「{keyword}」给出最终认知收敛。

白虎攻击结果：{prev_output}

原始种子：{wood_output}

{context}

要求：

1. 只保留经过对抗验证的结论，标注置信度(0-1)

2. 提取可复用的认知模式

3. 列出残差（本次分析无法解决的问题）

4. 第一性原理总结（物理/信息论/热力学/博弈论层面）

5. 输出纯JSON格式：

{{"conclusions": [{{"text": "...", "confidence": 0.0}}], "patterns": ["..."], "residuals": [{{"text": "...", "confidence": 0.0}}], "first_principles": "...", "convergence_score": 0.0}}"""

}

def run_pipeline(keyword: str, domain: str = None, depth: str = "standard") -> dict:

    """Execute the full 5-phase flywheel pipeline"""

    context = get_related_knowledge(keyword, domain)

    context_str = f"\n已知背景知识：\n{context}" if context else ""



    results = {}

    phase_order = ["wood", "fire", "earth", "metal", "water"]

    phase_names = {"wood": "青龙·种子", "fire": "朱雀·执行", "earth": "土·校验",

                   "metal": "白虎·对抗", "water": "玄武·收敛"}



    prev_output = ""

    wood_output = ""



    for phase in phase_order:

        prompt_template = PHASE_PROMPTS[phase]

        prompt = prompt_template.format(

            keyword=keyword,

            context=context_str,

            prev_output=prev_output[:3000],

            wood_output=wood_output[:2000]

        )



        # Adjust temperature by phase

        temp = {"wood": 0.9, "fire": 0.5, "earth": 0.3, "metal": 0.8, "water": 0.3}

        # Multi-model routing: use optimal model per phase

        if HAS_ROUTER:

            routing = PHASE_MODEL_MAP.get(phase, {"beast": None, "task_type": "default"})

            try:

                routed = quad_route(prompt, task_type=routing["task_type"],

                                   beast=routing.get("beast"), max_tokens=3000)

                raw = routed.get("response", "")

                model_used = routed.get("model", "unknown")

                if not raw:

                    raise ValueError("Empty response from router")

            except Exception as e:

                # Fallback to MiniMax

                raw = call_llm(prompt, max_tokens=3000, temperature=temp.get(phase, 0.7))

                model_used = "MiniMax-M2.7 (fallback)"

        else:

            raw = call_llm(prompt, max_tokens=3000, temperature=temp.get(phase, 0.7))

            model_used = "MiniMax-M2.7"



        # Try parse JSON

        parsed = None

        try:

            clean = raw.strip()

            if clean.startswith("```"):

                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]

            # Find JSON object in response

            json_match = re.search(r'\{[\s\S]*\}', clean)

            if json_match:

                parsed = json.loads(json_match.group())

        except:

            pass



        results[phase] = {

            "phase": phase_names[phase],

            "output": parsed if parsed else raw,

            "raw": parsed is None,

            "model": model_used if 'model_used' in dir() else "unknown"

        }



        prev_output = json.dumps(parsed, ensure_ascii=False) if parsed else raw

        if phase == "wood":

            wood_output = prev_output



        # Apply xiangke constraints after metal

        if phase == "metal" and HAS_XIANGKE:

            xk = XiangkeEngine()

            xk_result = xk.apply_constraints(results)

            results["_xiangke"] = {

                "adjustments": xk_result["adjustments"],

                "active_constraints": xk.get_balance_report()["active_constraints"]

            }

            # Inject water prompt modifiers into context

            water_mod = xk.get_prompt_modifiers("water")

            if water_mod:

                context_str = context_str + "\n" + water_mod



        # Compressed mode: skip metal+water

        if depth == "compressed" and phase == "earth":

            break



    return results



# ─── Request Models ──────────────────────────────────────────────────────────



class AnalyzeRequest(BaseModel):

    keyword: str

    domain: Optional[str] = None

    depth: Optional[str] = "standard"  # standard / compressed / deep



# ─── Endpoints ───────────────────────────────────────────────────────────────



@app.get("/", response_class=HTMLResponse)

def landing():

    return """<!DOCTYPE html><html><head><meta charset="utf-8">

<title>SkyCetus CaaS — 五行飞轮认知即服务</title>

<style>

body{font-family:-apple-system,system-ui,sans-serif;background:#0a0a0a;color:#e0e0e0;

display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0}

.c{max-width:700px;padding:40px;text-align:center}

h1{font-size:2.2rem;background:linear-gradient(135deg,#60a5fa,#a78bfa);

-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}

.sub{color:#64748b;font-size:1.1rem;margin-bottom:40px}

.ep{background:#111;border:1px solid #1e293b;border-radius:8px;padding:20px;

margin:12px 0;text-align:left}

.ep h3{color:#60a5fa;margin:0 0 8px}

code{background:#1e293b;padding:2px 6px;border-radius:3px;font-size:0.9em;color:#a78bfa}

.tag{display:inline-block;background:#1e293b;color:#94a3b8;padding:4px 10px;

border-radius:12px;font-size:0.8rem;margin:4px}

.q{color:#64748b;font-size:0.85rem;margin-top:30px}

a{color:#60a5fa}

</style></head><body><div class="c">

<h1>SkyCetus CaaS</h1>

<p class="sub">五行飞轮认知即服务 · Cognition as a Service</p>

<p>产业认知驱动的执行优化层<br>

<span style="color:#64748b">理想模型决定下限，人类残差决定上限</span></p>



<div class="ep"><h3>POST /caas/analyze</h3>

<p>Full 5-phase flywheel analysis</p>

<code>{"keyword": "碳化硅", "domain": "半导体", "depth": "standard"}</code>

<div><span class="tag">木·种子</span><span class="tag">火·执行</span>

<span class="tag">土·校验</span><span class="tag">金·对抗</span><span class="tag">水·收敛</span></div></div>



<div class="ep"><h3>GET /caas/status</h3>

<p>Service health, Hub connection, knowledge base stats</p></div>



<div class="ep"><h3>GET /caas/materials</h3>

<p>Browse L0 materials database (42 materials × 8 chains)</p>

<code>?domain=半导体&tier=S</code></div>



<div class="ep"><h3>GET /caas/residuals</h3>

<p>View accumulated cognitive residuals</p>

<code>?keyword=碳化硅&limit=10</code></div>



<p class="q">Free tier: 3 analyses/day per IP<br>

API key: <a href="mailto:contact@skycetus.cn">contact@skycetus.cn</a> for paid access<br><br>

<a href="https://github.com/binbinyu99-crypto/wuxing-flywheel">GitHub</a> ·

<a href="https://skycetus.cn">SkyCetus</a></p>

</div></body></html>"""





# === Async Job Queue ===



def _run_job(job_id, keyword, domain, depth, client_ip):

    """Background job runner"""

    try:

        _job_store[job_id]["status"] = "running"

        result = run_pipeline(keyword, domain, depth)

        _job_store[job_id]["status"] = "completed"

        _job_store[job_id]["result"] = result

    except Exception as e:

        _job_store[job_id]["status"] = "failed"

        _job_store[job_id]["error"] = str(e)

    _job_store[job_id]["completed"] = time.time()



@app.post("/caas/analyze/async")

async def analyze_async(request: Request):

    """Submit analysis as async job. Returns job_id immediately."""

    data = await request.json()

    keyword = data.get("keyword", "")

    domain = data.get("domain", "general")

    depth = data.get("depth", "standard")

    client_ip = request.client.host if request.client else "unknown"



    if not keyword:

        raise HTTPException(400, "keyword required")



    job_id = str(uuid.uuid4())[:8]

    _job_store[job_id] = {

        "status": "queued",

        "keyword": keyword,

        "domain": domain,

        "depth": depth,

        "started": time.time(),

        "completed": None,

        "result": None,

        "error": None

    }



    _job_executor.submit(_run_job, job_id, keyword, domain, depth, client_ip)



    return {

        "job_id": job_id,

        "status": "queued",

        "poll_url": f"/caas/job/{job_id}",

        "estimated_seconds": 120 if depth == "compressed" else 400

    }



@app.get("/caas/job/{job_id}")

async def get_job(job_id: str):

    """Poll job status and get result when complete"""

    job = _job_store.get(job_id)

    if not job:

        raise HTTPException(404, f"Job {job_id} not found")



    response = {

        "job_id": job_id,

        "status": job["status"],

        "keyword": job["keyword"],

        "domain": job["domain"],

        "depth": job["depth"],

        "elapsed_seconds": round(time.time() - job["started"], 1)

    }



    if job["status"] == "completed":

        response["result"] = job["result"]

        response["duration_seconds"] = round(job["completed"] - job["started"], 1)

    elif job["status"] == "failed":

        response["error"] = job["error"]



    return response



@app.get("/caas/jobs")

async def list_jobs():

    """List all jobs"""

    jobs = []

    for jid, j in _job_store.items():

        jobs.append({

            "job_id": jid,

            "status": j["status"],

            "keyword": j["keyword"],

            "depth": j["depth"],

            "elapsed": round(time.time() - j["started"], 1)

        })

    return {"jobs": jobs, "count": len(jobs)}



@app.get("/caas/status")

def status():

    hub_ok = False

    hub_tasks = 0

    try:

        import urllib.request

        r = urllib.request.urlopen(f"{HUB_URL}/api/v1/status", timeout=3)

        d = json.loads(r.read())

        hub_ok = True

        hub_tasks = d.get("network", {}).get("tasks", {}).get("pending", 0) if isinstance(d, dict) else len(d)

    except:

        pass



    l0_count = 0

    if os.path.exists(L0_DATA):

        try:

            with open(L0_DATA, "r", encoding="utf-8") as f:

                l0 = json.load(f)

                l0_count = sum(len(v) for v in l0.values()) if isinstance(l0, dict) else len(l0)

        except:

            pass



    # Residual count

    res_count = 0

    ana_count = 0

    try:

        # PostgreSQL status query
        import pg_storage as _pgs
        with _pgs.get_conn() as _conn:
            _cur = _conn.cursor()
            _cur.execute("SELECT COUNT(*) FROM residuals")
            res_count = _cur.fetchone()[0]
            _cur.execute("SELECT COUNT(*) FROM analyses")
            analysis_count = _cur.fetchone()[0]

    except:

        pass



    return {

        "service": "SkyCetus CaaS Gateway",

        "version": VERSION,

        "hub": {"connected": hub_ok},

        "knowledge_base": {

            "l0_materials": l0_count,

            "accumulated_residuals": res_count,

            "completed_analyses": ana_count

        },

        "llm": {

            "provider": "Multi-Model" if HAS_ROUTER else "MiniMax",

            "model": "Quad Router v4" if HAS_ROUTER else "MiniMax-M2.7",

            "models": list(QUAD_MODELS.keys()) if HAS_ROUTER else ["minimax"],

            "phase_routing": {p: r["task_type"] for p, r in PHASE_MODEL_MAP.items()} if HAS_ROUTER else None

        },

        "rate_limit": {"free_tier": f"{FREE_LIMIT}/day per IP", "paid_tier": f"{PAID_LIMIT}/day per key"},

        "timestamp": datetime.now().isoformat()

    }



@app.get("/caas/materials")

def materials(domain: Optional[str] = None, tier: Optional[str] = None):

    if not os.path.exists(L0_DATA):

        raise HTTPException(404, "L0 data not loaded")

    with open(L0_DATA, "r", encoding="utf-8") as f:

        data = json.load(f)

    if domain:

        data = {k: v for k, v in data.items() if domain.lower() in k.lower()}

    if tier:

        data = {k: [m for m in v if m.get("tier", "").upper() == tier.upper()]

                for k, v in data.items()}

        data = {k: v for k, v in data.items() if v}

    total = sum(len(v) for v in data.values())

    return {"materials": data, "count": total}



@app.get("/caas/residuals")
def residuals(keyword: Optional[str] = None, limit: int = 20):
    """Query residuals - PostgreSQL only."""
    try:
        import pg_storage as _pgs
        results = _pgs.residual_query(keyword=keyword, limit=limit)
        return {"residuals": results, "source": "postgresql"}
    except Exception as e:
        return {"residuals": [], "error": str(e), "source": "postgresql"}

@app.post("/caas/analyze")

async def analyze(req: AnalyzeRequest, request: Request):

    # Rate limiting

    client_ip = request.client.host if request.client else "unknown"

    api_key = request.headers.get("X-API-Key")



    allowed, remaining, limit = check_rate_limit(client_ip, api_key)

    if not allowed:

        if api_key:

            raise HTTPException(429, {

                "error": "API key daily limit reached",

                "limit": limit,

                "reset": "midnight UTC+8"

            })

        raise HTTPException(429, {

            "error": "Free tier limit reached (3/day)",

            "remaining": 0,

            "upgrade": "Contact contact@skycetus.cn for API key",

            "tip": "Install the free skill pack: github.com/binbinyu99-crypto/wuxing-flywheel"

        })



    # Run pipeline

    start = time.time()

    results = run_pipeline(req.keyword, req.domain, req.depth)

    duration_ms = int((time.time() - start) * 1000)



    phases_run = ",".join(results.keys())



    # Extract and save residuals from water phase

    water = results.get("water", {})

    water_out = water.get("output", {})

    if isinstance(water_out, dict) and "residuals" in water_out:

        save_residuals(req.keyword, req.domain, water_out["residuals"], source="caas_v2")



    # Save full analysis

    save_analysis(req.keyword, req.domain, results, phases_run, duration_ms)



    # Store in knowledge base

    if HAS_KB:

        try:

            kb_result = store_result(req.keyword, req.domain or "general", {

                "total_rounds": 1,

                "final_residual": water_out.get("convergence_score", 0.5) if isinstance(water_out, dict) else 0.5,

                "converged": isinstance(water_out, dict) and water_out.get("convergence_score", 0) > 0.7,

                "total_elapsed": duration_ms / 1000,

                "final_conclusions": water_out.get("conclusions", []) if isinstance(water_out, dict) else [],

                "rounds": [{"phases": results}]

            })

        except Exception as e:

            kb_result = {"error": str(e)}

    else:

        kb_result = {"disabled": True}



    # Log usage

    log_usage(client_ip, api_key, req.keyword, req.domain, phases_run, duration_ms)



    return {

        "status": "success",

        "keyword": req.keyword,

        "domain": req.domain,

        "depth": req.depth,

        "phases": results,

        "meta": {

            "duration_ms": duration_ms,

            "remaining_today": remaining,

            "daily_limit": limit,

            "knowledge_sources": ["l0_materials", "hub_residuals", "prior_analyses", "knowledge_store"],

            "knowledge_base": kb_result if HAS_KB else None,

            "xiangke": results.pop("_xiangke", None)

        }

    }



@app.get("/caas/knowledge")

def knowledge(keyword: Optional[str] = None):

    if not HAS_KB:

        return {"error": "knowledge_store not available"}

    if keyword:

        data = query_knowledge(keyword)

        if data:

            return {"keyword": keyword, "data": data}

        return {"keyword": keyword, "data": None, "message": "No prior analysis found"}

    items = list_all_keywords()

    return {"entries": items, "count": len(items)}



@app.get("/caas/knowledge/context")

def knowledge_context(keyword: str):

    if not HAS_KB:

        return {"error": "knowledge_store not available"}

    ctx = get_context_for_pipeline(keyword)

    return {"keyword": keyword, "context": ctx if ctx else "No prior context available"}



# ─── Main ────────────────────────────────────────────────────────────────────





# === Wuxing Governance Endpoints (v2.6) ===



@app.get("/caas/balance")

async def get_wuxing_balance_view():

    """Get current Wuxing balance analysis"""

    analysis = analyze_balance()

    recommendations = []

    if not analysis["balanced"]:

        from wuxing_balance import get_rebalance_recommendations

        recommendations = get_rebalance_recommendations(analysis)

    return {

        "version": VERSION,

        "analysis": analysis,

        "recommendations": recommendations,

    }



@app.get("/caas/affinity/{node_id}")

async def get_node_affinity(node_id: str):

    """Get phase affinity profile for a node"""

    if not HAS_AFFINITY:
        return {"error": "phase_affinity module not available"}
    profile = affinity_engine.get_node_profile(node_id)

    return {"version": VERSION, "profile": profile}



@app.post("/caas/affinity/{node_id}/record")

async def record_affinity(node_id: str, phase: str = "earth", success: bool = True):

    """Record a task attempt for phase affinity tracking"""

    affinity_engine.record_attempt(node_id, phase, success)

    return {"version": VERSION, "recorded": True, "node": node_id, "phase": phase, "success": success}



@app.get("/caas/affinity/rank/{phase}")

async def rank_nodes_for_phase(phase: str):

    """Rank nodes for claiming a task in a given phase"""

    # Get trust scores from rate limiter

    node_trusts = {}

    for nid, score in rate_limiter._trust_cache.items():

        node_trusts[nid] = score

    if not node_trusts:

        node_trusts = {"default": 0.5}

    rankings = affinity_engine.rank_nodes_for_phase(phase, node_trusts)

    return {"version": VERSION, "phase": phase, "rankings": rankings}



@app.get("/caas/bootstrap/{node_id}")

async def get_bootstrap_status(node_id: str):

    """Get graduation status for a node"""

    if not HAS_BOOTSTRAP:
        return {"error": "bootstrap_graduation module not available"}
    status = graduation_system.get_node_status(node_id)

    return {"version": VERSION, "status": status}



@app.post("/caas/bootstrap/{node_id}/register")

async def register_node(node_id: str, initial_trust: float = 0.1):

    """Register a new node in the bootstrap system"""

    node = graduation_system.register_node(node_id, initial_trust)

    return {"version": VERSION, "registered": True, "node": node}



@app.post("/caas/bootstrap/{node_id}/event")

async def record_bootstrap_event(node_id: str, event_type: str = "task_completed", quality_score: float = None):

    """Record a graduation-relevant event"""

    result = graduation_system.record_event(node_id, event_type, quality_score)

    return {"version": VERSION, "event_recorded": True, "graduation_check": result}



@app.post("/caas/bootstrap/{node_id}/graduate")

async def graduate_node(node_id: str):

    """Attempt to promote a node to the next tier"""

    result = graduation_system.graduate(node_id)

    return {"version": VERSION, "result": result}






# === Lux Distribution Endpoints (v2.7) ===

@app.post("/caas/lux/distribute")
async def distribute_lux_endpoint(
    task_id: str, executor_id: str, creator_id: str,
    validator_id: str = None, complexity: str = "standard", quality: str = "good"
):
    """Distribute Lux rewards for a completed task"""
    if not HAS_LUX:
        return {"error": "lux_engine not available"}
    result = distribute_lux(task_id, executor_id, creator_id, validator_id, None, complexity, quality)
    return {"version": VERSION, "distribution": result}

@app.get("/caas/lux/balance/{node_id}")
async def get_lux_balance(node_id: str):
    """Get Lux balance for a node"""
    if not HAS_LUX:
        return {"error": "lux_engine not available"}
    return {"version": VERSION, "balance": get_balance(node_id)}

@app.get("/caas/lux/leaderboard")
async def get_lux_leaderboard(limit: int = 20):
    """Get Lux leaderboard"""
    if not HAS_LUX:
        return {"error": "lux_engine not available"}
    return {"version": VERSION, "leaderboard": get_leaderboard(limit)}

@app.get("/caas/lux/pool")
async def get_lux_pool():
    """Get system pool status"""
    if not HAS_LUX:
        return {"error": "lux_engine not available"}
    return {"version": VERSION, "system_pool": get_system_pool_total()}

@app.get("/caas/lux/stats")
async def get_lux_stats():
    """Get overall Lux distribution statistics"""
    if not HAS_LUX:
        return {"error": "lux_engine not available"}
    return {"version": VERSION, "stats": get_distribution_stats()}



# === Xiangsheng Chain Endpoints (v2.8) ===

@app.get("/caas/chain/status")
async def get_chain_status():
    """Get xiangsheng chain status"""
    if not HAS_XIANGSHENG:
        return {"error": "xiangsheng_trigger not available"}
    return {"version": VERSION, "chain": xiangsheng.get_chain_status()}

@app.post("/caas/chain/check")
async def check_chain_transition(from_phase: str, payload: dict = {}):
    """Check if conditions are met for next phase transition"""
    if not HAS_XIANGSHENG:
        return {"error": "xiangsheng_trigger not available"}
    result = xiangsheng.check_transition(from_phase, payload)
    return {"version": VERSION, "check": result}

@app.post("/caas/chain/trigger")
async def trigger_chain_transition(from_phase: str, payload: dict = {}, force: bool = False):
    """Trigger next phase in xiangsheng chain"""
    if not HAS_XIANGSHENG:
        return {"error": "xiangsheng_trigger not available"}
    result = xiangsheng.trigger(from_phase, payload, force)
    return {"version": VERSION, "trigger": result}

@app.post("/caas/chain/cascade")
async def cascade_chain(start_phase: str = "wood", payload: dict = {}, max_steps: int = 5):
    """Auto-cascade through xiangsheng chain"""
    if not HAS_XIANGSHENG:
        return {"error": "xiangsheng_trigger not available"}
    result = xiangsheng.auto_cascade(start_phase, payload, max_steps)
    return {"version": VERSION, "cascade": result}

@app.get("/caas/chain/transitions")
async def get_chain_transitions():
    """Get all transition definitions"""
    return {"version": VERSION, "transitions": TRANSITIONS, "phases": CHAIN_NAMES}




# ============================================================
# Metal Flywheel (Jin/Baihu/West) - Validation Endpoints
# ============================================================

@app.post("/api/caas/metal/validate")
async def metal_validate_endpoint(request: Request):
    """Run Metal wheel validation on content"""
    import traceback as _tb
    if not METAL_AVAILABLE:
        return JSONResponse(content={"error": "Metal validator not available"}, status_code=503)
    try:
        body = await request.json()
        input_content = body.get("content", body.get("text", ""))
        task_id = body.get("task_id")
        schema = body.get("schema")
        kb = body.get("knowledge_base")
        
        result = metal_validate(input_content, task_id=task_id, schema=schema, knowledge_base=kb)
        return result
    except Exception as e:
        err = _tb.format_exc()
        print(f"[METAL VALIDATE ERROR] {err}")
        return {"error": str(e), "traceback": err}

@app.post("/api/caas/metal/prune-seeds")
async def metal_prune_endpoint(request: Request):
    """Metal xiangke: prune low-quality seeds"""
    if not METAL_AVAILABLE:
        return {"error": "Metal validator not available"}
    try:
        body = await request.json()
        seeds = body.get("seeds", [])
        min_score = body.get("min_score", 0.5)
        result = prune_seeds(seeds, min_score=min_score)
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/caas/metal/audit-history")
async def metal_audit_history(task_id: str = None, verdict: str = None, limit: int = 20):
    """Query Metal audit trail"""
    if not METAL_AVAILABLE:
        return {"error": "Metal validator not available"}
    try:
        history = get_audit_history(task_id=task_id, verdict=verdict, limit=limit)
        return {"history": history, "count": len(history)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/caas/metal/stats")
async def metal_stats_endpoint():
    """Get Metal audit statistics"""
    import traceback as _tb
    if not METAL_AVAILABLE:
        return JSONResponse({"error": "Metal validator not available", "reason": "import failed"}, status_code=503)
    try:
        stats = get_audit_stats()
        stats["phase"] = "metal"
        stats["beast"] = "baihu"
        stats["direction"] = "west"
        return stats
    except Exception as e:
        err = _tb.format_exc()
        print(f"[METAL ERROR] {err}")
        return {"error": str(e), "traceback": err}







# ============ FIRE ENGINE (Zhuque/South) ============

@app.post("/api/caas/fire/execute")
async def fire_execute_endpoint(request: Request):
    """Execute a task through fire pipeline"""
    if not FIRE_AVAILABLE:
        return {"error": "Fire engine not available"}
    try:
        body = await request.json()
        result = fire_execute(
            task_text=body.get("text", body.get("task_text", "")),
            task_id=body.get("task_id"),
            use_llm=body.get("use_llm", False),
            domain=body.get("domain", "general")
        )
        return result
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/caas/fire/decompose")
async def fire_decompose_endpoint(request: Request):
    """Decompose task into sub-tasks"""
    if not FIRE_AVAILABLE:
        return {"error": "Fire engine not available"}
    try:
        body = await request.json()
        subtasks = fire_decompose(body.get("text", ""), body.get("max_subtasks", 5))
        return {"subtasks": subtasks, "count": len(subtasks)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/caas/fire/stats")
async def fire_stats_endpoint():
    """Get fire engine statistics"""
    if not FIRE_AVAILABLE:
        return {"error": "Fire engine not available"}
    try:
        stats = fire_stats()
        stats["phase"] = "fire"
        stats["beast"] = "zhuque"
        stats["direction"] = "south"
        return stats
    except Exception as e:
        return {"error": str(e)}

# ============ FULL WUXING PIPELINE ============

@app.post("/api/caas/wuxing/full-cycle")
async def wuxing_full_cycle(request: Request):
    """Run complete wuxing cycle: wood->fire->earth->metal->water->wood"""
    try:
        body = await request.json()
        seed_text = body.get("text", body.get("seed", ""))
        domain = body.get("domain", "general")
        use_llm = body.get("use_llm", False)
        
        cycle = {"phases": {}, "status": "running", "started_at": datetime.now().isoformat()}
        
        # Phase 1: WOOD (Seed Creation)
        if WOOD_AVAILABLE:
            wood_result = wood_create(text=seed_text, domain=domain, source="wuxing-cycle")
            cycle["phases"]["wood"] = {"status": "completed", "seed_id": wood_result["seed_id"], "score": wood_result["scores"]["overall"]}
        else:
            cycle["phases"]["wood"] = {"status": "skipped", "reason": "engine unavailable"}
        
        # Phase 2: FIRE (Execution)
        if FIRE_AVAILABLE:
            fire_result = fire_execute(task_text=seed_text, task_id=wood_result.get("seed_id") if WOOD_AVAILABLE else None, use_llm=use_llm, domain=domain)
            cycle["phases"]["fire"] = {"status": "completed", "execution_id": fire_result["execution_id"], "quality": fire_result["quality_score"], "duration": fire_result["duration_s"]}
            execution_content = json.dumps(fire_result["results"], ensure_ascii=False)
        else:
            cycle["phases"]["fire"] = {"status": "skipped", "reason": "engine unavailable"}
            execution_content = seed_text
        
        # Phase 3: EARTH (Delivery/Hub)
        cycle["phases"]["earth"] = {"status": "completed", "action": "result_delivered", "content_length": len(execution_content)}
        
        # Phase 4: METAL (Validation)
        if METAL_AVAILABLE:
            metal_result = metal_validate(execution_content)
            cycle["phases"]["metal"] = {"status": "completed", "verdict": metal_result["verdict"], "score": metal_result["overall_score"]}
        else:
            cycle["phases"]["metal"] = {"status": "skipped", "reason": "engine unavailable"}
        
        # Phase 5: WATER (Distillation)
        if WATER_AVAILABLE:
            water_result = water_extract(execution_content, task_id=fire_result.get("execution_id") if FIRE_AVAILABLE else None, source_phase="earth", domain=domain)
            cycle["phases"]["water"] = {"status": "completed", "residual_id": water_result["residual_id"], "patterns": water_result["patterns_found"], "convergence": water_result["convergence_score"]}
            
            # Water->Wood: generate new seeds
            new_seeds = water_generate_seeds(domain=domain, max_seeds=3)
            cycle["phases"]["water"]["new_seeds"] = new_seeds["seeds_generated"]
        else:
            cycle["phases"]["water"] = {"status": "skipped", "reason": "engine unavailable"}
        
        # Cycle summary
        completed_phases = sum(1 for p in cycle["phases"].values() if p["status"] == "completed")
        cycle["status"] = "completed"
        cycle["completed_at"] = datetime.now().isoformat()
        cycle["summary"] = {
            "phases_completed": completed_phases,
            "phases_total": 5,
            "completion_rate": completed_phases / 5,
            "domain": domain
        }
        
        return cycle
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.get("/api/caas/wuxing/dashboard")
async def wuxing_dashboard():
    """Get unified wuxing flywheel dashboard"""
    dashboard = {"timestamp": datetime.now().isoformat(), "phases": {}}
    
    if WOOD_AVAILABLE:
        try:
            dashboard["phases"]["wood"] = wood_stats()
            dashboard["phases"]["wood"]["direction"] = "east"
        except: dashboard["phases"]["wood"] = {"error": "stats failed"}
    
    if FIRE_AVAILABLE:
        try:
            dashboard["phases"]["fire"] = fire_stats()
            dashboard["phases"]["fire"]["direction"] = "south"
        except: dashboard["phases"]["fire"] = {"error": "stats failed"}
    
    # Earth = Hub stats
    dashboard["phases"]["earth"] = {"direction": "center", "role": "hub", "status": "active"}
    
    if METAL_AVAILABLE:
        try:
            dashboard["phases"]["metal"] = get_audit_stats()
            dashboard["phases"]["metal"]["direction"] = "west"
        except: dashboard["phases"]["metal"] = {"error": "stats failed"}
    
    if WATER_AVAILABLE:
        try:
            dashboard["phases"]["water"] = water_stats()
            dashboard["phases"]["water"]["direction"] = "north"
        except: dashboard["phases"]["water"] = {"error": "stats failed"}
    
    engines_available = sum(1 for v in [WOOD_AVAILABLE, FIRE_AVAILABLE, True, METAL_AVAILABLE, WATER_AVAILABLE] if v)
    dashboard["system"] = {
        "engines_online": engines_available,
        "engines_total": 5,
        "readiness": f"{engines_available}/5",
        "version": VERSION
    }
    
    return dashboard

# ============ WOOD ENGINE (Qinglong/East) ============

@app.post("/api/caas/wood/create-seed")
async def wood_create_endpoint(request: Request):
    """Create a new seed"""
    if not WOOD_AVAILABLE:
        return {"error": "Wood engine not available"}
    try:
        body = await request.json()
        result = wood_create(
            text=body.get("text", ""),
            domain=body.get("domain", "general"),
            source=body.get("source", "api"),
            tags=body.get("tags"),
            parent_seed=body.get("parent_seed")
        )
        return result
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/caas/wood/mutate")
async def wood_mutate_endpoint(request: Request):
    """Mutate an existing seed"""
    if not WOOD_AVAILABLE:
        return {"error": "Wood engine not available"}
    try:
        body = await request.json()
        result = wood_mutate(
            seed_id=body.get("seed_id"),
            mutation_type=body.get("type", "evolve")
        )
        return result
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/caas/wood/convert")
async def wood_convert_endpoint(request: Request):
    """Convert seed to task"""
    if not WOOD_AVAILABLE:
        return {"error": "Wood engine not available"}
    try:
        body = await request.json()
        result = wood_convert(seed_id=body.get("seed_id"))
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/caas/wood/seeds")
async def wood_list_endpoint(domain: str = None, status: str = "active", limit: int = 20):
    """List seeds"""
    if not WOOD_AVAILABLE:
        return {"error": "Wood engine not available"}
    try:
        return wood_list(domain=domain, status=status, limit=limit)
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/caas/wood/challenge-earth")
async def wood_challenge_endpoint(request: Request):
    """Wood challenges Earth (xiangke)"""
    if not WOOD_AVAILABLE:
        return {"error": "Wood engine not available"}
    try:
        body = await request.json()
        result = wood_challenge_earth(
            body.get("content", ""),
            domain=body.get("domain")
        )
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/caas/wood/stats")
async def wood_stats_endpoint():
    """Get wood engine statistics"""
    if not WOOD_AVAILABLE:
        return {"error": "Wood engine not available"}
    try:
        stats = wood_stats()
        stats["phase"] = "wood"
        stats["beast"] = "qinglong"
        stats["direction"] = "east"
        return stats
    except Exception as e:
        return {"error": str(e)}

# ============ WATER ENGINE (Xuanwu/North) ============

@app.post("/api/caas/water/extract")
async def water_extract_endpoint(request: Request):
    """Extract residual knowledge from task result"""
    if not WATER_AVAILABLE:
        return {"error": "Water engine not available"}
    try:
        body = await request.json()
        result = water_extract(
            body.get("content", ""),
            task_id=body.get("task_id"),
            source_phase=body.get("source_phase", "earth"),
            domain=body.get("domain", "general")
        )
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/caas/water/convergence")
async def water_convergence_endpoint(domain: str = None):
    """Get knowledge convergence report"""
    if not WATER_AVAILABLE:
        return {"error": "Water engine not available"}
    try:
        report = water_convergence(domain)
        report["phase"] = "water"
        report["beast"] = "xuanwu"
        report["direction"] = "north"
        return report
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/caas/water/generate-seeds")
async def water_seeds_endpoint(request: Request):
    """Generate seeds from accumulated knowledge (water->wood xiangsheng)"""
    if not WATER_AVAILABLE:
        return {"error": "Water engine not available"}
    try:
        body = await request.json()
        seeds = water_generate_seeds(
            domain=body.get("domain"),
            max_seeds=body.get("max_seeds", 5)
        )
        return seeds
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/caas/water/constrain-fire")
async def water_constrain_endpoint(request: Request):
    """Water constrains Fire (xiangke check)"""
    if not WATER_AVAILABLE:
        return {"error": "Water engine not available"}
    try:
        body = await request.json()
        result = water_constrain_fire(
            body.get("plan", body.get("content", "")),
            domain=body.get("domain")
        )
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/caas/water/stats")
async def water_stats_endpoint():
    """Get water engine statistics"""
    if not WATER_AVAILABLE:
        return {"error": "Water engine not available"}
    try:
        stats = water_stats()
        stats["phase"] = "water"
        stats["beast"] = "xuanwu"
        stats["direction"] = "north"
        return stats
    except Exception as e:
        return {"error": str(e)}


# PostgreSQL health endpoint
@app.get("/api/caas/pg/health")
async def pg_health():
    if not PG_AVAILABLE:
        return {"status": "unavailable", "message": "pg_storage not imported"}
    return pg_storage.health_check()

@app.get("/api/caas/pg/stats")
async def pg_stats():
    if not PG_AVAILABLE:
        return {"status": "unavailable"}
    result = {}
    try:
        result["metal"] = pg_storage.metal_get_stats()
    except: pass
    try:
        result["water"] = pg_storage.water_get_convergence()
    except: pass
    return result


# Hub Bridge endpoints
@app.get("/api/caas/hub/status")
async def hub_status():
    if not HUB_AVAILABLE:
        return {"error": "hub_connector not available"}
    return hub_connector.check_hub()

@app.get("/api/caas/hub/stats")
async def hub_stats():
    if not HUB_AVAILABLE:
        return {"error": "hub_connector not available"}
    return hub_connector.get_hub_stats()

@app.get("/api/caas/hub/pending")
async def hub_pending(limit: int = 10):
    if not HUB_AVAILABLE:
        return {"error": "hub_connector not available"}
    tasks = hub_connector.get_pending_tasks(limit)
    return {"count": len(tasks), "tasks": tasks}

@app.post("/api/caas/hub/publish")
async def hub_publish(request: Request):
    if not HUB_AVAILABLE:
        return {"error": "hub_connector not available"}
    body = await request.json()
    return hub_connector.publish_task(
        title=body.get("title", ""),
        description=body.get("description", ""),
        priority=body.get("priority", "P1"),
        phase=body.get("phase", "fire")
    )



# Pipeline v2 endpoint (optimized)
@app.post("/api/caas/pipeline/analyze")
async def pipeline_analyze(request: Request):
    if not PIPELINE_V2:
        return {"error": "wuxing_pipeline_v2 not available"}
    body = await request.json()
    topic = body.get("topic", "")
    domain = body.get("domain", "general")
    depth = body.get("depth", "compressed")
    if not topic:
        raise HTTPException(status_code=400, detail="topic required")
    
    import threading
    result_holder = [None]
    def run():
        result_holder[0] = wuxing_pipeline_v2.run_pipeline(topic, domain, depth)
    
    t = threading.Thread(target=run)
    t.start()
    t.join(timeout=300)
    
    if result_holder[0]:
        return result_holder[0]
    return {"error": "Pipeline timeout"}

@app.get("/api/caas/pipeline/version")
async def pipeline_version():
    return {"version": wuxing_pipeline_v2.VERSION if PIPELINE_V2 else "unavailable", "v2": PIPELINE_V2}


if __name__ == "__main__":

    print(f"[CaaS] Starting SkyCetus CaaS Gateway v2.0 on port {PORT}")

    print(f"[CaaS] Free tier: {FREE_LIMIT}/day | Paid: {PAID_LIMIT}/day")

    print(f"[CaaS] L0 data: {L0_DATA}")

    print(f"[CaaS] Hub: {HUB_URL}")

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

