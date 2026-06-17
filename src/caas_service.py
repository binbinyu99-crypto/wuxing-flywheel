# -*- coding: utf-8 -*-
"""
caas_service.py v1.1.0 鈥?CaaS User/Quota/Invite System
Phase 0: Registration, Invite Codes, Quota Management, Task Routing
Runs as FastAPI app on port 19107
2026-05-06
"""
import json, time, uuid, hashlib, os
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="CaaS Service", version="1.0.0")

# Auth router disabled (T5-001: using inline endpoints instead)
DB_DSN = "dbname=skycetus user=postgres host=localhost"

def get_db():
    conn = psycopg2.connect(DB_DSN)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Create CaaS tables if not exist."""
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()
    
    # Users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS caas_users (
        user_id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT,
        invite_code_used TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        status TEXT DEFAULT 'active',
        total_runs INTEGER DEFAULT 0,
        analyst_level TEXT DEFAULT 'user',
        analyst_commission_rate REAL DEFAULT 0.0
    )
    """)
    
    # Invite codes
    cur.execute("""
    CREATE TABLE IF NOT EXISTS caas_invite_codes (
        code TEXT PRIMARY KEY,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        used_by TEXT,
        used_at TIMESTAMP,
        status TEXT DEFAULT 'active',
        coupon_value REAL DEFAULT 0.0,
        coupon_type TEXT DEFAULT 'none'
    )
    """)
    
    # Quotas & transactions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS caas_user_quotas (
        user_id TEXT PRIMARY KEY REFERENCES caas_users(user_id),
        standard_balance INTEGER DEFAULT 0,
        flagship_balance INTEGER DEFAULT 0,
        total_purchased INTEGER DEFAULT 0,
        total_spent REAL DEFAULT 0.0,
        last_purchase_at TIMESTAMP,
        CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES caas_users(user_id)
    )
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS caas_transactions (
        txn_id TEXT PRIMARY KEY,
        user_id TEXT REFERENCES caas_users(user_id),
        txn_type TEXT NOT NULL,
        model_tier TEXT,
        amount REAL DEFAULT 0.0,
        quantity INTEGER DEFAULT 1,
        description TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """)
    
    # Analyst tracking
    cur.execute("""
    CREATE TABLE IF NOT EXISTS caas_analysts (
        user_id TEXT PRIMARY KEY REFERENCES caas_users(user_id),
        level TEXT DEFAULT 'analyst',
        commission_rate REAL DEFAULT 0.30,
        total_assignments INTEGER DEFAULT 0,
        avg_rating REAL DEFAULT 0.0,
        domains TEXT[] DEFAULT '{}',
        promoted_at TIMESTAMP DEFAULT NOW()
    )
    """)
    
    # Expert residuals (Robin's decision T25)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS caas_expert_residuals (
        residual_id TEXT PRIMARY KEY,
        run_id TEXT,
        expert_user_id TEXT,
        interpretation TEXT,
        residual_data JSONB,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """)
    
    # Lux ledger (AI incentive only, no real economic value)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS caas_lux_ledger (
        entry_id TEXT PRIMARY KEY,
        user_id TEXT,
        amount REAL,
        reason TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("[CaaS] Database tables initialized")


# ===== Models =====
class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    invite_code: str


class LoginRequest(BaseModel):
    username: str
    password: str

class PurchaseRequest(BaseModel):
    user_id: str
    model_tier: str  # "standard" or "flagship"
    package: str  # "single", "light", "standard", "professional"
    period: Optional[str] = "single"  # "single", "monthly", "quarterly", "yearly"

class SubmitAnalysisRequest(BaseModel):
    user_id: str
    topic: str
    model_tier: str = "standard"
    deep_mode: bool = True

class InviteGenerateRequest(BaseModel):
    created_by: str
    count: int = 1
    coupon_value: float = 0.0
    coupon_type: str = "none"  # "none", "discount", "free_run"


# ===== Pricing =====
PRICING = {
    "standard": {
        "unit_price": 5.0,
        "packages": {
            "single": {"runs": 1, "price": 5.0},
            "light": {"runs": 30, "price": 150.0, "monthly": 120.0, "quarterly": 324.0, "yearly": 1152.0},
            "standard": {"runs": 100, "price": 500.0, "monthly": 380.0, "quarterly": 1026.0, "yearly": 3648.0},
            "professional": {"runs": 300, "price": 1500.0, "monthly": 1080.0, "quarterly": 2916.0, "yearly": 10368.0},
        }
    },
    "flagship": {
        "unit_price": 49.0,
        "packages": {
            "single": {"runs": 1, "price": 49.0},
            "light": {"runs": 10, "price": 490.0, "monthly": 392.0, "quarterly": 1058.0, "yearly": 3763.0},
            "standard": {"runs": 30, "price": 1470.0, "monthly": 1117.0, "quarterly": 3016.0, "yearly": 10722.0},
            "professional": {"runs": 100, "price": 4900.0, "monthly": 3528.0, "quarterly": 9526.0, "yearly": 33868.0},
        }
    }
}

ANALYST_TIERS = {
    "analyst": {"min_runs": 10, "commission": 0.30},
    "E1": {"min_runs": 30, "min_assignments": 30, "min_rating": 4.0, "min_domains": 1, "commission": 0.40},
    "E2": {"min_runs": 100, "min_assignments": 100, "min_rating": 4.5, "min_domains": 2, "commission": 0.50},
    "E3": {"min_runs": 300, "min_assignments": 300, "min_rating": 4.8, "min_domains": 3, "commission": 0.60},
}


# ===== API Routes =====

@app.on_event("startup")
async def startup():
    init_db()

@app.get("/health")
async def health():
    return {"status": "ok", "service": "CaaS", "version": "1.0.0"}

# --- Registration ---
@app.post("/caas/register")
async def register(req: RegisterRequest):
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Verify invite code
    cur.execute("SELECT * FROM caas_invite_codes WHERE code = %s AND status = 'active'", (req.invite_code,))
    code = cur.fetchone()
    if not code:
        conn.close()
        raise HTTPException(400, "Invalid or used invite code")
    
    # Create user
    user_id = f"caas-{uuid.uuid4().hex[:12]}"
    try:
        # Hash password
        import hashlib, secrets
        salt = secrets.token_hex(16)
        pw_hash = hashlib.sha256((req.password + salt).encode()).hexdigest()
        cur.execute(
            "INSERT INTO caas_users (user_id, username, email, invite_code_used, password_hash, salt) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, req.username, req.email, req.invite_code, pw_hash, salt)
        )
        # Mark code as used
        cur.execute(
            "UPDATE caas_invite_codes SET used_by = %s, used_at = NOW(), status = 'used' WHERE code = %s",
            (user_id, req.invite_code)
        )
        # Init quota
        cur.execute(
            "INSERT INTO caas_user_quotas (user_id) VALUES (%s)", (user_id,)
        )
        # Apply coupon if any
        if code.get("coupon_type") == "free_run" and code.get("coupon_value", 0) > 0:
            runs = int(code["coupon_value"])
            cur.execute(
                "UPDATE caas_user_quotas SET standard_balance = standard_balance + %s WHERE user_id = %s",
                (runs, user_id)
            )
        
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        conn.close()
        raise HTTPException(400, "Username already exists")
    
    conn.close()
    return {"user_id": user_id, "username": req.username, "status": "registered"}

# --- Invite Codes ---
@app.post("/caas/invite/generate")
async def generate_invites(req: InviteGenerateRequest):
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()
    
    codes = []
    for _ in range(min(req.count, 20)):  # Max 20 at a time
        code = f"SKY-{uuid.uuid4().hex[:8].upper()}"
        cur.execute(
            "INSERT INTO caas_invite_codes (code, created_by, coupon_value, coupon_type) VALUES (%s, %s, %s, %s)",
            (code, req.created_by, req.coupon_value, req.coupon_type)
        )
        codes.append(code)
    
    conn.commit()
    conn.close()
    return {"codes": codes, "count": len(codes)}

@app.get("/caas/invite/list")
async def list_invites(created_by: str = None):
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if created_by:
        cur.execute("SELECT * FROM caas_invite_codes WHERE created_by = %s ORDER BY created_at DESC", (created_by,))
    else:
        cur.execute("SELECT * FROM caas_invite_codes ORDER BY created_at DESC LIMIT 100")
    
    codes = cur.fetchall()
    conn.close()
    # Convert datetime to string
    for c in codes:
        for k in ["created_at", "used_at"]:
            if c.get(k):
                c[k] = str(c[k])
    return {"codes": codes}

# --- Quota ---
@app.get("/caas/quota/{user_id}")
async def get_quota(user_id: str):
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM caas_user_quotas WHERE user_id = %s", (user_id,))
    quota = cur.fetchone()
    conn.close()
    
    if not quota:
        raise HTTPException(404, "User not found")
    
    for k in ["last_purchase_at"]:
        if quota.get(k):
            quota[k] = str(quota[k])
    return quota

@app.post("/caas/purchase")
async def purchase(req: PurchaseRequest):
    tier = PRICING.get(req.model_tier)
    if not tier:
        raise HTTPException(400, f"Invalid model tier: {req.model_tier}")
    
    pkg = tier["packages"].get(req.package)
    if not pkg:
        raise HTTPException(400, f"Invalid package: {req.package}")
    
    # Calculate price based on period
    if req.period == "single" or req.period not in pkg:
        price = pkg["price"]
    else:
        price = pkg.get(req.period, pkg["price"])
    
    runs = pkg["runs"]
    balance_col = "standard_balance" if req.model_tier == "standard" else "flagship_balance"
    
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()
    
    txn_id = f"txn-{uuid.uuid4().hex[:12]}"
    
    try:
        # Add quota
        cur.execute(
            f"UPDATE caas_user_quotas SET {balance_col} = {balance_col} + %s, total_purchased = total_purchased + %s, total_spent = total_spent + %s, last_purchase_at = NOW() WHERE user_id = %s",
            (runs, runs, price, req.user_id)
        )
        if cur.rowcount == 0:
            conn.rollback()
            conn.close()
            raise HTTPException(404, "User not found")
        
        # Record transaction
        cur.execute(
            "INSERT INTO caas_transactions (txn_id, user_id, txn_type, model_tier, amount, quantity, description) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (txn_id, req.user_id, "purchase", req.model_tier, price, runs, f"{req.package} {req.period}")
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(500, str(e))
    
    conn.close()
    return {"txn_id": txn_id, "runs_added": runs, "price": price, "model_tier": req.model_tier}

# --- Analysis Submission ---
@app.post("/caas/submit")
async def submit_analysis(req: SubmitAnalysisRequest):
    balance_col = "standard_balance" if req.model_tier == "standard" else "flagship_balance"
    
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check quota
    cur.execute(f"SELECT {balance_col} as balance FROM caas_user_quotas WHERE user_id = %s", (req.user_id,))
    quota = cur.fetchone()
    if not quota:
        conn.close()
        raise HTTPException(404, "User not found")
    if quota["balance"] <= 0:
        conn.close()
        raise HTTPException(402, f"Insufficient {req.model_tier} balance. Current: {quota['balance']}")
    
    # Deduct 1 run
    cur.execute(
        f"UPDATE caas_user_quotas SET {balance_col} = {balance_col} - 1 WHERE user_id = %s AND {balance_col} > 0",
        (req.user_id,)
    )
    
    # Update user total runs
    cur.execute(
        "UPDATE caas_users SET total_runs = total_runs + 1 WHERE user_id = %s",
        (req.user_id,)
    )
    
    # Check auto-promotion to analyst (10 runs)
    cur.execute("SELECT total_runs, analyst_level FROM caas_users WHERE user_id = %s", (req.user_id,))
    user = cur.fetchone()
    if user and user["total_runs"] >= 10 and user["analyst_level"] == "user":
        cur.execute(
            "UPDATE caas_users SET analyst_level = 'analyst', analyst_commission_rate = 0.30 WHERE user_id = %s",
            (req.user_id,)
        )
        cur.execute(
            "INSERT INTO caas_analysts (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
            (req.user_id,)
        )
    
    # Record transaction
    txn_id = f"txn-{uuid.uuid4().hex[:12]}"
    cur.execute(
        "INSERT INTO caas_transactions (txn_id, user_id, txn_type, model_tier, amount, quantity, description) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (txn_id, req.user_id, "consume", req.model_tier, 0, 1, f"Analysis: {req.topic[:100]}")
    )
    
    conn.commit()
    conn.close()
    
    # Queue for delivery worker
    caas_run_id = f"caas-run-{uuid.uuid4().hex[:12]}"
    conn2 = psycopg2.connect(DB_DSN)
    cur2 = conn2.cursor()
    cur2.execute(
        "INSERT INTO caas_runs (caas_run_id, user_id, topic, model_tier, status) VALUES (%s, %s, %s, %s, 'queued')",
        (caas_run_id, req.user_id, req.topic, req.model_tier)
    )
    conn2.commit()
    conn2.close()
    
    promoted = user and user["total_runs"] >= 10 and user["analyst_level"] == "user"
    return {
        "status": "queued",
        "caas_run_id": caas_run_id,
        "txn_id": txn_id,
        "model_tier": req.model_tier,
        "remaining_balance": max(0, quota["balance"] - 1),
        "topic": req.topic[:200],
        "promoted": promoted
    }

# --- Status ---
@app.get("/caas/status")
async def caas_status():
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT COUNT(*) as total FROM caas_users")
    users = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM caas_invite_codes WHERE status = 'active'")
    active_codes = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM caas_analysts")
    analysts = cur.fetchone()["total"]
    cur.execute("SELECT COALESCE(SUM(total_spent), 0) as revenue FROM caas_user_quotas")
    revenue = cur.fetchone()["revenue"]
    
    conn.close()
    return {
        "users": users,
        "active_invite_codes": active_codes,
        "analysts": analysts,
        "total_revenue": float(revenue),
        "version": "1.0.0"
    }

# --- Runs ---
@app.get("/caas/runs/{user_id}")
async def get_runs(user_id: str, limit: int = 20):
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM caas_runs WHERE user_id = %s ORDER BY submitted_at DESC LIMIT %s",
        (user_id, limit)
    )
    runs = cur.fetchall()
    conn.close()
    for r in runs:
        for k in ["submitted_at", "started_at", "completed_at"]:
            if r.get(k):
                r[k] = str(r[k])
    return {"runs": runs}

@app.get("/caas/run/{caas_run_id}")
async def get_run(caas_run_id: str):
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM caas_runs WHERE caas_run_id = %s", (caas_run_id,))
    run = cur.fetchone()
    conn.close()
    if not run:
        raise HTTPException(404, "Run not found")
    for k in ["submitted_at", "started_at", "completed_at"]:
        if run.get(k):
            run[k] = str(run[k])
    return run

# --- Expert Assignment (CaaS-006) ---
class AssignExpertRequest(BaseModel):
    caas_run_id: str
    expert_user_id: str
    client_user_id: str
    consultation_type: str = "standard"

class CompleteConsultRequest(BaseModel):
    assignment_id: str
    rating: Optional[float] = None
    feedback: Optional[str] = None

@app.post("/caas/expert/assign")
async def expert_assign(req: AssignExpertRequest):
    from caas_expert import assign_expert
    return assign_expert(req.caas_run_id, req.expert_user_id, req.client_user_id, req.consultation_type)

@app.post("/caas/expert/complete")
async def expert_complete(req: CompleteConsultRequest):
    from caas_expert import complete_consultation
    return complete_consultation(req.assignment_id, req.rating, req.feedback)

# --- Residual Collection (CaaS-007, Robin T25) ---
class CollectResidualRequest(BaseModel):
    run_id: str
    caas_run_id: str = ""
    expert_user_id: str
    interpretation: str
    residual_type: str = "gap"
    severity: float = 0.5
    domain: Optional[str] = None
    actionable: bool = False

class ResidualFeedbackRequest(BaseModel):
    residual_id: str
    expert_user_id: str
    content: str
    confidence: float = 0.5

@app.post("/caas/residual/collect")
async def residual_collect(req: CollectResidualRequest):
    from caas_expert import collect_residual
    return collect_residual(req.run_id, req.caas_run_id, req.expert_user_id,
                           req.interpretation, req.residual_type, req.severity,
                           req.domain, req.actionable)

@app.post("/caas/residual/feedback")
async def residual_feedback(req: ResidualFeedbackRequest):
    from caas_expert import add_residual_feedback
    return add_residual_feedback(req.residual_id, req.expert_user_id, req.content, req.confidence)

@app.get("/caas/residuals/{run_id}")
async def get_residuals(run_id: str):
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM caas_expert_residuals WHERE run_id = %s OR caas_run_id = %s ORDER BY created_at", (run_id, run_id))
    residuals = cur.fetchall()
    conn.close()
    for r in residuals:
        if r.get("created_at"): r["created_at"] = str(r["created_at"])
    return {"residuals": residuals}

# --- Verticals (CaaS-010/011) ---
@app.get("/caas/verticals")
async def verticals_list():
    from caas_verticals import list_verticals as lv
    return {"verticals": lv()}

@app.get("/caas/vertical/{vertical_id}")
async def vertical_get(vertical_id: str):
    from caas_verticals import get_vertical as gv
    v = gv(vertical_id)
    if not v:
        raise HTTPException(404, "Vertical not found")
    if v.get("created_at"): v["created_at"] = str(v["created_at"])
    return v

# --- Lux Economy (CaaS-009) ---
class LuxAwardRequest(BaseModel):
    user_id: str
    amount: float
    reason: str

@app.post("/caas/lux/award")
async def lux_award(req: LuxAwardRequest):
    entry_id = f"lux-{uuid.uuid4().hex[:12]}"
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO caas_lux_ledger (entry_id, user_id, amount, reason) VALUES (%s, %s, %s, %s)",
        (entry_id, req.user_id, req.amount, req.reason)
    )
    conn.commit()
    conn.close()
    return {"entry_id": entry_id, "amount": req.amount}

@app.get("/caas/lux/{user_id}")
async def lux_balance(user_id: str):
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT COALESCE(SUM(amount), 0) as balance FROM caas_lux_ledger WHERE user_id = %s",
        (user_id,)
    )
    balance = cur.fetchone()["balance"]
    cur.execute(
        "SELECT * FROM caas_lux_ledger WHERE user_id = %s ORDER BY created_at DESC LIMIT 20",
        (user_id,)
    )
    history = cur.fetchall()
    conn.close()
    for h in history:
        if h.get("created_at"): h["created_at"] = str(h["created_at"])
    return {"balance": float(balance), "history": history}

# --- Engram Query (CaaS-008) ---
@app.get("/caas/engram/query")
async def engram_query(domain: str = None, keyword: str = None, limit: int = 10):
    from caas_engram_bridge import query_engram
    return query_engram(domain, keyword, limit)

@app.post("/caas/engram/reindex")
async def engram_reindex():
    from caas_engram_bridge import index_all_pages, bridge_residuals
    web = index_all_pages()
    res_count = bridge_residuals()
    return {"web_indexing": web, "residuals_bridged": res_count}

# --- User Info ---
@app.get("/caas/user/{user_id}")
async def get_user(user_id: str):
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM caas_users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(404, "User not found")
    
    cur.execute("SELECT * FROM caas_user_quotas WHERE user_id = %s", (user_id,))
    quota = cur.fetchone()
    
    cur.execute("SELECT * FROM caas_analysts WHERE user_id = %s", (user_id,))
    analyst = cur.fetchone()
    
    conn.close()
    
    # Serialize datetimes
    for obj in [user, quota, analyst]:
        if obj:
            for k, v in list(obj.items()):
                if isinstance(v, datetime):
                    obj[k] = str(v)
    
    return {"user": user, "quota": quota, "analyst": analyst}





# === Auth Endpoints (T5-001) ===

@app.post("/caas/auth/login")
async def auth_login(req: LoginRequest):
    """Login and get JWT token."""
    import hashlib, jwt, datetime
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT user_id, username, password_hash, salt, is_active FROM caas_users WHERE username = %s", (req.username,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(401, "Invalid credentials")
        if not user.get('is_active', True) == False:
            pass  # active
        pw_check = hashlib.sha256((req.password + (user['salt'] or '')).encode()).hexdigest()
        if pw_check != user.get('password_hash', ''):
            raise HTTPException(401, "Invalid credentials")
        # Update last_login
        cur.execute("UPDATE caas_users SET last_login = NOW() WHERE user_id = %s", (user['user_id'],))
        conn.commit()
        # Generate JWT
        token = jwt.encode({
            'user_id': user['user_id'],
            'username': user['username'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
        }, 'skycetus-jwt-secret-2026', algorithm='HS256')
        return {"token": token, "user_id": user['user_id'], "username": user['username']}
    finally:
        conn.close()

@app.get("/caas/auth/me")
async def auth_me(request: Request):
    """Get current user info from JWT token."""
    import jwt
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        raise HTTPException(401, "Missing token")
    try:
        payload = jwt.decode(auth[7:], 'skycetus-jwt-secret-2026', algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT user_id, username, email, status, total_runs, analyst_level, created_at, last_login FROM caas_users WHERE user_id = %s", (payload['user_id'],))
        user = cur.fetchone()
        if not user:
            raise HTTPException(404, "User not found")
        # Get quota info
        try:
            cur.execute("SELECT daily_limit, used_today FROM caas_quotas WHERE user_id = %s", (payload['user_id'],))
            quota = cur.fetchone()
        except Exception:
            quota = None
        return {
            "user": {k: str(v) if hasattr(v, 'isoformat') else v for k, v in dict(user).items()},
            "quota": dict(quota) if quota else {"daily_limit": 3, "used_today": 0}
        }
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn, threading
    init_db()
    
    # Init delivery tables
    from caas_delivery import init_delivery_tables, delivery_loop
    from caas_expert import init_expert_tables
    from caas_verticals import init_vertical_tables, seed_verticals
    init_delivery_tables()
    init_expert_tables()
    init_vertical_tables()
    seed_verticals()
    
    # Start delivery worker in background
    worker = threading.Thread(target=delivery_loop, daemon=True)
    worker.start()
    print("[CaaS] Delivery worker started")
    
    uvicorn.run(app, host="0.0.0.0", port=19107)

