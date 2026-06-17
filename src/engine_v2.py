# -*- coding: utf-8 -*-
"""
Wuxing Flywheel Engine v7.0 — 认知循环 × 东西方均衡 × 相生相克

Key upgrades from v1.0:
  1. Multi-round iteration (residuals feed back as next-round seeds)
  2. Verification function (internal consistency + novelty scoring)
  3. 相生相克 info flow between elements (not parallel queries)
  4. 游离态 interface (human can inject at any round)
  5. Feedback Ledger (all rounds scored + tracked)

Architecture:
  Round N: 青龙(创生) → 朱雀(教化) → 谛听(验证) → 白虎(洞察) → 玄武(解构收敛)
           → residuals + score → Round N+1

Usage:
  python engine_v2.py "Your topic here"
  python engine_v2.py "Your topic" --rounds 3
  python engine_v2.py "Your topic" --rounds 3 --interactive
"""

import json, sys, os, time, uuid, argparse
try:
    import psycopg2, psycopg2.extras
except ImportError:
    psycopg2 = None
import sqlite3  # fallback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from edge_agents import EdgeAgentRegistry, create_edge_registry
from concurrent.futures import as_completed
import re
from conflict_detector import detect_conflicts
try:
    from integrity_mesh import IntegrityMesh
    _integrity_mesh = IntegrityMesh()
    HAS_INTEGRITY = True
    print("[engine_v2] IntegrityMesh loaded")
except ImportError:
    _integrity_mesh = None
    HAS_INTEGRITY = False
    print("[engine_v2] IntegrityMesh not available")

# V13.0: NPT Validator — 认知不扩散协议校验
try:
    from npt_validator import NPTValidator
    _npt_validator = NPTValidator(strict=False)
    print("[engine_v2] NPT Validator loaded")
except ImportError:
    _npt_validator = None
    print("[engine_v2] NPT Validator not available")

# V13.0: Adversarial Enforcer — 白虎审计强制化
try:
    from adversarial_enforcer import AdversarialEnforcer
    _adversarial_enforcer = AdversarialEnforcer(strict=False)
    print("[engine_v2] Adversarial Enforcer loaded")
except ImportError:
    _adversarial_enforcer = None
    print("[engine_v2] Adversarial Enforcer not available")


# V14.0: ds4-inspired Layered Memory Architecture (2026-05-24)
# Inspired by antirez/ds4 (DwarfStar 4) disk KV Cache breakthrough.
# Core insight: memory should be tiered by access frequency, not uniformly stored.
# Hot memory (DRAM) = current round active context
# Warm memory (SSD KV) = recent rounds, searchable via HNSW+PQ
# Cold memory (compressed archive) = all historical rounds, gzip compressed
# This maps directly to Aethony's 3-tier memory: public/personal/private
_LAYERED_MEMORY = True
_HOT_MEMORY_LIMIT_TOKENS = int(os.environ.get("FW_HOT_MEM", 32000))      # ~32K tokens in RAM
_WARM_MEMORY_INDEX = os.environ.get("FW_WARM_INDEX", "hnsw")             # HNSW vector index
_COLD_COMPRESSION = os.environ.get("FW_COLD_COMPRESS", "gzip")           # gzip archive

try:
    import gzip
    from memory_types import MemoryTier, LayeredMemoryManager
    _layered_memory = LayeredMemoryManager(
        hot_limit=_HOT_MEMORY_LIMIT_TOKENS,
        warm_index=_WARM_MEMORY_INDEX,
        cold_compression=_COLD_COMPRESSION,
        base_dir=BASE_DIR / "memory_tiers"
    )

# V7.0: Civilizational Cognitive Topology (2026-05-24)
# Philosophical mappings updated based on group chat discussion with Robin:
# - 青龙 = 道家 (创生/涌现) — 无中生有，方向自现
# - 朱雀 = 儒家 (教化/传播) — 格物致知，四层证据
# - 白虎 = 弗洛伊德 (深层洞察) — 三我结构，诊断动机
# - 谛听 = 波普尔 (验证) — 可证伪性，证据等级
# - 玄武 = 尼采 + 佛家中观 (解构收敛) — 价值重估 + 不落两边
# Cognitive cycle: 创造 → 传播 → 解构 → 验证 → 再创造
# East:West balance: 3:2 (道儒佛 vs 弗洛伊德波普尔) + 尼采跨东西
# Three-layer analogy: 八仙(传播层) / 八卦(结构层) / 神经系统(本质层)

    print(f"[engine_v2] ds4 Layered Memory loaded: hot={_HOT_MEMORY_LIMIT_TOKENS} tokens, warm={_WARM_MEMORY_INDEX}, cold={_COLD_COMPRESSION}")
except ImportError:
    _layered_memory = None
    print("[engine_v2] LayeredMemoryManager not available, using flat memory")

from conflict_detector import generate_conflict_seeds, init_conflict_pool, get_conflict_stats

# V9.0: Trading mode support
_TRADING_DOMAIN = False
try:
    from trading_prefeed import build_trading_seed
    from trading_prompts import TRADING_PROMPTS
    HAS_TRADING = True
except ImportError:
    HAS_TRADING = False

sys.stdout.reconfigure(encoding='utf-8')

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "flywheel_v2.db"  # SQLite fallback
PG_DSN = os.environ.get("FLYWHEEL_PG_DSN", "dbname=skycetus user=postgres host=localhost")
PG_SCHEMA = "flywheel"
USE_PG = os.environ.get("FLYWHEEL_DB", "pg").lower() == "pg"
PROMPTS_DIR = BASE_DIR / "prompts_v2"

# Multi-model routing config
MODEL_REGISTRY = {
    # === 清心API (PsyLabs) — OpenAI-compatible proxy, 400+ models ===
    # Base URL: https://api.psylabs.top/v1/chat/completions
    # All models below route through this single API key
    "gpt5": {
        "api_key": "K4HR1CBWv0UdFBe3ZnZ6O7400BskyvJDZRufx4BcxkRCSb4v",
        "api_base": "https://api.psylabs.top/v1/chat/completions",
        "model": "gpt-5.5",  # upgraded from gpt-5
        "thinking": False,
        "strength": "strongest_reasoning",  # OpenAI GPT-5.5 — absolute best
    },
    "claude_opus": {
        "api_key": "K4HR1CBWv0UdFBe3ZnZ6O7400BskyvJDZRufx4BcxkRCSb4v",
        "api_base": "https://api.psylabs.top/v1/chat/completions",
        "model": "claude-opus-4-7",  # upgraded from 4.6 to 4.7 (latest)
        "thinking": False,
        "strength": "deep_analysis",  # Anthropic Claude-Opus-4.7 — absolute best
    },
    "grok4": {
        "api_key": "K4HR1CBWv0UdFBe3ZnZ6O7400BskyvJDZRufx4BcxkRCSb4v",
        "api_base": "https://api.psylabs.top/v1/chat/completions",
        "model": "grok-4",
        "thinking": False,
        "strength": "adversarial",  # xAI's strongest, excellent for attacks
    },
    "deepseek_v4": {
        "api_key": "K4HR1CBWv0UdFBe3ZnZ6O7400BskyvJDZRufx4BcxkRCSb4v",
        "api_base": "https://api.psylabs.top/v1/chat/completions",
        "model": "deepseek-v4-pro",
        "thinking": False,
        "strength": "logical_reasoning",  # DeepSeek's latest, strongest reasoning
    },
    # === Original providers (kept as fallback) ===
    "minimax": {
        "api_key": os.environ.get("MINIMAX_API_KEY",
            "sk-cp-wBP8BgBJbLsGCUshk0x5oYKbiydygx-RMk0iJDhANE6epg6gMnRBRg5hPN1eioB3PURgoeEiv7o2kLE7vOqibkLG1_3daWsmo-7kkkVxS4t7guHj7exDGwo"),
        "api_base": "https://api.minimaxi.com/anthropic/v1/messages",
        "model": "MiniMax-M2.7",
        "thinking": True,
        "strength": "deep_analysis",
    },
    "kimi": {
        "api_key": os.environ.get("DASHSCOPE_API_KEY",
            "sk-sp-da9d1b325a8b490e8344b29a2fd49ea5"),
        "api_base": "https://coding.dashscope.aliyuncs.com/v1/chat/completions",
        "model": "kimi-k2.5",
        "thinking": False,
        "strength": "independent_judge",
    },
    "deepseek": {
        "api_key": os.environ.get("DEEPSEEK_API_KEY",
            "sk-64ba741ee60d400b98be80ff82189a4b"),
        "api_base": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "thinking": False,
        "strength": "logical_reasoning",
    },
    "qwen": {
        "api_key": os.environ.get("DASHSCOPE_API_KEY",
            "sk-sp-da9d1b325a8b490e8344b29a2fd49ea5"),
        "api_base": "https://coding.dashscope.aliyuncs.com/v1/chat/completions",
        "model": "qwen3.6-plus",
        "thinking": False,
        "strength": "chinese_creative",
    },
    "glm": {
        "api_key": os.environ.get("DASHSCOPE_API_KEY",
            "sk-sp-da9d1b325a8b490e8344b29a2fd49ea5"),
        "api_base": "https://coding.dashscope.aliyuncs.com/v1/chat/completions",
        "model": "glm-5",
        "thinking": False,
        "strength": "verification",
    },

}

# Default routing: which model handles which element
# ============================================================
# MODE SELECTION (set FLYWHEEL_MODE env var):
#   "standard" (default): Domestic models only — Qwen + Kimi + MiniMax (包月)
#                         Cost: ~¥0.5-2/analysis (package subscription)
#   "flagship": International models — GPT-5.5 + Claude Opus + Grok-4
#               Cost: ~$5-10/analysis (pay-per-use)
#   "local": Single model reasoning — any one model from registry
#            Cost: ~¥0 (package subscription)
# ============================================================
FLYWHEEL_MODE = os.environ.get("FLYWHEEL_MODE", "standard")

# Phase 1: Standard mode (domestic models, cost-effective)
# 3-model diversity: Kimi(reasoning+judge) + Qwen(creative) + MiniMax(fallback)
ELEMENT_MODEL_ROUTE_STANDARD = {
    "qinglong": "qwen",        # seeds: Qwen strong creative divergence
    "zhuque":   "kimi-k2.6",    # execution: DeepSeek strong structured analysis
    "diting":   "kimi",        # verification: Kimi independent cross-check
    "baihu":    "minimax",     # attack: MiniMax strong adversarial (different model family)
    "xuanwu":   "kimi-k2.6",    # convergence: DeepSeek synthesis + meta-cognition
    "verifier": "kimi",        # judge: Kimi independent scoring
}

# Phase 2: Flagship mode (international models, highest quality)
# 4-model diversity: GPT-5.5 + Claude Opus + Grok-4 + Kimi(judge)
# Use sparingly: only for high-value analysis (fundraising, major decisions)
ELEMENT_MODEL_ROUTE_FLAGSHIP = {
    "qinglong": "gpt5",        # seeds: GPT-5.5 best divergent thinking
    "zhuque":   "claude_opus", # execution: Claude Opus best deep analysis
    "diting":   "gpt5",        # verification: GPT-5.5 independent cross-check
    "baihu":    "grok4",       # attack: Grok-4 best adversarial
    "xuanwu":   "claude_opus", # convergence: Claude Opus best synthesis
    "verifier": "kimi",        # judge: Kimi independent (different family from generators)
}

# Select active routing based on mode
if FLYWHEEL_MODE == "flagship":
    ELEMENT_MODEL_ROUTE = ELEMENT_MODEL_ROUTE_FLAGSHIP
    print(f"[flywheel] MODE: flagship (GPT-5.5 + Claude Opus + Grok-4)")
elif FLYWHEEL_MODE == "local":
    # Single model for quick analysis
    _local_model = os.environ.get("FLYWHEEL_LOCAL_MODEL", "qwen")
    ELEMENT_MODEL_ROUTE = {
        "qinglong": _local_model, "zhuque": _local_model,
        "diting": _local_model, "baihu": _local_model,
        "xuanwu": _local_model, "verifier": _local_model,
    }
    print(f"[flywheel] MODE: local (single model: {_local_model})")
else:
    ELEMENT_MODEL_ROUTE = ELEMENT_MODEL_ROUTE_STANDARD
    print(f"[flywheel] MODE: standard (domestic: Qwen + Kimi + MiniMax 包月)")

# Legacy single-model fallback
API_KEY = MODEL_REGISTRY["minimax"]["api_key"]
API_BASE = MODEL_REGISTRY["minimax"]["api_base"]
MODEL = MODEL_REGISTRY["minimax"]["model"]

# 五行 element names
# --- Amplifier v1.0 (AMP-001~004) ---
try:
    from amplifier import pre_amplify, format_amplified_prompt
    HAS_AMPLIFIER = True
except ImportError:
    HAS_AMPLIFIER = False
    print("[AMPLIFIER] amplifier.py not found, disabled")

# Feature flag (AMP-004)
import os as _amp_os
AMPLIFIER_ENABLED = _amp_os.environ.get("AMPLIFIER_ENABLED", "true").lower() == "true"

ELEMENTS = ["qinglong", "zhuque", "diting", "baihu", "xuanwu"]
ELEMENT_NAMES = {
    "qinglong": "青龙·木·创生(道家)",
    "zhuque":   "朱雀·火·教化(儒家)",
    "diting":   "谛听·土·验证(波普尔)",
    "baihu":    "白虎·金·洞察(弗洛伊德)",
    "xuanwu":   "玄武·水·解构(尼采/佛家)",
}

# 相生 (generative) flow: each element feeds the next
SHENGKE = {
    "sheng": {  # generates/feeds
        "qinglong": "zhuque",   # 木生火: seeds drive execution
        "zhuque":   "diting",   # 火生土: execution results go to verification
        "diting":   "baihu",    # 土生金: verified results go to attack
        "baihu":    "xuanwu",   # 金生水: attacked residuals go to convergence
        "xuanwu":   "qinglong", # 水生木: convergence generates new seeds (LOOP!)
    },
    "ke": {  # constrains/challenges (correct 五行相克: 金克木,木克土,土克水,水克火,火克金)
        "qinglong": "diting",   # 木克土: new seeds challenge existing verification standards
        "zhuque":   "baihu",    # 火克金: execution insights constrain adversarial over-attack
        "diting":   "xuanwu",   # 土克水: reality check constrains premature convergence
        "baihu":    "qinglong", # 金克木: adversarial check filters unreliable seeds
        "xuanwu":   "zhuque",   # 水克火: convergence restrains execution divergence
    }
}


# Edge Agent Registry (16-agent system: 5 nodes + 10 edges + 天鲸)
EDGE_REGISTRY = None  # Initialized lazily in run_round when call_llm is available

def _get_edge_registry():
    global EDGE_REGISTRY
    if EDGE_REGISTRY is None:
        EDGE_REGISTRY = create_edge_registry(call_llm, model_key="deepseek")
    return EDGE_REGISTRY


def _clean_llm_output(text):
    """Strip LLM artifacts (<think> tags, ```json blocks) from raw output, preserving content."""
    if not isinstance(text, str) or not text.strip():
        return text
    s = text.strip()
    # Strip <think>...</think> blocks entirely (reasoning, not output)
    s = re.sub(r'<think>.*?</think>', '', s, flags=re.DOTALL)
    # Handle unclosed <think> at end
    s = re.sub(r'<think>.*$', '', s, flags=re.DOTALL)
    # Strip leftover markers
    s = re.sub(r'</?think>', '', s)
    # Strip markdown code block markers (keep content)
    s = re.sub(r'^\s*```(?:json)?\s*\n?', '', s)
    s = re.sub(r'\n?\s*```\s*$', '', s)
    return s.strip()


# === P7-009: Quality Grading System ===
def _assess_report_quality(result_data):
    """Assess report quality on 4 dimensions. Returns quality metadata dict."""
    quality = {"dimensions": {}, "overall_grade": "?", "overall_score": 0, "flags": []}
    
    rounds = result_data.get("rounds", [])
    kunpeng = result_data.get("kunpeng", {})
    
    # 1. Structure completeness (0-1): all 5 elements present per round
    elements_expected = {"qinglong", "zhuque", "baihu", "diting", "xuanwu"}
    struct_scores = []
    for rd in rounds:
        present = set()
        for elem_out in rd.get("element_outputs", {}).values() if isinstance(rd.get("element_outputs"), dict) else []:
            if elem_out and len(str(elem_out)) > 50:
                present.add(elem_out) if False else None
        # Count non-empty element outputs
        eo = rd.get("element_outputs", {})
        if isinstance(eo, dict):
            filled = sum(1 for k in elements_expected if eo.get(k) and len(str(eo[k])) > 50)
            struct_scores.append(filled / 5.0)
        else:
            struct_scores.append(0)
    structure = sum(struct_scores) / max(len(struct_scores), 1)
    quality["dimensions"]["structure_completeness"] = round(structure, 3)
    
    # 2. Argument density (0-1): avg length of element outputs (proxy for depth)
    total_chars = 0
    total_outputs = 0
    for rd in rounds:
        eo = rd.get("element_outputs", {})
        if isinstance(eo, dict):
            for v in eo.values():
                if v:
                    total_chars += len(str(v))
                    total_outputs += 1
    avg_chars = total_chars / max(total_outputs, 1)
    # 500+ chars = good, 200- = poor
    arg_density = min(1.0, max(0, (avg_chars - 200) / 800))
    quality["dimensions"]["argument_density"] = round(arg_density, 3)
    
    # 3. Cross-validation coverage (0-1): baihu (adversarial) and diting (verification) present
    cv_scores = []
    for rd in rounds:
        eo = rd.get("element_outputs", {})
        if isinstance(eo, dict):
            has_baihu = bool(eo.get("baihu") and len(str(eo["baihu"])) > 50)
            has_diting = bool(eo.get("diting") and len(str(eo["diting"])) > 50)
            cv_scores.append((int(has_baihu) + int(has_diting)) / 2.0)
    cross_val = sum(cv_scores) / max(len(cv_scores), 1)
    quality["dimensions"]["cross_validation"] = round(cross_val, 3)
    
    # 4. Kunpeng enrichment completeness (0-1)
    kunpeng_fields = ["kun_dive", "peng_soar", "dao_merge", "buddhist_three", 
                      "freudian_layers", "data_gaps", "strategic_recommendations", "core_contradiction"]
    if kunpeng:
        filled = sum(1 for f in kunpeng_fields if kunpeng.get(f) and len(str(kunpeng[f])) > 20)
        kp_score = filled / len(kunpeng_fields)
    else:
        kp_score = 0
    quality["dimensions"]["kunpeng_completeness"] = round(kp_score, 3)
    
    # Overall score (weighted)
    overall = (structure * 0.3 + arg_density * 0.3 + cross_val * 0.2 + kp_score * 0.2)
    quality["overall_score"] = round(overall, 3)
    
    # Grade
    if overall >= 0.85:
        quality["overall_grade"] = "A"
    elif overall >= 0.70:
        quality["overall_grade"] = "B"
    elif overall >= 0.50:
        quality["overall_grade"] = "C"
    else:
        quality["overall_grade"] = "D"
    
    # Flags
    if structure < 0.6:
        quality["flags"].append("incomplete_structure")
    if arg_density < 0.3:
        quality["flags"].append("shallow_arguments")
    if cross_val < 0.5:
        quality["flags"].append("weak_cross_validation")
    if kp_score < 0.5:
        quality["flags"].append("incomplete_kunpeng")
    if len(rounds) < 2:
        quality["flags"].append("single_round_only")
    
    return quality

def gen_id(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
class DBConn:
    """Unified DB wrapper — makes PG work like SQLite conn.execute() pattern."""
    def __init__(self, pg=True):
        self.is_pg = pg and psycopg2 is not None
        if self.is_pg:
            self.conn = psycopg2.connect(PG_DSN, cursor_factory=psycopg2.extras.RealDictCursor)
            self.conn.autocommit = False
            # Set search_path so we don't need flywheel. prefix everywhere
            cur = self.conn.cursor()
            cur.execute(f"SET search_path TO {PG_SCHEMA}, public;")
            self.conn.commit()
        else:
            self.conn = sqlite3.connect(str(DB_PATH))
            self.conn.row_factory = sqlite3.Row
            SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, topic TEXT NOT NULL, max_rounds INTEGER DEFAULT 3, status TEXT DEFAULT 'running', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, completed_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS rounds (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, round_num INTEGER NOT NULL, input_seeds TEXT, input_residuals TEXT, observer_injection TEXT, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, completed_at TIMESTAMP, FOREIGN KEY (run_id) REFERENCES runs(id));
CREATE TABLE IF NOT EXISTS elements (id TEXT PRIMARY KEY, round_id TEXT NOT NULL, run_id TEXT NOT NULL, element TEXT NOT NULL, input_text TEXT, output_text TEXT, sheng_from TEXT, ke_signal TEXT, tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0, latency_ms INTEGER DEFAULT 0, model_key TEXT DEFAULT 'minimax', status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (round_id) REFERENCES rounds(id));
CREATE TABLE IF NOT EXISTS ledger (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, round_id TEXT NOT NULL, round_num INTEGER NOT NULL, consistency_score REAL, novelty_score REAL, depth_score REAL, actionability_score REAL, overall_score REAL, residuals TEXT, residual_count INTEGER DEFAULT 0, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (run_id) REFERENCES runs(id));
"""
            self.conn.executescript(SCHEMA_V2)
            self.conn.commit()
        self._init_extensions()

    def _init_extensions(self):
        """Initialize extension tables (conflict pool, etc.)"""
        try:
            init_conflict_pool(self)
        except Exception as e:
            print(f'    [conflict_pool] Extension init warning: {e}')

    def execute(self, sql, params=None):
        if self.is_pg:
            # Convert ? placeholders to %s for psycopg2
            sql = sql.replace('?', '%s')
            cur = self.conn.cursor()
            cur.execute(sql, params)
            return cur
        else:
            if params:
                return self.conn.execute(sql, params)
            return self.conn.execute(sql)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def init_db():
    db = DBConn(pg=USE_PG)
    mode = "PostgreSQL" if db.is_pg else "SQLite"
    print(f"  💾 Database: {mode}")
    return db


# ---------------------------------------------------------------------------
# LLM Client (same as v1, proven stable)
# ---------------------------------------------------------------------------
def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.3,
             max_tokens: int = 8192, model_key: str = None) -> dict:
    """Call LLM with multi-model routing support.
    model_key: 'minimax', 'kimi', or None (uses default minimax).
    """
    import urllib.request, urllib.error
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"

    # Resolve model config
    cfg = MODEL_REGISTRY.get(model_key, MODEL_REGISTRY["minimax"]) if model_key else MODEL_REGISTRY["minimax"]
    api_base = cfg["api_base"]
    api_key = cfg["api_key"]
    model = cfg["model"]
    use_thinking = cfg.get("thinking", True)

    # Build messages - Anthropic uses combined user, OpenAI uses system+user
    is_anthropic = "anthropic" in api_base
    if is_anthropic:
        messages = [
            {"role": "user", "content": f"{system_prompt}\n\n---\n\n{user_prompt}"}
        ]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
        "temperature": temperature
    }
    if use_thinking and is_anthropic:
        payload["thinking"] = {"type": "enabled", "budget_tokens": 1000}

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_base, data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST"
    )

    import random as _rnd
    start = time.time()
    _max_retries = 3
    body = None
    for _attempt in range(_max_retries):
        try:
            resp = urllib.request.urlopen(req, timeout=300)
            body = json.loads(resp.read())
            break
        except urllib.error.HTTPError as _he:
            if _he.code in (429, 502, 503) and _attempt < _max_retries - 1:
                _wait = (2 ** _attempt) * 5 + _rnd.uniform(0, 3)
                print(f"    [LLM] {model} HTTP {_he.code}, retry {_attempt+1}/{_max_retries} in {_wait:.0f}s")
                time.sleep(_wait)
                continue
            return {"text": "", "error": f"HTTP {_he.code}: {str(_he)[:200]}", "tokens_in": 0, "tokens_out": 0, "latency_ms": 0}
        except Exception as e:
            if _attempt < _max_retries - 1 and "timeout" in str(e).lower():
                _wait = (2 ** _attempt) * 10
                print(f"    [LLM] {model} timeout, retry {_attempt+1}/{_max_retries} in {_wait}s")
                time.sleep(_wait)
                continue
            return {"text": "", "error": str(e), "tokens_in": 0, "tokens_out": 0, "latency_ms": 0}
    if body is None:
        return {"text": "", "error": "Max retries exceeded", "tokens_in": 0, "tokens_out": 0, "latency_ms": 0}

    latency = int((time.time() - start) * 1000)
    text = ""

    # Detect response format: OpenAI (choices) vs Anthropic (content blocks)
    if "choices" in body:
        # OpenAI format (DeepSeek, etc.)
        choices = body.get("choices", [])
        if choices:
            text = choices[0].get("message", {}).get("content", "")
        usage = body.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)
    else:
        # Anthropic format (MiniMax, Kimi)
        content = body.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    break
        elif isinstance(content, str):
            text = content
        usage = body.get("usage", {})
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)

    return {
        "text": text,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": latency
    }


def parse_json_safe(text: str) -> dict:
    """Best-effort JSON extraction from LLM output."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    if "```" in text:
        for block in text.split("```")[1::2]:
            block = block.strip()
            if block.startswith("json"):
                block = block[4:].strip()
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {"raw": text}


# ---------------------------------------------------------------------------
# Engram: Prior Run Retrieval ("能查的别算")
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# V14.0: 谛听 Auto-Fetch — Knowledge Gap Auto-Fill
# When data_gaps with severity > 0.7 are found, auto-search and inject
# ---------------------------------------------------------------------------
def _autofetch_for_gaps(data_gaps, topic, max_queries=3):
    """Auto-fetch data for high-severity knowledge gaps.
    Returns supplementary context string to inject into next round.
    """
    if not data_gaps or not isinstance(data_gaps, list):
        return ""
    
    # Filter high-severity gaps
    high_gaps = []
    for gap in data_gaps:
        sev = 0
        if isinstance(gap, dict):
            sev = gap.get("severity", gap.get("score", 0))
            if isinstance(sev, str):
                try: sev = float(sev)
                except: sev = 0
        elif isinstance(gap, str):
            sev = 0.8  # string gaps default to high
        if sev >= 0.7:
            high_gaps.append(gap)
    
    if not high_gaps:
        return ""
    
    print(f"\n  \U0001f50d 谛听 Auto-Fetch: {len(high_gaps)} high-severity gaps detected")
    
    # Generate search queries from gaps
    queries = []
    for gap in high_gaps[:max_queries]:
        if isinstance(gap, dict):
            q = gap.get("description", gap.get("gap", gap.get("title", "")))
        else:
            q = str(gap)
        if q:
            # Trim to essential search terms
            q = q[:100].strip()
            queries.append(q)
    
    if not queries:
        return ""
    
    # Execute searches via urllib (same as flywheel API uses)
    import urllib.request, urllib.parse
    results_text = []
    
    for q in queries:
        try:
            search_q = f"{topic} {q}"[:150]
            url = "https://yuanbao.tencent.com/api/search?" + urllib.parse.urlencode({"q": search_q, "limit": "3"})
            # Use a simpler approach: call the ProSearch endpoint if available, 
            # otherwise use a direct LLM call to synthesize what we know
            print(f"    \U0001f50e Query: {search_q[:80]}...")
            
            # Try local prosearch via HTTP
            try:
                proxy_url = "http://localhost:19104/proxy/prosearch"
                req_data = json.dumps({"query": search_q, "count": 3}).encode()
                req = urllib.request.Request(proxy_url, data=req_data, 
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                    if data.get("success") and data.get("data", {}).get("docs"):
                        for doc in data["data"]["docs"][:2]:
                            snippet = doc.get("passage", doc.get("snippet", ""))[:500]
                            title = doc.get("title", "")[:100]
                            if snippet:
                                results_text.append(f"[{title}] {snippet}")
                        print(f"    \u2705 Found {len(data['data']['docs'])} results")
                        continue
            except Exception as e:
                pass  # Proxy not available, try direct
            
            # Fallback: use DuckDuckGo instant answers API (no auth needed)
            try:
                ddg_url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode({
                    "q": search_q[:100], "format": "json", "no_html": "1"
                })
                req = urllib.request.Request(ddg_url, headers={"User-Agent": "SkyCetus-Flywheel/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    abstract = data.get("AbstractText", "")
                    if abstract:
                        results_text.append(f"[DDG] {abstract[:500]}")
                        print(f"    \u2705 DDG abstract found")
                    related = data.get("RelatedTopics", [])
                    for rt in related[:2]:
                        if isinstance(rt, dict) and rt.get("Text"):
                            results_text.append(f"[Related] {rt['Text'][:300]}")
            except Exception:
                pass
            
            # If still nothing, generate a targeted LLM query to fill the gap
            if not results_text:
                print(f"    \u26A0\uFE0F No search results, will use LLM synthesis")
                try:
                    synth = call_llm(
                        "You are a research data synthesizer. Given a knowledge gap, provide the most current factual data points you know about this topic. Be specific with numbers, dates, and sources. Respond in Chinese.",
                        f"Knowledge gap to fill: {q}\nTopic context: {topic}\nProvide 3-5 key data points:",
                        temperature=0.2, max_tokens=500
                    )
                    if synth:
                        results_text.append(f"[LLM-Synth] {synth[:500]}")
                        print(f"    \u2705 LLM synthesis generated")
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"    \u274C Search failed: {e}")
    
    if not results_text:
        return ""
    
    # Format as injection context
    injection = "\n\n[谛听 Auto-Fetch 补充数据]\n"
    injection += "以下数据由系统自动检索补充，用于填补上轮分析中的高严重度知识缺口：\n\n"
    for i, rt in enumerate(results_text, 1):
        injection += f"{i}. {rt}\n\n"
    injection += "[/Auto-Fetch]\n"
    
    print(f"    \U0001f4e6 Injected {len(results_text)} data fragments ({len(injection)} chars)")
    return injection


def retrieve_prior(conn, topic: str, max_results: int = 3, gate_threshold: float = 0.30) -> dict:
    """Engram-style retrieval: find prior runs relevant to current topic.
    Uses character bigram similarity for Chinese topic matching.
    Gate threshold filters low-relevance matches (avoids noise injection).
    Returns structured prior context for prompt injection.
    """
    import re

    # Common Chinese words that appear in most analysis topics (stop words)
    STOP_BIGRAMS = {'分析', '深度', '核心', '问题', '中国', '全球', '市场', '产业', '技术', '维度'}

    def bigrams(text):
        """Extract character bigrams for Chinese, words for English.
        Filters out common analytical stop-bigrams to reduce false matches."""
        chars = re.findall(r'[\u4e00-\u9fff]', text)
        words = re.findall(r'[a-zA-Z]{3,}', text.lower())  # min 3 chars to skip 'vs'
        bg = set()
        for i in range(len(chars) - 1):
            pair = chars[i] + chars[i + 1]
            if pair not in STOP_BIGRAMS:
                bg.add(pair)
        bg.update(words)
        return bg

    topic_bg = bigrams(topic)
    if not topic_bg:
        return {"found": False, "prior_runs": [], "topic": topic}

    rows = conn.execute(
        "SELECT id, topic, status, created_at FROM runs WHERE status = 'done' ORDER BY created_at DESC LIMIT 100"
    ).fetchall()

    if not rows:
        return {"found": False, "prior_runs": [], "topic": topic}

    scored = []
    for row in rows:
        # Truncate stored topic to first 200 chars (DB stores full prompt)
        row_topic = row['topic'][:200] if row['topic'] else ""
        row_bg = bigrams(row_topic)
        if not row_bg:
            continue
        intersection = len(topic_bg & row_bg)
        # Asymmetric: what fraction of query bigrams appear in prior topic?
        # This measures "does this prior run cover my topic?" not "are they identical?"
        coverage = intersection / len(topic_bg) if topic_bg else 0
        if coverage >= gate_threshold:
            scored.append((coverage, dict(row)))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_results]

    if not top:
        return {"found": False, "prior_runs": [], "topic": topic}

    prior_runs = []
    for sim, row in top:
        run_id = row['id']

        # Get best round by score
        best = conn.execute(
            "SELECT round_num, overall_score FROM ledger WHERE run_id = ? AND overall_score IS NOT NULL ORDER BY overall_score DESC LIMIT 1",
            (run_id,)
        ).fetchone()

        if not best:
            continue

        round_num = best['round_num']

        # Get round_id for the best round
        rnd = conn.execute(
            "SELECT id FROM rounds WHERE run_id = ? AND round_num = ?",
            (run_id, round_num)
        ).fetchone()

        if not rnd:
            continue

        round_id = rnd['id']

        # Get key element outputs (qinglong seeds, baihu attacks, xuanwu conclusion)
        elems = conn.execute(
            "SELECT element, output_text FROM elements WHERE round_id = ? AND element IN ('qinglong', 'baihu', 'xuanwu')",
            (round_id,)
        ).fetchall()

        elem_data = {}
        for e in elems:
            text = e['output_text'] or ""
            elem_data[e['element']] = text[:1500]

        prior_runs.append({
            "run_id": run_id,
            "topic": row['topic'],
            "similarity": round(sim, 3),
            "best_round": round_num,
            "score": best['overall_score'],
            "qinglong_seeds": elem_data.get("qinglong", ""),
            "baihu_attacks": elem_data.get("baihu", ""),
            "xuanwu_conclusion": elem_data.get("xuanwu", ""),
        })

    return {"found": bool(prior_runs), "prior_runs": prior_runs, "topic": topic}


def format_prior_for_prompt(prior: dict, element: str) -> str:
    """Format retrieved prior context for injection into element prompts.
    Different elements get different slices of prior knowledge:
      - qinglong: prior conclusions + seeds → generate incremental seeds
      - baihu: prior attacks → avoid repeating, find new weaknesses
      - xuanwu: prior conclusions + residuals → track what's resolved vs open
      - zhuque/diting: no injection (work on current round data)
    """
    if not prior or not prior.get("found") or not prior.get("prior_runs"):
        return ""

    runs = prior["prior_runs"]
    parts = []

    if element == "qinglong":
        parts.append("[Engram·历史记忆] 以下是与本主题相关的历史飞轮运行结果。请基于这些已有分析生成增量种子，不要重复已有的发现：")
        for r in runs:
            parts.append(f"\n--- 历史Run: {r['topic']} (相似度:{r['similarity']}, 得分:{r['score']}) ---")
            if r.get("xuanwu_conclusion"):
                parts.append(f"核心结论：{r['xuanwu_conclusion'][:800]}")
            if r.get("qinglong_seeds"):
                parts.append(f"已探索种子：{r['qinglong_seeds'][:600]}")

    elif element == "baihu":
        parts.append("[Engram·历史攻击记忆] 以下是历史运行中白虎已发起的攻击。请避免重复这些攻击，寻找新的漏洞：")
        for r in runs:
            if r.get("baihu_attacks"):
                parts.append(f"\n--- 历史攻击 ({r['topic']}, 得分:{r['score']}) ---")
                parts.append(r['baihu_attacks'][:1000])

    elif element == "xuanwu":
        parts.append("[Engram·历史残差记忆] 以下是历史运行的收敛结论。请识别哪些残差已被解决，哪些仍需关注：")
        for r in runs:
            if r.get("xuanwu_conclusion"):
                parts.append(f"\n--- 历史结论 ({r['topic']}, 得分:{r['score']}) ---")
                parts.append(r['xuanwu_conclusion'][:1000])

    else:
        # zhuque and diting work on current round data, no prior injection
        return ""

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Prompts for each element (v2 — 相生相克 aware)
# ---------------------------------------------------------------------------
def _load_prompt_file(element: str) -> str:
    """Load prompt from prompts_v2/{element}_system.txt if available."""
    prompt_file = PROMPTS_DIR / f"{element}_system.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8").strip()
    return ""


def get_element_prompt(element: str, topic: str, round_num: int,
                       prior_output: str = "", residuals: str = "",
                       sheng_input: str = "", ke_signal: str = "",
                       observer_note: str = "",
                       engram_context: str = "") -> tuple:
    """Returns (system_prompt, user_prompt) for each element.
    Loads from prompts_v2/ files first, falls back to hardcoded."""

    observer_block = f"\n\n[游离态观察者注入]\n{observer_note}" if observer_note else ""
    residual_block = f"\n\n[上轮残差 — 必须回应]\n{residuals}" if residuals else ""
    sheng_block = f"\n\n[相生输入 — 来自上一元素的产出]\n{sheng_input}" if sheng_input else ""
    ke_block = f"\n\n[相克约束 — 必须考虑的限制]\n{ke_signal}" if ke_signal else ""
    engram_block = f"\n\n{engram_context}" if engram_context else ""

    # Try loading from external file
    file_prompt = _load_prompt_file(element)
    if file_prompt:
        try:
            system = file_prompt.format(round_num=round_num)
        except (KeyError, IndexError):
            system = file_prompt.replace("{round_num}", str(round_num))

        # Build user prompt based on element
        from datetime import datetime as _dt
        _today = _dt.now().strftime("%Y年%m月%d日")
        user_parts = [f"当前日期：{_today}", f"主题：{topic}", f"轮次：{round_num}"]
        if element == "qinglong":
            user_parts.extend([engram_block, residual_block, sheng_block, ke_block, observer_block])
        elif element == "zhuque":
            user_parts.extend([f"\n\n[青龙种子]", sheng_block, ke_block, observer_block])
        elif element == "diting":
            user_parts.extend([f"\n\n[朱雀分析]", sheng_block, ke_block, observer_block])
        elif element == "baihu":
            user_parts.extend([engram_block, f"\n\n[谛听校验]", sheng_block, ke_block, observer_block])
        elif element == "xuanwu":
            user_parts.extend([engram_block, f"\n\n[白虎攻击]", sheng_block, ke_block, observer_block])
        return (system, "".join(user_parts))

    # Fallback: hardcoded prompts
    # V9.0: Trading mode - use specialized prompts
    if _TRADING_DOMAIN and HAS_TRADING:
        tp = TRADING_PROMPTS.get(element)
        if tp:
            return (
                tp["system"],
                f"当前日期：{_today}\n标的：{topic}\n轮次：{round_num}{engram_block}\n\n{sheng_block}{ke_block}{observer_block}"
            )
    
    prompts = {
        "qinglong": (
            f"""你是青龙（木·种子生成器），五行飞轮2.0的第一个元素。
你的职责：从主题中发散出多条探索路径（种子）。
第{round_num}轮。如果有上轮残差，必须优先从残差中生成新种子。
相生：你的输出将驱动朱雀（火·执行）。
相克：你被谛听（土·校验）约束——不靠谱的种子会被过滤。

输出JSON格式：
{{"seeds": [{{"id": "s1", "title": "...", "hypothesis": "...", "novelty": 0.0-1.0, "path": "A|B|C"}}], "reasoning": "...", "ke_signal_to_diting": "..."}}

path说明：A=主路径(已验证方向), B=替代路径(可行但非最优), C=探索路径(创新/实验性)""",
            f"当前日期：{_today}\n主题：{topic}\n轮次：{round_num}{engram_block}{residual_block}{sheng_block}{ke_block}{observer_block}"
        ),

        "zhuque": (
            f"""你是朱雀（火·执行分析），五行飞轮2.0的第二个元素。
你的职责：对青龙生成的种子进行深度分析和执行。
第{round_num}轮。
相生：你接收青龙（木）的种子，你的输出将送给谛听（土·校验）。
相克：你被白虎（金·对抗）约束——过度乐观的分析会被攻击。

对每个种子进行：
1. 深度分析（市场/技术/可行性）
2. 关键数据和证据
3. 风险识别
4. 行动建议

输出JSON格式：
{{"analyses": [{{"seed_id": "s1", "analysis": "...", "evidence": [...], "risks": [...], "actions": [...], "confidence": 0.0-1.0}}], "ke_signal_to_baihu": "火克金：执行洞察约束白虎过度攻击", "synthesis": "..."}}""",
            f"当前日期：{_today}\n主题：{topic}\n轮次：{round_num}\n\n[青龙种子]{sheng_block}{ke_block}{observer_block}"
        ),

        "diting": (
            f"""你是谛听（土·现实校验），五行飞轮2.0的第三个元素。
谛听的本义：谛听能辨别天下万物的声音，分辨真伪。
你的职责：校验朱雀的分析是否与现实一致。
第{round_num}轮。
相生：你接收朱雀（火）的分析，你的输出送给白虎（金·对抗）。
相克：你约束青龙（木）——过滤不靠谱的种子方向。

校验维度：
1. 数据是否有来源支撑（还是AI编造的）
2. 逻辑是否自洽
3. 结论是否可验证
4. 是否遗漏了关键因素

输出JSON格式：
{{"verifications": [{{"seed_id": "s1", "verdict": "verified|partial|unverified", "issues": [...], "missing": [...], "reality_score": 0.0-1.0}}], "ke_signal_to_xuanwu": "土克水：谛听校验约束玄武过早收敛"}}""",
            f"当前日期：{_today}\n主题：{topic}\n轮次：{round_num}\n\n[朱雀分析]{sheng_block}{ke_block}{observer_block}"
        ),

        "baihu": (
            f"""你是白虎（金·对抗检验），五行飞轮2.0的第四个元素。
你的职责：攻击已验证的分析，找出漏洞和盲点。
第{round_num}轮。
相生：你接收谛听（土）的校验结果，你的攻击残差送给玄武（水·收敛）。
相克：你约束朱雀（火）——打击过度乐观。但你被玄武（水）约束——不能无限攻击。

攻击方式：
1. 反事实分析（如果假设不成立呢？）
2. 竞争者视角（对手会怎么反驳？）
3. 最坏情况（黑天鹅事件）
4. 数据质疑（这个数据可靠吗？）

输出JSON格式：
{{"attacks": [{{"seed_id": "s1", "attack": "...", "severity": 0.0-1.0, "unresolved": true|false}}], "ke_signal_to_qinglong": "金克木：白虎攻击约束青龙发散", "residuals": [{{"description": "...", "type": "gap|error|assumption|blind_spot"}}]}}""",
            f"当前日期：{_today}\n主题：{topic}\n轮次：{round_num}{engram_block}\n\n[谛听校验]{sheng_block}{ke_block}{observer_block}"
        ),

        "xuanwu": (
            f"""你是玄武（水·收敛），五行飞轮2.0的第五个元素。
你的职责：从白虎的攻击残差中收敛出结论，并生成下一轮的种子。
第{round_num}轮。
相生：你接收白虎（金）的攻击结果，你的输出生成新种子回到青龙（水生木·闭环！）。
相克：你约束白虎（金）——限制无限攻击，推动收敛。你被朱雀（火）约束——不能过早收敛。

你的任务：
1. 综合所有元素的产出
2. 识别最强论点和最弱环节
3. 鲲潜(kun_dive)：在约束条件下做出现实判断，给出概率化预测
4. 鹏举(peng_soar)：去掉所有约束，推导极限形态和第一性原理
5. 合流(dao_merge)：提取底层规则，一句话揭示本质之道
6. 佛家三象(buddhist_three)：从时间维度分析——过去（历史积累与经验沉淀）、现在（当下执行与即时决策）、未来（预测规划与风险预判），每个维度给出战略课题
7. 弗洛伊德心理层(freudian_layers)：从组织行为角度分析——本我Id（冲动探索，被发散出的方向）、自我Ego（理性平衡，收敛后的务实判断）、超我Superego（伦理约束，NPT协议映射的防控机制），每层给出判断
8. 提取残差（未解决问题）作为下一轮种子

输出JSON格式：
{{"conclusion": "最终合的结论", "confidence": 0.0-1.0, "strongest": "最强论点", "weakest": "最弱环节", "kun_dive": {{"conclusion": "约束条件下的现实判断", "predictions": [{{"claim": "...", "probability": 0.0-1.0, "timeframe": "...", "constraints": "..."}}]}}, "peng_soar": {{"limit_form": "如果去掉所有约束,极限形态是什么", "first_principle_basis": "第一性原理依据", "breakthrough_conditions": "突破条件"}}, "dao_merge": {{"rules": ["底层规则1", "底层规则2"], "one_sentence_dao": "一句话揭示底层之道"}}, "buddhist_three": {{"past": {{"observation": "历史积累分析", "strategic_task": "战略课题"}}, "present": {{"observation": "当下执行分析", "strategic_task": "战略课题"}}, "future": {{"observation": "预测规划分析", "strategic_task": "战略课题"}}}}, "freudian_layers": {{"id": {{"observation": "本我冲动探索分析", "judgment": "弗洛伊德判断"}}, "ego": {{"observation": "自我理性平衡分析", "judgment": "弗洛伊德判断"}}, "superego": {{"observation": "超我伦理约束分析", "judgment": "弗洛伊德判断"}}}}, "data_gaps": [{{"gap": "缺口描述", "severity": 0.0-1.0, "consequence": "不补数据的后果", "solution": "解决路径"}}], "strategic_recommendations": [{{"title": "建议标题", "layer": "数据/财务/合规/风控/战略", "detail": "具体建议内容"}}], "core_contradiction": "当前系统的核心矛盾一句话描述", "residuals": [{{"description": "...", "severity": 0.0-1.0, "type": "gap|contradiction|unexplored"}}], "next_seeds": [{{"title": "...", "from_residual": "..."}}], "ke_signal_to_zhuque": "水克火：玄武收敛约束朱雀执行"}}""",
            f"当前日期：{_today}\n主题：{topic}\n轮次：{round_num}{engram_block}\n\n[白虎攻击]{sheng_block}{ke_block}{observer_block}"
        ),
    }

    return prompts[element]


# ---------------------------------------------------------------------------
# Verification Function (R8 AlphaZero insight)
# ---------------------------------------------------------------------------
def verify_round(topic: str, round_num: int, element_outputs: dict,
                 prior_scores: list = None) -> dict:
    """Score this round's output quality. Returns verification dict."""

    all_output = "\n\n".join([
        f"[{ELEMENT_NAMES[e]}]\n{element_outputs.get(e, '(no output)')[:3000]}"
        for e in ELEMENTS
    ])

    prior_ctx = ""
    if prior_scores:
        prior_ctx = f"\n\n前几轮分数：{json.dumps(prior_scores, ensure_ascii=False)}"

    # Try loading verifier prompt from file
    verifier_prompt = _load_prompt_file("verifier")
    if not verifier_prompt:
        verifier_prompt = """你是五行飞轮2.0的验证函数。
你的角色类似AlphaZero的胜负判定——评估本轮输出的质量。

评估维度（每项0.0-1.0）：
1. consistency（一致性）：五个元素的输出是否逻辑自洽
2. novelty（新颖性）：相比上一轮，是否有新的发现
3. depth（深度）：分析是否足够深入，而非泛泛而谈
4. actionability（可行动性）：结论是否可以指导具体行动

输出JSON：
{{"consistency": 0.0-1.0, "novelty": 0.0-1.0, "depth": 0.0-1.0, "actionability": 0.0-1.0, "overall": 0.0-1.0, "verdict": "continue|converged|degrading", "notes": "一句话评价"}}

verdict判定：
- continue: 还有改进空间，残差有价值
- converged: 残差已收敛，可以停止
- degrading: 质量在下降，需要外部输入"""
    system = verifier_prompt

    user = f"主题：{topic}\n轮次：{round_num}\n\n本轮五行输出：\n{all_output}{prior_ctx}"

    verifier_model = ELEMENT_MODEL_ROUTE.get("verifier", "kimi")
    result = call_llm(system, user, temperature=0.1, max_tokens=2048, model_key=verifier_model)
    if result.get("error") or not result["text"]:
        # Smart fallback for verifier
        for fb in ["glm", "qwen", "deepseek"]:
            if fb != verifier_model:
                result = call_llm(system, user, temperature=0.1, max_tokens=2048, model_key=fb)
                if not result.get("error") and result["text"]:
                    break
    if result.get("error") or not result["text"]:
        return {"overall": 0.5, "verdict": "continue", "notes": f"Verification failed: {result.get('error', 'empty')}"}

    return parse_json_safe(result["text"])


# ---------------------------------------------------------------------------
# V10.0: Kunpeng-driven iteration judgment (replaces verify_round)
# ---------------------------------------------------------------------------
def kunpeng_judge(topic, round_num, kunpeng_data, prior_scores=None):
    """Use kunpeng deep analysis to determine round quality.
    Replaces external verifier. Kunpeng confidence drives iteration.
    No LLM call needed - purely computational from existing kunpeng data.
    
    V10.2 Calibration (P8-003 scoring fix):
    - Auto-converge threshold: 0.90 (was 0.85)
    - Plateau delta: 0.05 (was 0.03)
    - Minimum 2 rounds before convergence check
    - Degrading threshold: -0.08 (was -0.05)
    """

    confidence = kunpeng_data.get("confidence", 0.0)
    if isinstance(confidence, str):
        try: confidence = float(confidence)
        except: confidence = 0.5

    def _fq(data):
        """Field quality score 0-1."""
        if not data: return 0.0
        if isinstance(data, str): return min(len(data.strip()) / 100, 1.0)
        if isinstance(data, dict):
            filled = sum(1 for v in data.values() if v)
            return filled / max(len(data), 1)
        if isinstance(data, list): return min(len(data) / 3, 1.0)
        return 0.5

    # Dimensional scores from kunpeng field quality
    consistency = round(_fq(kunpeng_data.get("dao_merge")), 3)
    novelty = round(_fq(kunpeng_data.get("peng_soar")), 3)
    depth = round((_fq(kunpeng_data.get("buddhist_three")) +
                   _fq(kunpeng_data.get("freudian_layers")) +
                   _fq(kunpeng_data.get("data_gaps"))) / 3, 3)
    actionability = round(_fq(kunpeng_data.get("strategic_recommendations")), 3)

    # V10.2: Blended scoring - confidence (50%) + dimensional quality (50%)
    dim_avg = round((consistency + novelty + depth + actionability) / 4, 3)
    overall = round(confidence * 0.50 + dim_avg * 0.50, 3)
    # Floor at 0.30 (even bad analysis has some structure)
    overall = max(overall, 0.30)

    # V10.1: Calibrated convergence thresholds
    CONVERGE_SCORE = 0.90      # Only auto-converge for truly excellent (was 0.85)
    PLATEAU_DELTA = 0.05       # Allow more exploration (was 0.03)
    DEGRADE_DELTA = 0.08       # More tolerance for oscillation (was 0.05)
    MIN_ROUNDS_CONVERGE = 2    # Don't converge before round 2

    # Determine verdict
    verdict = "continue"
    
    # Never converge in round 1
    if round_num < MIN_ROUNDS_CONVERGE:
        verdict = "continue"
    elif confidence >= CONVERGE_SCORE:
        verdict = "converged"
    elif prior_scores and len(prior_scores) >= 1:
        last = prior_scores[-1]
        # Plateau: only if already at decent quality AND stable
        if confidence >= 0.70 and abs(last - confidence) < PLATEAU_DELTA:
            verdict = "converged"  # meaningful plateau at decent quality
        elif confidence < last - DEGRADE_DELTA:
            verdict = "degrading"

    # Notes from core contradiction or dao
    cc = kunpeng_data.get("core_contradiction", "")
    if cc and isinstance(cc, str) and len(cc) > 5:
        notes = cc[:200]
    else:
        dao = kunpeng_data.get("dao_merge", {})
        if isinstance(dao, dict) and dao.get("one_sentence_dao"):
            notes = dao["one_sentence_dao"]
        else:
            notes = f"\u9cb2\u9e4f\u7f6e\u4fe1\u5ea6: {confidence:.2f}"

    print(f"    [\u9cb2\u9e4f\u88c1\u5224] conf={confidence:.2f} c={consistency} n={novelty} d={depth} a={actionability} \u2192 {verdict}")

    return {
        "consistency": consistency,
        "novelty": novelty,
        "depth": depth,
        "actionability": actionability,
        "overall": overall,
        "verdict": verdict,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Core: Run One Round
# ---------------------------------------------------------------------------
def run_round(conn, run_id: str, topic: str, round_num: int, prev_round_ke: dict = None,
              seeds: str = "", residuals: str = "",
              observer_injection: str = "",
              prior_context: dict = None,
              edge_mode: str = "full") -> tuple:
    """Execute one full round of the 5-element flywheel.
    Returns (element_outputs, verification, residuals_text)."""

    round_id = gen_id("rnd_")
    conn.execute(
        "INSERT INTO rounds (id, run_id, round_num, input_seeds, input_residuals, observer_injection, status) VALUES (?,?,?,?,?,?,?)",
        (round_id, run_id, round_num, seeds[:16000], residuals[:16000],
         observer_injection[:4000] if observer_injection else None, "running")
    )
    conn.commit()

    print(f"\n{'='*70}")
    print(f"  ROUND {round_num}")
    print(f"  Topic: {topic}")
    if observer_injection:
        print(f"  🌙 游离态注入: {observer_injection[:100]}...")
    print(f"{'='*70}")

    element_outputs = {}
    ke_signals = {}  # Accumulated
    prev_ke = prev_round_ke if prev_round_ke else {}  # ke signals from prev round

    def _run_one_element(elem, input_text, ke_signal, engram_block=""):
        """Run a single element with retry+fallback. Thread-safe."""
        model_key = ELEMENT_MODEL_ROUTE.get(elem, "minimax")
        model_label = MODEL_REGISTRY.get(model_key, {}).get("model", "?")
        print(f"    [model] {model_label} ({model_key})")

        system, user = get_element_prompt(
            elem, topic, round_num,
            prior_output=input_text,
            residuals=residuals if elem == "qinglong" else "",
            sheng_input=input_text,
            ke_signal=ke_signal,
            observer_note=observer_injection if elem == "qinglong" else "",
            engram_context=engram_block
        )

        t0 = time.time()
        # V11.2: xuanwu needs more tokens for complete kunpeng JSON output
        _elem_max_tokens = 16384 if elem in ("xuanwu", "zhuque") else 8192
        result = call_llm(system, user, temperature=0.3, max_tokens=_elem_max_tokens, model_key=model_key)
        elapsed = int((time.time() - t0) * 1000)

        # Same-model retry once
        if result.get("error") and not result["text"]:
            print(f"    [warn] {model_key} failed, retrying...")
            time.sleep(3)
            result = call_llm(system, user, temperature=0.3, max_tokens=_elem_max_tokens, model_key=model_key)
            elapsed = int((time.time() - t0) * 1000)

        # Smart fallback chain
        if result.get("error") and not result["text"]:
            fallback_chain = {"qwen": ["kimi-k2.6", "glm"], "kimi-k2.6": ["qwen", "glm"],
                             "glm": ["qwen", "kimi"], "kimi": ["glm", "qwen"],
                             "minimax": ["kimi", "qwen"]}
            for fb_key in fallback_chain.get(model_key, ["qwen"]):
                print(f"    [warn] {model_key} failed, fallback to {fb_key}...")
                result = call_llm(system, user, temperature=0.3, max_tokens=_elem_max_tokens, model_key=fb_key)
                elapsed = int((time.time() - t0) * 1000)
                if not result.get("error") or result["text"]:
                    model_key = fb_key
                    break

        output = result["text"] if result["text"] else f"(failed: {result.get('error', 'empty')})"
        output = _clean_llm_output(output)  # V9.1: strip LLM artifacts at source
        return {"elem": elem, "output": output, "result": result, "elapsed": elapsed,
                "model_key": model_key, "input_text": input_text, "ke_signal": ke_signal}

    def _store_element(elem_data):
        """Store element result in DB."""
        elem = elem_data["elem"]
        output = elem_data["output"]
        result = elem_data["result"]
        elapsed = elem_data["elapsed"]
        model_key = elem_data["model_key"]
        input_text = elem_data["input_text"]
        ke_signal = elem_data["ke_signal"]

        elem_id = gen_id("elm_")
        idx = ELEMENTS.index(elem)
        sheng_from = SHENGKE["sheng"].get(ELEMENTS[idx - 1] if idx > 0 else "xuanwu")

        conn.execute(
            """INSERT INTO elements (id, round_id, run_id, element, input_text, output_text,
               sheng_from, ke_signal, tokens_in, tokens_out, latency_ms, model_key, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (elem_id, round_id, run_id, elem, input_text[:8000], output[:32000],
             sheng_from, (str(ke_signal) if not isinstance(ke_signal, str) else ke_signal)[:8000], result["tokens_in"], result["tokens_out"],
             elapsed, model_key, "done" if result["text"] else "failed")
        )
        conn.commit()

        preview = output[:120].replace("\n", " ")
        print(f"    [ok] {result['tokens_out']} tokens, {elapsed}ms")
        print(f"    [text] {preview}...")

        # Extract ke signals
        try:
            parsed = parse_json_safe(output)
            for key in ["ke_signal_to_qinglong", "ke_signal_to_zhuque", "ke_signal_to_baihu",
                         "ke_signal_to_diting", "ke_signal_to_xuanwu"]:
                if key in parsed:
                    ke_signals[elem] = parsed[key]
        except Exception:
            pass

    # ================================================================
    # PHASED PARALLEL EXECUTION
    # Before: qinglong -> zhuque -> diting -> baihu -> xuanwu (5 serial)
    # After:  qinglong -> [zhuque || baihu] -> diting -> xuanwu (4 phases)
    # Saves ~30-50s per round by running zhuque and baihu concurrently
    # ================================================================

    def _engram(elem):
        if prior_context and prior_context.get("found") and round_num == 1:
            return format_prior_for_prompt(prior_context, elem)
        return ""

    # --- Phase 1: qinglong (seeds, independent) ---
    print(f"\n  >> Phase 1: {ELEMENT_NAMES['qinglong']}")
    qinglong_data = _run_one_element("qinglong", seeds, prev_ke.get("baihu_to_qinglong", ""), _engram("qinglong"))  # 金克木: baihu constrains qinglong
    element_outputs["qinglong"] = qinglong_data["output"]
    _store_element(qinglong_data)

    qinglong_out = qinglong_data["output"]
    qinglong_ke = ke_signals.get("qinglong", "")

    # --- Edge Agents: transform qinglong output ---
    edge_reg = _get_edge_registry()
    _do_sheng = edge_mode in ("sheng", "full")
    _do_ke = edge_mode in ("ke", "full")
    print(f"\n    [edge] mode={edge_mode} | 木生火{'✓' if _do_sheng else '○'} 木克土{'✓' if _do_ke else '○'}")
    if _do_sheng and _do_ke:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="edge") as _ep:
            _f_gen = _ep.submit(edge_reg.process_generation, "qinglong", "zhuque", qinglong_out, topic, round_num)
            _f_ke = _ep.submit(edge_reg.process_control, "qinglong", "diting", qinglong_out, topic, round_num)
            zhuque_input = _f_gen.result()
            ke_from_qinglong_to_diting = _f_ke.result()
    elif _do_sheng:
        zhuque_input = edge_reg.process_generation("qinglong", "zhuque", qinglong_out, topic, round_num)
        ke_from_qinglong_to_diting = ""
    elif _do_ke:
        zhuque_input = qinglong_out
        ke_from_qinglong_to_diting = edge_reg.process_control("qinglong", "diting", qinglong_out, topic, round_num)
    else:
        zhuque_input = qinglong_out
        ke_from_qinglong_to_diting = ""

    # --- Phase 2: zhuque || baihu (parallel, both read transformed input) ---
    print(f"\n  >> Phase 2: {ELEMENT_NAMES['zhuque']} || {ELEMENT_NAMES['baihu']}  [PARALLEL]")
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_zhuque = pool.submit(_run_one_element, "zhuque", zhuque_input, prev_ke.get("xuanwu_to_zhuque", ""), _engram("zhuque"))  # 水克火: xuanwu constrains zhuque
        future_baihu = pool.submit(_run_one_element, "baihu", qinglong_out, prev_ke.get("zhuque_to_baihu", ""), _engram("baihu"))  # 火克金: zhuque constrains baihu

        zhuque_data = future_zhuque.result()
        baihu_data = future_baihu.result()

    element_outputs["zhuque"] = zhuque_data["output"]
    element_outputs["baihu"] = baihu_data["output"]
    _store_element(zhuque_data)
    _store_element(baihu_data)

    # --- Edge Agents: 金克木 (baihu constrains next-round qinglong) ---
    ke_from_baihu_to_qinglong = edge_reg.process_control("baihu", "qinglong", baihu_data["output"], topic, round_num) if _do_ke else ""

    # Combine for downstream (edge-enhanced version below)
    zhuque_ke = ke_signals.get("zhuque", "")

    # --- Edge Agents: transform for diting ---
    print(f"\n    [edge] mode={edge_mode} | 火生土{'✓' if _do_sheng else '○'} 火克金{'✓' if _do_ke else '○'}")
    if _do_sheng and _do_ke:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="edge") as _ep:
            _f_gen = _ep.submit(edge_reg.process_generation, "zhuque", "diting", zhuque_data["output"], topic, round_num)
            _f_ke = _ep.submit(edge_reg.process_control, "zhuque", "baihu", zhuque_data["output"], topic, round_num)
            diting_input = _f_gen.result()
            ke_from_zhuque_to_baihu = _f_ke.result()  # 火克金
    elif _do_sheng:
        diting_input = edge_reg.process_generation("zhuque", "diting", zhuque_data["output"], topic, round_num)
        ke_from_zhuque_to_baihu = ""
    elif _do_ke:
        diting_input = zhuque_data["output"]
        ke_from_zhuque_to_baihu = edge_reg.process_control("zhuque", "baihu", zhuque_data["output"], topic, round_num)
    else:
        diting_input = zhuque_data["output"]
        ke_from_zhuque_to_baihu = ""
    combined_for_diting = f"=== 火生土·结构化命题 ===\n{diting_input}\n\n=== 白虎攻击 ===\n{baihu_data['output']}"

    # --- Phase 3: diting (verifies structured propositions + attack results) ---
    print(f"\n  >> Phase 3: {ELEMENT_NAMES['diting']}")
    diting_ke = ke_from_qinglong_to_diting if ke_from_qinglong_to_diting else qinglong_ke
    diting_data = _run_one_element("diting", combined_for_diting, diting_ke, _engram("diting"))
    element_outputs["diting"] = diting_data["output"]
    _store_element(diting_data)

    # --- Edge Agents: transform for xuanwu ---
    print(f"\n    [edge] mode={edge_mode} | 土生金{'✓' if _do_sheng else '○'} 金生水{'✓' if _do_sheng else '○'} 土克水{'✓' if _do_ke else '○'}")
    if _do_sheng:
        baihu_targets = edge_reg.process_generation("diting", "baihu", diting_data["output"], topic, round_num)
    else:
        baihu_targets = diting_data["output"]
    if _do_sheng and _do_ke:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="edge") as _ep:
            _f_gen = _ep.submit(edge_reg.process_generation, "baihu", "xuanwu", baihu_data["output"], topic, round_num)
            _f_ke = _ep.submit(edge_reg.process_control, "diting", "xuanwu", diting_data["output"], topic, round_num)
            xuanwu_input = _f_gen.result()
            ke_from_diting_to_xuanwu = _f_ke.result()  # 土克水
    elif _do_sheng:
        xuanwu_input = edge_reg.process_generation("baihu", "xuanwu", baihu_data["output"], topic, round_num)
        ke_from_diting_to_xuanwu = ""
    elif _do_ke:
        xuanwu_input = baihu_data["output"]
        ke_from_diting_to_xuanwu = edge_reg.process_control("diting", "xuanwu", diting_data["output"], topic, round_num)
    else:
        xuanwu_input = baihu_data["output"]
        ke_from_diting_to_xuanwu = ""
    # Note: xuanwu→zhuque (水克火) deferred - actual call happens after xuanwu runs below

    combined_for_xuanwu = f"=== 谛听校验 ===\n{diting_data['output']}\n\n=== 金生水·对抗收敛 ===\n{xuanwu_input}"

    # --- Phase 4: xuanwu (converges with edge-processed input) ---
    print(f"\n  >> Phase 4: {ELEMENT_NAMES['xuanwu']}")
    xuanwu_ke = ke_from_diting_to_xuanwu if ke_from_diting_to_xuanwu else ""  # 土克水: diting constrains xuanwu
    xuanwu_data = _run_one_element("xuanwu", combined_for_xuanwu, xuanwu_ke, _engram("xuanwu"))
    element_outputs["xuanwu"] = xuanwu_data["output"]
    _store_element(xuanwu_data)

    # --- Edge Agents: 水克火 (deferred cross-round signal) ---
    ke_from_xuanwu_to_zhuque = edge_reg.process_control("xuanwu", "zhuque", xuanwu_data["output"], topic, round_num) if _do_ke else ""  # 水克火
    # Store cross-round edge signals for next iteration
    element_outputs["_edge_ke"] = {
        "baihu_to_qinglong": ke_from_baihu_to_qinglong if ke_from_baihu_to_qinglong else "",
        "xuanwu_to_zhuque": ke_from_xuanwu_to_zhuque if ke_from_xuanwu_to_zhuque else "",
        "zhuque_to_baihu": ke_from_zhuque_to_baihu if ke_from_zhuque_to_baihu else "",
    }

    # --- V10.0: Kunpeng Judgment (replaces external verifier) ---
    print(f"\n  🔍 鲲鹏裁判...")
    prior_scores = []
    prior_entries = conn.execute(
        "SELECT overall_score FROM ledger WHERE run_id = ? ORDER BY round_num", (run_id,)
    ).fetchall()
    prior_scores = [r["overall_score"] for r in prior_entries if r["overall_score"]]

    # Extract residuals AND 鲲潜/鹏举/合流 from xuanwu output
    residuals_text = ""
    kunpeng_data = {}  # V8.5: structured convergence data
    try:
        xuanwu_parsed = parse_json_safe(element_outputs.get("xuanwu", "{}"))
        # V9.0: Enrichment pass for missing fields
        # V11.5: Enrich zhuque key_parameters + references if truncated
        enrich_zhuque(topic, element_outputs, call_llm)
        print(f"    [TRACE] About to call enrich_xuanwu, xuanwu_parsed keys: {list(xuanwu_parsed.keys())}")
        xuanwu_parsed = enrich_xuanwu(topic, round_num, element_outputs, xuanwu_parsed, call_llm)
        residuals_list = xuanwu_parsed.get("residuals", [])
        next_seeds = xuanwu_parsed.get("next_seeds", [])
        
        # V8.5: Parse 鲲潜·鹏举·合流 three-stage convergence
        kun_dive = xuanwu_parsed.get("kun_dive", {})
        peng_soar = xuanwu_parsed.get("peng_soar", {})
        dao_merge = xuanwu_parsed.get("dao_merge", {})
        confidence = xuanwu_parsed.get("confidence", 0.0)
        ke_signal = xuanwu_parsed.get("ke_signal_to_zhuque", "")  # 水克火
        
        buddhist_three = xuanwu_parsed.get("buddhist_three", {})
        freudian_layers = xuanwu_parsed.get("freudian_layers", {})
        data_gaps = xuanwu_parsed.get("data_gaps", [])
        strategic_recs = xuanwu_parsed.get("strategic_recommendations", [])
        core_contradiction = xuanwu_parsed.get("core_contradiction", "")
        
        kunpeng_data = {
            "kun_dive": kun_dive,    # 鲲潜：约束下的现实结论
            "peng_soar": peng_soar,  # 鹏举：无约束极限推演
            "dao_merge": dao_merge,  # 合流：底层规律揭示
            "buddhist_three": buddhist_three,  # 佛家三象：过去/现在/未来
            "freudian_layers": freudian_layers,  # 弗洛伊德：本我/自我/超我
            "data_gaps": data_gaps,  # 数据缺口表
            "strategic_recommendations": strategic_recs,  # 战略建议
            "confidence": confidence,
            "ke_signal_to_zhuque": ke_signal,  # 水克火
        }
        
        residuals_text = json.dumps({
            "residuals": residuals_list,
            "next_seeds": next_seeds,
            "round_conclusion": kun_dive.get("conclusion", xuanwu_parsed.get("conclusion", "")),
            "kunpeng": kunpeng_data,
        }, ensure_ascii=False, indent=2)
        
        # Log structured extraction
        has_kun = bool(kun_dive.get("conclusion") or kun_dive.get("predictions"))
        has_peng = bool(peng_soar.get("limit_form") or peng_soar.get("first_principle_basis"))
        has_dao = bool(dao_merge.get("rules") or dao_merge.get("one_sentence_dao"))
        print(f"    [鲲潜/鹏举/合流] kun={has_kun} peng={has_peng} dao={has_dao} conf={confidence}")
    except Exception as _e:
        import traceback
        print(f"    [V9.0 ERROR] Enrichment/extraction failed: {_e}")
        print(traceback.format_exc())
        residuals_text = element_outputs.get("xuanwu", "")[:3000]
        # V11.1 Fallback: recover confidence from pre-enrichment xuanwu parse
        try:
            _xw_fallback = parse_json_safe(element_outputs.get("xuanwu", "{}"))
            _fb_conf = _xw_fallback.get("confidence", 0.5)
            if isinstance(_fb_conf, str):
                try: _fb_conf = float(_fb_conf)
                except: _fb_conf = 0.5
            kunpeng_data = {
                "confidence": _fb_conf,
                "kun_dive": _xw_fallback.get("kun_dive", {}),
                "peng_soar": _xw_fallback.get("peng_soar", {}),
                "dao_merge": _xw_fallback.get("dao_merge", {}),
            }
            print(f"    [V11.1 FALLBACK] Recovered confidence={_fb_conf:.2f} from xuanwu")
        except:
            kunpeng_data = {"confidence": 0.5}
            print("    [V11.1 FALLBACK] Using default confidence=0.50")

    # V10.0: Kunpeng judges this round (replaces verify_round)
    verification = kunpeng_judge(topic, round_num, kunpeng_data, prior_scores)

    # V12.0: IntegrityMesh — adversarial quality scoring (骨骼, not 门卫)
    # Removing this degrades output quality, not just safety.
    if HAS_INTEGRITY and _integrity_mesh:
        try:
            dim_scores = {
                "logical_consistency": float(verification.get("consistency", verification.get("overall", 0.5))),
                "evidence_integrity": float(verification.get("depth", verification.get("overall", 0.5))),
                "temporal_robustness": float(verification.get("overall", 0.5)),
                "stakeholder_symmetry": float(verification.get("overall", 0.5)),
                "counterfactual_survival": float(verification.get("overall", 0.5)) * 0.9,
                "information_asymmetry": float(verification.get("actionability", verification.get("overall", 0.5))),
            }
            integrity_score = _integrity_mesh.compute_integrity_score(dim_scores)
            weaknesses = _integrity_mesh.detect_structural_weakness(dim_scores)
            verification["integrity_score"] = integrity_score
            verification["structural_weaknesses"] = weaknesses
            if weaknesses:
                print(f"    [integrity] {len(weaknesses)} structural weakness(es) detected")
                for w in weaknesses:
                    print(f"      ⚠ {w['type']}: {w['description'][:80]}")
            else:
                print(f"    [integrity] score={integrity_score:.3f}, no structural weaknesses")
        except Exception as _im_err:
            print(f"    [integrity] error: {_im_err}")

    # V13.0: Adversarial Enforcer — 白虎审计强制化
    if _adversarial_enforcer:
        try:
            baihu_raw = element_outputs.get("baihu", "")
            _audit = _adversarial_enforcer.enforce(baihu_raw, verification.get("overall", 0.5))
            if _audit.is_rubber_stamp:
                print(f"    [adversarial] ⚠ Rubber-stamp audit detected — baihu may not be challenging enough")
            adj_score, adj_reason = _adversarial_enforcer.adjust_score(verification.get("overall", 0.5), _audit)
            if adj_score != verification.get("overall", 0.5):
                verification["pre_adversarial_score"] = verification.get("overall", 0.5)
                verification["overall"] = adj_score
                print(f"    [adversarial] Score adjusted: {verification['pre_adversarial_score']:.3f} → {adj_score:.3f} ({adj_reason})")
            else:
                print(f"    [adversarial] Audit passed, no score adjustment needed")
            verification["adversarial_audit"] = {
                "attacks": len(_audit.attacks),
                "max_severity": _audit.max_severity,
                "unresolved": _audit.unresolved_count,
                "rubber_stamp": _audit.is_rubber_stamp,
                "passed": _audit.passed
            }
        except Exception as _ae_err:
            print(f"    [adversarial] error (non-fatal): {_ae_err}")

    # Store in ledger
    ledger_id = gen_id("ldg_")
    v = verification
    conn.execute(
        """INSERT INTO ledger (id, run_id, round_id, round_num,
           consistency_score, novelty_score, depth_score, actionability_score,
           overall_score, residuals, residual_count, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ledger_id, run_id, round_id, round_num,
         v.get("consistency"), v.get("novelty"), v.get("depth"), v.get("actionability"),
         v.get("overall", 0.5), residuals_text[:32000],
         len(residuals_list) if 'residuals_list' in dir() else 0,
         v.get("notes", ""))
    )
    conn.execute(
        "UPDATE rounds SET status = 'done', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (round_id,)
    )
    conn.commit()

    overall = v.get("overall", 0.5)
    verdict = v.get("verdict", "continue")
    notes = v.get("notes", "")
    print(f"    Score: {overall:.2f} | Verdict: {verdict}")
    print(f"    Notes: {notes}")

    # Collect ke signals for cross-round restraint cycle
    _round_ke = {}
    for _en, _ed in [("diting", element_outputs.get("diting", "")), ("baihu", element_outputs.get("baihu", "")), ("xuanwu", element_outputs.get("xuanwu", "")), ("qinglong", element_outputs.get("qinglong", "")), ("zhuque", element_outputs.get("zhuque", ""))]:
        try:
            _p = json.loads(_ed.strip().strip("`").replace("```json", "").replace("```", ""))
            for _t in ["qinglong", "zhuque", "diting", "baihu", "xuanwu"]:
                _k = f"ke_signal_to_{_t}"
                if _k in _p and _p[_k]: _round_ke[f"{_en}_to_{_t}"] = _p[_k]
        except: pass
    # Merge edge agent ke signals into the ke_signals dict
    _edge_ke = element_outputs.get("_edge_ke", {})
    for k, v in _edge_ke.items():
        if v:
            _round_ke[k] = v
    element_outputs["_ke_signals"] = _round_ke

    # --- V11.0: Conflict Detection (Logic Conflict Pool) ---
    _conflicts = []
    _conflict_seeds = ""
    try:
        _conflicts = detect_conflicts(element_outputs, topic, round_num, run_id, call_llm, conn)
        if _conflicts:
            _conflict_seeds = generate_conflict_seeds(_conflicts, topic)
            stats = get_conflict_stats(conn, run_id)
            print(f"    [conflict] Pool stats: {stats}")
    except Exception as _ce:
        print(f"    [conflict] Detection failed (non-fatal): {_ce}")
    element_outputs["_conflicts"] = _conflicts
    element_outputs["_conflict_seeds"] = _conflict_seeds
    return element_outputs, verification, residuals_text, kunpeng_data




# ---------------------------------------------------------------------------
# V9.0: Xuanwu Enrichment Pass (fills missing fields)
# ---------------------------------------------------------------------------
ENRICHMENT_FIELDS = ["kun_dive", "peng_soar", "dao_merge", "buddhist_three", 
                     "freudian_layers", "data_gaps", "strategic_recommendations", 
                     "core_contradiction"]


def enrich_zhuque(topic, element_outputs, call_llm_fn):
    """V11.7: Second-pass enrichment for zhuque key_parameters and references.
    Preserves original analyses from truncated JSON output."""
    zhuque_raw = element_outputs.get("zhuque", "")
    if not zhuque_raw:
        return
    
    raw_str = str(zhuque_raw).strip()
    
    # Check if raw text looks truncated (doesn't end with proper JSON closing)
    is_truncated = not raw_str.rstrip().endswith('}')
    print(f"    [V11.7] Zhuque raw: {len(raw_str)} chars, truncated={is_truncated}, ends=...{raw_str[-40:]!r}")
    
    # Try to parse JSON - use multiple strategies
    zhuque_parsed = parse_json_safe(zhuque_raw)
    is_raw_fallback = (len(zhuque_parsed) == 1 and 'raw' in zhuque_parsed)
    
    if is_raw_fallback:
        # parse_json_safe couldn't parse it, try partial extraction
        import re
        # Try to extract analyses array even from truncated JSON
        partial = {}
        # Find analyses array
        analyses_match = re.search(r'"analyses"\s*:\s*\[', raw_str)
        if analyses_match:
            # Try to find complete analysis objects
            analyses = []
            # Find each seed analysis block
            seed_pattern = re.compile(r'\{\s*"seed_id"\s*:\s*"(s\d+)"\s*,\s*"analysis"\s*:\s*"((?:[^"\\]|\\.)*)(?:"\s*\})?', re.DOTALL)
            for m in seed_pattern.finditer(raw_str):
                sid = m.group(1)
                text = m.group(2)[:3000]  # Limit size
                analyses.append({"seed_id": sid, "analysis": text})
            if analyses:
                partial["analyses"] = analyses
                print(f"    [V11.7] Extracted {len(analyses)} seed analyses from truncated JSON")
        zhuque_parsed = partial
    
    has_params = isinstance(zhuque_parsed.get("key_parameters"), list) and len(zhuque_parsed.get("key_parameters", [])) > 0
    has_refs = isinstance(zhuque_parsed.get("references"), list) and len(zhuque_parsed.get("references", [])) > 0
    
    if has_params and has_refs and not is_truncated:
        print(f"    [V11.7] Zhuque complete with key_parameters({len(zhuque_parsed['key_parameters'])})+references({len(zhuque_parsed['references'])}), skip")
        return
    
    missing = []
    if not has_params: missing.append("key_parameters")
    if not has_refs: missing.append("references")
    if is_truncated: missing.append("TRUNCATED")
    print(f"    [V11.7] Zhuque needs enrichment: {missing}")
    
    # Build context from whatever analyses we have
    analyses = zhuque_parsed.get("analyses", [])
    analyses_summary = ""
    for a in analyses[:3]:
        if isinstance(a, dict):
            sid = a.get("seed_id", "?")
            text = str(a.get("analysis", ""))[:500]
            analyses_summary += f"Seed {sid}: {text}\n"
    
    if not analyses_summary:
        # Fall back to raw text
        analyses_summary = raw_str[:2000]
    
    enrichment_prompt = f"""当前日期：{__import__("datetime").datetime.now().strftime("%Y年%m月%d日")}
基于以下朱雀（火·执行）分析结果，提取关键参数演进表和参考文献列表。

主题：{topic}

朱雀分析摘要：
{analyses_summary}

请输出严格JSON，包含以下字段：
{{
  "key_parameters": [
    {{"name": "参数名称", "current": "当前值/状态", "trend": "趋势方向", "source": "数据来源", "confidence": "HIGH/MEDIUM/LOW"}}
  ],
  "references": [
    {{"id": 1, "source": "来源名称", "type": "VERIFIED/ESTIMATE/INFERRED", "detail": "具体内容描述"}}
  ]
}}

要求：
- key_parameters: 从分析中提取3-8个关键量化指标及其演进趋势
- references: 列出分析中引用的所有数据来源，标注可信度等级
- 只输出JSON，不要其他文字"""

    try:
        resp = call_llm_fn(
            system_prompt="你是一个结构化数据提取器。从分析文本中提取关键参数和参考文献。只输出JSON。",
            user_prompt=enrichment_prompt,
            model_key="deepseek"
        )
        enrichment_raw = resp.get("text", "") if isinstance(resp, dict) else str(resp)
        print(f"    [V11.7] Zhuque enrichment response: {len(enrichment_raw)} chars")
        enriched = parse_json_safe(enrichment_raw)
        if enriched and not (len(enriched) == 1 and 'raw' in enriched):
            filled = 0
            if enriched.get("key_parameters") and not has_params:
                zhuque_parsed["key_parameters"] = enriched["key_parameters"]
                filled += 1
                print(f"    [V11.7] Filled: key_parameters ({len(enriched['key_parameters'])} items)")
            if enriched.get("references") and not has_refs:
                zhuque_parsed["references"] = enriched["references"]
                filled += 1
                print(f"    [V11.7] Filled: references ({len(enriched['references'])} items)")
            
            if filled > 0:
                # Write enriched data back, preserving all existing fields
                element_outputs["zhuque"] = json.dumps(zhuque_parsed, ensure_ascii=False, indent=2)
                print(f"    [V11.7] Zhuque enriched output: {len(element_outputs['zhuque'])} chars, keys: {list(zhuque_parsed.keys())}")
            else:
                print(f"    [V11.7] No new fields to fill")
        else:
            print(f"    [V11.7] Enrichment JSON parse failed")
    except Exception as e:
        print(f"    [V11.7] Zhuque enrichment error: {e}")


def enrich_xuanwu(topic, round_num, element_outputs, xuanwu_parsed, call_llm_fn):
    """Second-pass LLM call to fill fields the first xuanwu pass missed."""
    missing = [f for f in ENRICHMENT_FIELDS if not xuanwu_parsed.get(f)]
    if not missing:
        print(f"    [V9.0] All enrichment fields present, skip")
        return xuanwu_parsed
    
    print(f"    [V9.0] Missing {len(missing)} fields: {missing}, running enrichment pass...")
    
    # Build focused prompt with only the missing fields
    field_schemas = {
        "kun_dive": '"kun_dive": {{"conclusion": "约束条件下的现实判断", "predictions": [{{"claim": "具体预测", "probability": 0.0-1.0, "timeframe": "时间范围", "constraints": "约束条件"}}]}}',
        "peng_soar": '"peng_soar": {{"limit_form": "去掉所有约束后的极限形态", "first_principle_basis": "第一性原理依据", "breakthrough_conditions": "突破条件"}}',
        "dao_merge": '"dao_merge": {{"rules": ["底层规律1", "底层规律2"], "one_sentence_dao": "一句话揭示底层之道"}}',
        "buddhist_three": '"buddhist_three": {{"past": {{"observation": "历史观察分析", "strategic_task": "战略课题"}}, "present": {{"observation": "当前执行分析", "strategic_task": "战略课题"}}, "future": {{"observation": "预判规划分析", "strategic_task": "战略课题"}}}}',
        "freudian_layers": '"freudian_layers": {{"id": {{"observation": "本我冲动探测分析", "judgment": "独立评价判断"}}, "ego": {{"observation": "自我理性平衡分析", "judgment": "独立评价判断"}}, "superego": {{"observation": "超我规范约束分析", "judgment": "独立评价判断"}}}}',
        "data_gaps": '"data_gaps": [{{"gap": "缺失数据", "severity": 0.0-1.0, "consequence": "缺少该数据的后果", "solution": "解决路径"}}]',
        "strategic_recommendations": '"strategic_recommendations": [{{"title": "建议标题", "layer": "运营/技术/合规/商务/战略", "detail": "具体建议内容"}}]',
        "core_contradiction": '"core_contradiction": "当前系统的核心矛盾一句话描述"',
    }
    
    schema_parts = [field_schemas[f] for f in missing if f in field_schemas]
    schema_str = ", ".join(schema_parts)
    
    # Context: include the first-pass conclusion
    first_conclusion = xuanwu_parsed.get("conclusion", "")
    first_confidence = xuanwu_parsed.get("confidence", 0)
    
    enrichment_prompt = f"""当前日期：{__import__("datetime").datetime.now().strftime("%Y年%m月%d日")}\n基于以下分析的收敛结论，补充深度分析字段。

主题：{topic}
已有收敛结论：{first_conclusion}
置信度：{first_confidence}

各元素分析摘要：
- 青龙(种子): {str(element_outputs.get('qinglong', ''))[:500]}
- 朱雀(执行): {str(element_outputs.get('zhuque', ''))[:500]}
- 谛听(审计): {str(element_outputs.get('diting', ''))[:500]}
- 白虎(攻击): {str(element_outputs.get('baihu', ''))[:500]}

请输出严格JSON，只包含以下字段：
{{{schema_str}}}"""
    
    try:
        enrichment_resp = call_llm_fn(
            system_prompt="你是一个深度分析补充器。基于已有分析结论，输出结构化的深度分析。只输出JSON，不要其他文字。",
            user_prompt=enrichment_prompt,
            model_key="qwen"
        )
        # call_llm returns dict with "text" key
        enrichment_raw = enrichment_resp.get("text", "") if isinstance(enrichment_resp, dict) else str(enrichment_resp)
        print(f"    [V9.0] Enrichment LLM response: {len(enrichment_raw)} chars")
        enriched = parse_json_safe(enrichment_raw)
        if enriched:
            for field in missing:
                if enriched.get(field):
                    xuanwu_parsed[field] = enriched[field]
                    print(f"    [V9.0] Filled: {field}")
            
            # Recount missing
            still_missing = [f for f in ENRICHMENT_FIELDS if not xuanwu_parsed.get(f)]
            if still_missing:
                print(f"    [V9.0] Still missing after enrichment: {still_missing}")
            else:
                print(f"    [V9.0] All fields filled successfully!")
    except Exception as e:
        print(f"    [V9.0] Enrichment error: {e}")
    
    return xuanwu_parsed



def quality_check(result: dict) -> dict:
    """V9.0: Quality gate - validate report completeness before publishing."""
    rounds = result.get("rounds", [])
    kunpeng = result.get("kunpeng", {})
    
    quality = {"score": 0, "issues": [], "grade": "F"}
    
    # Check basic structure
    if not rounds:
        quality["issues"].append("No rounds completed")
        return quality
    
    score = 0
    
    # 1. Has conclusion (20pts)
    conclusion = kunpeng.get("round_conclusion", "")
    if conclusion and len(conclusion) > 20:
        score += 20
    else:
        quality["issues"].append("Weak or missing conclusion")
    
    # 2. Has kun_dive with predictions (15pts)
    kd = kunpeng.get("kun_dive", {})
    if kd and (kd.get("conclusion") or kd.get("predictions")):
        score += 15
    else:
        quality["issues"].append("Missing kun_dive (constrained predictions)")
    
    # 3. Has peng_soar (10pts)
    ps = kunpeng.get("peng_soar", {})
    if ps and (ps.get("limit_form") or ps.get("first_principle_basis")):
        score += 10
    else:
        quality["issues"].append("Missing peng_soar (unconstrained analysis)")
    
    # 4. Has buddhist_three (10pts)
    bt = kunpeng.get("buddhist_three", {})
    if bt and isinstance(bt, dict) and any(bt.values()):
        score += 10
    else:
        quality["issues"].append("Missing buddhist_three (past/present/future)")
    
    # 5. Has freudian_layers (10pts)
    fl = kunpeng.get("freudian_layers", {})
    if fl and isinstance(fl, dict) and any(fl.values()):
        score += 10
    else:
        quality["issues"].append("Missing freudian_layers (id/ego/superego)")
    
    # 6. Has data_gaps (10pts)
    dg = kunpeng.get("data_gaps", [])
    if dg and isinstance(dg, list) and len(dg) > 0:
        score += 10
    else:
        quality["issues"].append("Missing data_gaps table")
    
    # 7. Has strategic_recommendations (10pts)
    sr = kunpeng.get("strategic_recommendations", [])
    if sr and isinstance(sr, list) and len(sr) > 0:
        score += 10
    else:
        quality["issues"].append("Missing strategic_recommendations")
    
    # 8. All elements present (15pts)
    last_elements = rounds[-1].get("elements", {})
    expected_elements = {"qinglong", "zhuque", "diting", "baihu", "xuanwu"}
    present = set(last_elements.keys()) & expected_elements
    if len(present) == 5:
        score += 15
    else:
        quality["issues"].append(f"Missing elements: {expected_elements - present}")
    
    quality["score"] = score
    if score >= 90:
        quality["grade"] = "A"
    elif score >= 70:
        quality["grade"] = "B"
    elif score >= 50:
        quality["grade"] = "C"
    elif score >= 30:
        quality["grade"] = "D"
    else:
        quality["grade"] = "F"
    
    return quality


# ---------------------------------------------------------------------------
# Core: Run Full Pipeline
# ---------------------------------------------------------------------------
def run_flywheel(topic: str, max_rounds: int = 3, interactive: bool = False,
                 inject_file: str = None, run_id: str = None, amplifier: bool = None,
                 edge_mode: str = "full", progress_callback=None):
    """Run the complete flywheel 2.0 pipeline.
    inject_file: path to a file whose contents are used as observer injection each round.
    run_id: optional pre-created run_id (from API). If None, creates new.
    """

    conn = init_db()
    if run_id is None:
        run_id = gen_id("run_")
        conn.execute(
            "INSERT INTO runs (id, topic, max_rounds) VALUES (?,?,?)",
            (run_id, topic, max_rounds)
        )
        conn.commit()
    else:
        # V5.0: Run may exist in API's table but not engine's table
        # Try update first, if no rows affected, insert
        existing = conn.execute("SELECT id FROM runs WHERE id = ?", (run_id,)).fetchone()
        if existing:
            conn.execute("UPDATE runs SET status='running' WHERE id=?", (run_id,))
        else:
            conn.execute(
                "INSERT INTO runs (id, topic, max_rounds, status) VALUES (?,?,?,?)",
                (run_id, topic, max_rounds, 'running')
            )
        conn.commit()

    print(f"\n{'#'*70}")
    print(f"#  五行飞轮 2.0 — Iterative × Verified × 相生相克")
    print(f"#  Run: {run_id}")
    print(f"#  Topic: {topic}")
    print(f"#  Max rounds: {max_rounds}")
    print(f"#  Interactive: {interactive}")
    print(f"{'#'*70}")

    # --- Engram: retrieve prior runs ---
    prior_context = retrieve_prior(conn, topic)
    if prior_context["found"]:
        n = len(prior_context["prior_runs"])
        topics = [r["topic"] for r in prior_context["prior_runs"]]
        print(f"\n  🧠 Engram: {n} prior run(s) found")
        for r in prior_context["prior_runs"]:
            print(f"     → {r['topic']} (sim:{r['similarity']}, score:{r['score']})")
    else:
        print(f"\n  🧠 Engram: no prior runs matched (cold start)")

    all_results = []
    final_exit_reason = "completed"  # v7.0 hard exit tracking
    residuals = ""
    seeds = topic  # First round uses topic as seed

    # --- AMP-003: Amplifier injection (before qinglong) ---
    amplified_context = None
    if HAS_AMPLIFIER and AMPLIFIER_ENABLED:
        print("\n  🔊 Amplifier: expanding topic into 3+1 dimensions...")
        try:
            amplified_context = pre_amplify(topic, call_llm)
            if amplified_context.get("amplified"):
                amp_seeds = f"""[放大器校准信号]

**原始主题：** {topic}

**意图边界（intent）：** {amplified_context['intent']}

**对象结构（object）：** {amplified_context['object']}

**约束与风险（constraint）：** {amplified_context['constraint']}

**未覆盖维度（unknown）：** {amplified_context['unknown']}

请基于以上四个方向的校准信号生成种子假设。同时保留20%的自由度——如果你认为上述校准遗漏了重要方向，可以生成1-2个完全基于原始输入的"野生种子"。

---
原始主题: {topic}"""
                seeds = amp_seeds
                print(f"  ✅ Amplifier: intent={len(amplified_context['intent'])}c, "
                      f"object={len(amplified_context['object'])}c, "
                      f"constraint={len(amplified_context['constraint'])}c, "
                      f"unknown={len(amplified_context['unknown'])}c")
            else:
                print("  ⚠️ Amplifier: LLM call failed, using raw input")
        except Exception as amp_err:
            print(f"  ⚠️ Amplifier error: {amp_err}, using raw input")
    elif not HAS_AMPLIFIER:
        print("\n  ℹ️ Amplifier: not installed (amplifier.py missing)")
    else:
        print("\n  ℹ️ Amplifier: disabled (AMPLIFIER_ENABLED=false)")
    
    # V9.0: Trading mode - use module-level flag (set by API before calling)
    if _TRADING_DOMAIN and HAS_TRADING:
        import re as _re
        ts_match = _re.search(r'(\d{6}\.[A-Z]{2})', topic)
        if ts_match:
            ts_code = ts_match.group(1)
            try:
                trading_data, _ = build_trading_seed(ts_code)
                seeds = f"{topic}\n\n{trading_data}"
                print(f"  📊 Trading data injected for {ts_code} ({len(trading_data)} chars)")
            except Exception as e:
                print(f"  ⚠️ Trading data fetch failed: {e}")

    prev_round_ke = {}
    # -- V6.0: CHECKPOINT & RESUME --
    _existing_rounds = conn.execute(
        "SELECT r.round_num, l.residuals, l.overall_score, l.notes, r.id as round_id "
        "FROM rounds r LEFT JOIN ledger l ON r.id = l.round_id AND l.run_id = r.run_id "
        "WHERE r.run_id = ? AND r.status = 'done' "
        "ORDER BY r.round_num",
        (run_id,)
    ).fetchall()
    
    _start_round = 1
    if _existing_rounds:
        for _er in _existing_rounds:
            _rnum = _er["round_num"] if isinstance(_er, dict) else _er[0]
            _res = (_er["residuals"] if isinstance(_er, dict) else _er[1]) or ""
            _score = (_er["overall_score"] if isinstance(_er, dict) else _er[2]) or 0.5
            
            _round_entry = {
                "round": _rnum,
                "verification": {"overall": _score, "verdict": "continue"},
                "residuals_preview": _res[:500],
                "kunpeng": {},
            }
            all_results.append(_round_entry)
            residuals = _res
            
            try:
                _parsed = parse_json_safe(_res)
                _next_seeds = _parsed.get("next_seeds", [])
                if _next_seeds:
                    seeds = "原始主题: " + topic + "\n\n新种子（来自上轮残差）:\n" + "\n".join(["- " + s.get("title", str(s)) for s in _next_seeds])
                else:
                    seeds = "原始主题: " + topic + "\n\n上轮残差:\n" + _res[:2000]
            except Exception:
                seeds = "原始主题: " + topic + "\n\n上轮残差:\n" + _res[:2000]
            
            _cached_round_id = _er["round_id"] if isinstance(_er, dict) else _er[4]
            if _cached_round_id:
                _cached_elems = conn.execute(
                    "SELECT element, output_text FROM elements WHERE round_id = ?",
                    (_cached_round_id,)
                ).fetchall()
                for _ce in _cached_elems:
                    _ce_elem = _ce["element"] if isinstance(_ce, dict) else _ce[0]
                    _ce_text = (_ce["output_text"] if isinstance(_ce, dict) else _ce[1]) or ""
                    try:
                        _ce_parsed = json.loads(_ce_text.strip().strip("`").replace("```json","").replace("```",""))
                        for _t in ["qinglong","zhuque","diting","baihu","xuanwu"]:
                            _k = f"ke_signal_to_{_t}"
                            if _k in _ce_parsed and _ce_parsed[_k]:
                                prev_round_ke[f"{_ce_elem}_to_{_t}"] = _ce_parsed[_k]
                    except Exception:
                        pass
        
        _start_round = max(_er["round_num"] if isinstance(_er, dict) else _er[0] for _er in _existing_rounds) + 1
        if _start_round <= max_rounds:
            print(f"\n  \U0001f504 RESUMING from round {_start_round} ({len(_existing_rounds)} rounds cached)")
            print(f"     Last cached score: {all_results[-1]['verification']['overall']:.2f}")
        else:
            print(f"\n  \u2705 All {max_rounds} rounds already complete, returning cached results")
    # -- END V6.0 CHECKPOINT --
    for round_num in range(_start_round, max_rounds + 1):
        # 游离态 interface: ask for human input or read from file
        observer_injection = ""
        if round_num > 1:
            if inject_file:
                # Read injection from file
                try:
                    inject_path = Path(inject_file)
                    if inject_path.exists():
                        content = inject_path.read_text(encoding="utf-8").strip()
                        if content:
                            observer_injection = content
                            print(f"\n  🌙 游离态注入 (from file): {content[:80]}...")
                except Exception as e:
                    print(f"  ⚠️ inject-file read error: {e}")
            elif interactive:
                print(f"\n{'~'*50}")
                print(f"  🌙 游离态接口 (Round {round_num})")
                print(f"  输入概念/方向/纠正，或直接回车继续：")
                try:
                    user_input = input("  > ").strip()
                    if user_input:
                        observer_injection = user_input
                        print(f"  ✅ 注入: {user_input[:80]}...")
                except (EOFError, KeyboardInterrupt):
                    pass
                print(f"{'~'*50}")

        # V6.0: Progress - round starting
        if progress_callback:
            try:
                progress_callback(round_num=round_num, max_rounds=max_rounds, phase="round_start")
            except: pass

        # Run one round (pass prior_context for R1 Engram injection)
        result_tuple = run_round(
            conn, run_id, topic, round_num, prev_round_ke=prev_round_ke,
            seeds=seeds, residuals=residuals,
            observer_injection=observer_injection,
            prior_context=prior_context,
            edge_mode=edge_mode
        )
        # V8.5: unpack with backward compat (3 or 4 values)
        if len(result_tuple) == 4:
            element_outputs, verification, new_residuals, kunpeng = result_tuple
        else:
            element_outputs, verification, new_residuals = result_tuple
            kunpeng = {}

        prev_round_ke = element_outputs.get("_ke_signals", {})
        round_entry = {
            "round": round_num,
            "verification": verification,
            "residuals_preview": new_residuals[:500],
            "kunpeng": kunpeng,  # V8.5: 鲲潜/鹏举/合流 data
        }
        # AMP-004: Store amplified_context in round 1 for downstream reporting
        if round_num == 1 and amplified_context:
            round_entry["amplified_context"] = amplified_context
        all_results.append(round_entry)

        # Check stopping conditions
        verdict = verification.get("verdict", "continue")
        overall = verification.get("overall", 0.5)


        # V6.0: Progress callback
        if progress_callback:
            try:
                progress_callback(round_num=round_num, max_rounds=max_rounds, score=overall, verdict=verdict, phase="round_complete")
            except Exception as _pcb_err:
                print(f"  [progress] callback error: {_pcb_err}")
        if verdict == "converged":
            final_exit_reason = "converged"
            print(f"\n  🎯 CONVERGED at round {round_num} (score: {overall:.2f}) — hard exit, no resume")
            break

        if verdict == "degrading" and round_num >= 2:
            scores = [r["verification"].get("overall", 0.5) for r in all_results]
            if len(scores) >= 2 and scores[-1] < scores[-2]:
                final_exit_reason = "degrading"
                print(f"\n  📉 DEGRADING at round {round_num} — needs external input")
                if not interactive:
                    break
                # In interactive mode, continue (human might inject)

        # Prepare next round
        residuals = new_residuals
        
        # V14.0: 谛听 Auto-Fetch — auto-fill knowledge gaps before next round
        _autofetch_injection = ""
        try:
            _kp_data = kunpeng if isinstance(kunpeng, dict) else {}
            _gaps = _kp_data.get("data_gaps", [])
            if not _gaps:
                # Also check diting's output for gaps
                _diting_out = element_outputs.get("diting", "")
                try:
                    _diting_parsed = parse_json_safe(_diting_out) if isinstance(_diting_out, str) else _diting_out
                    _gaps = _diting_parsed.get("data_gaps", _diting_parsed.get("missing_data", []))
                except: pass
            if _gaps:
                _autofetch_injection = _autofetch_for_gaps(_gaps, topic)
        except Exception as _af_err:
            print(f"  [Auto-Fetch] Error (non-fatal): {_af_err}")
        # Next round seeds = xuanwu's next_seeds + topic context
        try:
            parsed = parse_json_safe(new_residuals)
            next_seeds = parsed.get("next_seeds", [])
            if next_seeds:
                seeds = f"原始主题: {topic}\n\n新种子（来自上轮残差）:\n" + \
                        "\n".join([f"- {s.get('title', s)}" for s in next_seeds])
            else:
                seeds = f"原始主题: {topic}\n\n上轮残差:\n{residuals[:8000]}"

            # V11.0: Inject conflict seeds from previous round
            _prev_conflict_seeds = element_outputs.get("_conflict_seeds", "")
            if _prev_conflict_seeds:
                seeds += f"\n\n[冲突驱动种子]\n{_prev_conflict_seeds}"
                print(f"    [conflict] Injected conflict seeds into R{round_num + 1}")
            
            # V14.0: Append auto-fetched data to seeds
            if _autofetch_injection:
                seeds += _autofetch_injection
                print(f"    [auto-fetch] Injected {len(_autofetch_injection)} chars into R{round_num + 1}")
        except Exception:
            seeds = f"原始主题: {topic}\n\n上轮残差:\n{residuals[:8000]}"

    # --- Final Summary ---
    # V13.0: NPT Validator — final run validation before completion
    _npt_data = None
    if _npt_validator and all_results:
        try:
            # Build validation input from last round's data
            _last_round = all_results[-1]
            _npt_input = {
                "element_outputs": element_outputs if 'element_outputs' in dir() else {},
                "kunpeng": _last_round.get("kunpeng", {}),
                "rounds": all_results,
            }
            _npt_data = _npt_validator.validate_run(_npt_input)
            _npt_violations = _npt_data.get("violations", [])
            if _npt_violations:
                print(f"  [NPT] {len(_npt_violations)} violation(s) detected:")
                for _v in _npt_violations[:5]:
                    print(f"    ⚠ [{_v.get('axiom', '?')}] {_v.get('detail', 'unknown')[:100]}")
            else:
                print(f"  [NPT] All axioms satisfied ✅")
            # Store NPT result in last round entry for downstream access
            _last_round["npt_validation"] = _npt_data
        except Exception as _npt_err:
            print(f"  [NPT] Validation error (non-fatal): {_npt_err}")

    # Hard exit: set status based on how we exited the loop
    if final_exit_reason == "converged":
        run_status = "converged"  # hard exit, no resume allowed
    elif final_exit_reason == "degrading":
        run_status = "degraded"   # quality degraded, resume may help with external input
    else:
        run_status = "done"       # normal completion (max_rounds or other)

    conn.execute(
        "UPDATE runs SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (run_status, run_id)
    )
    conn.commit()

    print(f"\n{'#'*70}")
    print(f"#  FLYWHEEL 2.0 COMPLETE")
    print(f"#  Run: {run_id}")
    print(f"#  Rounds: {len(all_results)}")
    print(f"#")

    for r in all_results:
        v = r["verification"]
        s = v.get("overall", "?")
        verdict = v.get("verdict", "?")
        notes = v.get("notes", "")
        bar = "█" * int(float(s) * 10) if isinstance(s, (int, float)) else "?"
        print(f"#  R{r['round']}: {bar} {s} [{verdict}] {notes[:50]}")

    print(f"#")
    print(f"#  Database: PostgreSQL ({PG_DSN})" if USE_PG else f"#  Database: {DB_PATH}")
    print(f"{'#'*70}")

    conn.close()
    return all_results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="五行飞轮 Engine v2.0")
    parser.add_argument("topic", nargs="?", default="SiC功率半导体在新能源汽车中的市场机会与技术壁垒分析",
                        help="Analysis topic")
    parser.add_argument("--rounds", type=int, default=3, help="Max rounds (default: 3)")
    parser.add_argument("--interactive", action="store_true", help="Enable 游离态 interface")
    parser.add_argument("--inject-file", type=str, default=None,
                        help="Read observer injection from file instead of stdin")
    args = parser.parse_args()

    run_flywheel(args.topic, max_rounds=args.rounds, interactive=args.interactive,
                 inject_file=args.inject_file)


print(f"[engine_v2] Loaded with enrich_xuanwu={'enrich_xuanwu' in dir()}")