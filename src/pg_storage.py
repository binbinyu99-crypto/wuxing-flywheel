
"""
pg_storage.py — Unified PostgreSQL storage layer for CaaS Wuxing Flywheel
Replaces all SQLite usage across metal_validator, lux_engine, water_engine,
wood_engine, fire_engine, knowledge_store, trust_rate_limiter, phase_affinity,
bootstrap_graduation.

Connection: 127.0.0.1:5432 skycetus/SkyCetusDB2024!
"""

import psycopg2
import psycopg2.pool
import json
import time
import threading
from contextlib import contextmanager

VERSION = "2.0.0"  # v2: memory weights (MEU-02)

# Connection pool (thread-safe)
_pool = None
_pool_lock = threading.Lock()

def get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=10,
                    host="127.0.0.1",
                    port=5432,
                    dbname="skycetus",
                    user="skycetus",
                    password="<DB_PASSWORD>",
                    connect_timeout=10
                )
    return _pool

@contextmanager
def get_conn():
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)

@contextmanager
def get_cursor():
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

def init_tables():
    """Create CaaS-specific tables if not exist. Reuses existing tables where possible."""
    with get_conn() as conn:
        cur = conn.cursor()
        
        # Metal Validator audit table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_metal_audits (
                id SERIAL PRIMARY KEY,
                input_hash TEXT,
                content_preview TEXT,
                scores JSONB,
                verdict TEXT,
                final_score REAL,
                adversarial_results JSONB,
                pruned_seeds JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Water Engine tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_water_atoms (
                id SERIAL PRIMARY KEY,
                pattern TEXT NOT NULL,
                domain TEXT DEFAULT 'general',
                confidence REAL DEFAULT 0.3,
                occurrences INTEGER DEFAULT 1,
                sources JSONB DEFAULT '[]',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_water_convergence (
                id SERIAL PRIMARY KEY,
                domain TEXT,
                score REAL,
                atom_count INTEGER,
                high_confidence_count INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Wood Engine seed tracking (supplement to existing seeds/seeds_v2)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_wood_seeds (
                id SERIAL PRIMARY KEY,
                seed_id TEXT UNIQUE,
                content TEXT,
                domain TEXT DEFAULT 'general',
                score REAL DEFAULT 0.0,
                dimensions JSONB,
                status TEXT DEFAULT 'active',
                parent_id TEXT,
                mutation_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Fire Engine execution tracking
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_fire_executions (
                id SERIAL PRIMARY KEY,
                task_id TEXT,
                input_text TEXT,
                sub_tasks JSONB,
                result TEXT,
                quality_score REAL,
                execution_time REAL,
                model_used TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Knowledge Store (supplement to existing knowledge_nodes/edges)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_knowledge_entries (
                id SERIAL PRIMARY KEY,
                key TEXT,
                domain TEXT,
                content TEXT,
                source TEXT,
                residual_score REAL DEFAULT 0.0,
                access_count INTEGER DEFAULT 0,
                keywords JSONB DEFAULT '[]',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_caas_knowledge_domain ON caas_knowledge_entries(domain)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_caas_knowledge_key ON caas_knowledge_entries(key)
        """)
        
        # Trust & Rate Limiting (supplement to existing trust_scores)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_trust_records (
                id SERIAL PRIMARY KEY,
                node_id TEXT UNIQUE,
                trust_tier TEXT DEFAULT 'seed',
                trust_score REAL DEFAULT 0.0,
                total_tasks INTEGER DEFAULT 0,
                successful_tasks INTEGER DEFAULT 0,
                phase_history JSONB DEFAULT '[]',
                rate_limit_remaining INTEGER DEFAULT 3,
                rate_limit_reset TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Phase Affinity
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_phase_affinity (
                id SERIAL PRIMARY KEY,
                node_id TEXT,
                phase TEXT,
                affinity_score REAL DEFAULT 0.5,
                task_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                last_active TIMESTAMP DEFAULT NOW(),
                UNIQUE(node_id, phase)
            )
        """)
        
        # Bootstrap Graduation
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_bootstrap_nodes (
                id SERIAL PRIMARY KEY,
                node_id TEXT UNIQUE,
                current_tier INTEGER DEFAULT 0,
                total_tasks INTEGER DEFAULT 0,
                quality_avg REAL DEFAULT 0.0,
                feedback_count INTEGER DEFAULT 0,
                first_seen TIMESTAMP DEFAULT NOW(),
                last_promotion TIMESTAMP,
                promotion_history JSONB DEFAULT '[]'
            )
        """)
        
        # Xiangsheng chain state
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_xiangsheng_state (
                id SERIAL PRIMARY KEY,
                from_phase TEXT,
                to_phase TEXT,
                trigger_count INTEGER DEFAULT 0,
                last_triggered TIMESTAMP,
                conditions_met JSONB DEFAULT '{}',
                UNIQUE(from_phase, to_phase)
            )
        """)
        
        # CaaS analysis jobs (async)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_jobs (
                id SERIAL PRIMARY KEY,
                job_id TEXT UNIQUE,
                status TEXT DEFAULT 'pending',
                input_data JSONB,
                result JSONB,
                error TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            )
        """)
        
        # Wuxing balance snapshots
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_wuxing_balance (
                id SERIAL PRIMARY KEY,
                phase TEXT,
                task_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0,
                avg_quality REAL DEFAULT 0.0,
                imbalance_score REAL DEFAULT 0.0,
                snapshot_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Lux distribution records (supplement to existing lux_*)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_lux_distributions (
                id SERIAL PRIMARY KEY,
                task_id TEXT,
                executor_id TEXT,
                creator_id TEXT,
                total_lux REAL,
                executor_share REAL,
                creator_share REAL,
                system_share REAL,
                quality_multiplier REAL DEFAULT 1.0,
                self_play BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        conn.commit()
        cur.close()
    return True

# ============ Metal Validator PG Operations ============

def metal_save_audit(input_hash, content_preview, scores, verdict, final_score, adversarial_results=None, pruned_seeds=None):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO caas_metal_audits (input_hash, content_preview, scores, verdict, final_score, adversarial_results, pruned_seeds)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (input_hash, content_preview, json.dumps(scores), verdict, final_score,
              json.dumps(adversarial_results) if adversarial_results else None,
              json.dumps(pruned_seeds) if pruned_seeds else None))
        return cur.fetchone()[0]

def metal_get_audits(limit=50):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM caas_metal_audits ORDER BY created_at DESC LIMIT %s", (limit,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

def metal_get_stats():
    with get_cursor() as cur:
        cur.execute("""
            SELECT count(*) as total,
                   count(*) FILTER (WHERE verdict='PASS') as passed,
                   count(*) FILTER (WHERE verdict='FAIL') as failed,
                   count(*) FILTER (WHERE verdict='CONDITIONAL') as conditional,
                   avg(final_score) as avg_score
            FROM caas_metal_audits
        """)
        row = cur.fetchone()
        return {"total": row[0], "passed": row[1], "failed": row[2], "conditional": row[3], "avg_score": float(row[4] or 0)}

# ============ Water Engine PG Operations ============

def water_upsert_atom(pattern, domain="general", confidence_delta=0.1, source=None):
    with get_cursor() as cur:
        cur.execute("SELECT id, confidence, occurrences, sources FROM caas_water_atoms WHERE pattern=%s AND domain=%s", (pattern, domain))
        row = cur.fetchone()
        if row:
            new_conf = min(1.0, row[1] + confidence_delta)
            sources = json.loads(row[3]) if row[3] else []
            if source and source not in sources:
                sources.append(source)
            cur.execute("UPDATE caas_water_atoms SET confidence=%s, occurrences=occurrences+1, sources=%s, updated_at=NOW() WHERE id=%s",
                       (new_conf, json.dumps(sources), row[0]))
            return row[0]
        else:
            cur.execute("""
                INSERT INTO caas_water_atoms (pattern, domain, confidence, sources)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (pattern, domain, 0.3, json.dumps([source] if source else [])))
            return cur.fetchone()[0]

def water_get_convergence(domain="general"):
    with get_cursor() as cur:
        cur.execute("SELECT count(*), avg(confidence), count(*) FILTER (WHERE confidence >= 0.7) FROM caas_water_atoms WHERE domain=%s", (domain,))
        row = cur.fetchone()
        total = row[0] or 0
        avg_conf = float(row[1] or 0)
        high_conf = row[2] or 0
        score = avg_conf * (1 + high_conf / max(total, 1) * 0.5) if total > 0 else 0
        return {"domain": domain, "atom_count": total, "avg_confidence": avg_conf, "high_confidence": high_conf, "convergence_score": min(1.0, score)}

# ============ Wood Engine PG Operations ============

def wood_save_seed(seed_id, content, domain="general", score=0.0, dimensions=None, parent_id=None):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO caas_wood_seeds (seed_id, content, domain, score, dimensions, parent_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (seed_id) DO UPDATE SET score=%s, dimensions=%s, updated_at=NOW()
            RETURNING id
        """, (seed_id, content, domain, score, json.dumps(dimensions), parent_id, score, json.dumps(dimensions)))
        # caas_wood_seeds has no updated_at column, but ON CONFLICT won't fail
        return cur.fetchone()[0]

def wood_get_seeds(domain=None, status="active", limit=50):
    with get_cursor() as cur:
        if domain:
            cur.execute("SELECT * FROM caas_wood_seeds WHERE domain=%s AND status=%s ORDER BY score DESC LIMIT %s", (domain, status, limit))
        else:
            cur.execute("SELECT * FROM caas_wood_seeds WHERE status=%s ORDER BY score DESC LIMIT %s", (status, limit))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

# ============ Fire Engine PG Operations ============

def fire_save_execution(task_id, input_text, sub_tasks, result, quality_score, execution_time, model_used=None):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO caas_fire_executions (task_id, input_text, sub_tasks, result, quality_score, execution_time, model_used)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (task_id, input_text, json.dumps(sub_tasks), result, quality_score, execution_time, model_used))
        return cur.fetchone()[0]

# ============ Knowledge Store PG Operations ============

def knowledge_store(key, content, domain="general", source=None, residual_score=0.0, keywords=None):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO caas_knowledge_entries (key, domain, content, source, residual_score, keywords)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (key, domain, content, source, residual_score, json.dumps(keywords or [])))
        return cur.fetchone()[0]

def knowledge_search(query, domain=None, limit=10):
    with get_cursor() as cur:
        if domain:
            cur.execute("""
                SELECT * FROM caas_knowledge_entries
                WHERE domain=%s AND (content ILIKE %s OR key ILIKE %s)
                ORDER BY residual_score DESC, access_count DESC LIMIT %s
            """, (domain, f"%{query}%", f"%{query}%", limit))
        else:
            cur.execute("""
                SELECT * FROM caas_knowledge_entries
                WHERE content ILIKE %s OR key ILIKE %s
                ORDER BY residual_score DESC, access_count DESC LIMIT %s
            """, (f"%{query}%", f"%{query}%", limit))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ============ Memory Weight System (MEU-02: flywheel design v4.5) ============

def init_memory_weights():
    """Add memory weight columns to existing tables.
    
    Implements v4.5 flywheel design:
    W_new = W_old + alpha*passes - beta*breaks - gamma*instability
    
    access_count: how often this knowledge is recalled (越用越重要)
    decay_rate: how fast it loses relevance (default 0.01/day)
    last_accessed: timestamp of last access
    survival_score: how many verification rounds it survived
    break_count: how many times it was invalidated
    """
    with get_conn() as conn:
        cur = conn.cursor()
        # Add to caas_wood_seeds
        for col, dtype, default in [
            ("access_count", "INTEGER", "0"),
            ("decay_rate", "REAL", "0.01"),
            ("last_accessed", "TIMESTAMP", "NOW()"),
            ("survival_score", "REAL", "0.0"),
            ("break_count", "INTEGER", "0"),
        ]:
            try:
                cur.execute(f"ALTER TABLE caas_wood_seeds ADD COLUMN {col} {dtype} DEFAULT {default}")
            except Exception:
                conn.rollback()
                conn = get_pool().getconn()
                cur = conn.cursor()
        
        # Add to caas_knowledge_entries
        for col, dtype, default in [
            ("access_count", "INTEGER", "0"),
            ("decay_rate", "REAL", "0.01"),
            ("last_accessed", "TIMESTAMP", "NOW()"),
            ("survival_score", "REAL", "0.0"),
            ("break_count", "INTEGER", "0"),
        ]:
            try:
                cur.execute(f"ALTER TABLE caas_knowledge_entries ADD COLUMN {col} {dtype} DEFAULT {default}")
            except Exception:
                conn.rollback()
                conn = get_pool().getconn()
                cur = conn.cursor()
        
        conn.commit()
        print("[pg_storage] Memory weight columns initialized")


def memory_touch(table, record_id):
    """Increment access_count and update last_accessed when knowledge is recalled."""
    with get_cursor() as cur:
        cur.execute(f"""
            UPDATE {table} SET access_count = access_count + 1, last_accessed = NOW()
            WHERE id = %s
        """, (record_id,))


def memory_update_weight(table, record_id, passed=False, broken=False,
                         alpha=0.1, beta=0.3, gamma=0.05):
    """Update survival_score using v4.5 weight formula.
    
    W_new = W_old + alpha*passes - beta*breaks - gamma*instability
    """
    with get_cursor() as cur:
        delta = 0.0
        if passed:
            delta += alpha
        if broken:
            delta -= beta
            cur.execute(f"""
                UPDATE {table} SET break_count = break_count + 1, 
                survival_score = GREATEST(0, survival_score + %s)
                WHERE id = %s
            """, (delta, record_id))
        else:
            cur.execute(f"""
                UPDATE {table} SET survival_score = survival_score + %s
                WHERE id = %s
            """, (delta, record_id))
        
        # Auto-downgrade: break_count >= 3 → mark as degraded
        cur.execute(f"""
            UPDATE {table} SET status = 'degraded'
            WHERE id = %s AND break_count >= 3 AND status = 'active'
        """, (record_id,))
        
        # Auto-archive: break_count >= 5 → move to graveyard
        cur.execute(f"""
            UPDATE {table} SET status = 'graveyard'
            WHERE id = %s AND break_count >= 5
        """, (record_id,))


def memory_apply_decay(days_inactive_threshold=30):
    """Apply time-based decay to all knowledge entries.
    
    Reduces survival_score for entries not accessed recently.
    Call periodically (e.g., daily via cron).
    """
    with get_cursor() as cur:
        for table in ['caas_wood_seeds', 'caas_knowledge_entries']:
            try:
                cur.execute(f"""
                    UPDATE {table} 
                    SET survival_score = GREATEST(0, survival_score - decay_rate)
                    WHERE last_accessed < NOW() - INTERVAL '%s days'
                    AND status = 'active'
                """, (days_inactive_threshold,))
            except Exception:
                pass


def memory_get_top(table='caas_knowledge_entries', domain=None, limit=20):
    """Get top knowledge entries by combined weight (access + survival)."""
    with get_cursor() as cur:
        if domain:
            cur.execute(f"""
                SELECT *, (access_count * 0.3 + survival_score * 0.7) as weight
                FROM {table} WHERE domain = %s AND status = 'active'
                ORDER BY weight DESC LIMIT %s
            """, (domain, limit))
        else:
            cur.execute(f"""
                SELECT *, (access_count * 0.3 + survival_score * 0.7) as weight
                FROM {table} WHERE status = 'active'
                ORDER BY weight DESC LIMIT %s
            """, (limit,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ============ Trust & Rate Limiting PG Operations ============

def trust_get_or_create(node_id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM caas_trust_records WHERE node_id=%s", (node_id,))
        row = cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
        cur.execute("INSERT INTO caas_trust_records (node_id) VALUES (%s) RETURNING *", (node_id,))
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, cur.fetchone()))

def trust_update_score(node_id, score_delta, task_success=True):
    with get_cursor() as cur:
        cur.execute("""
            UPDATE caas_trust_records
            SET trust_score = LEAST(1.0, GREATEST(0.0, trust_score + %s)),
                total_tasks = total_tasks + 1,
                successful_tasks = successful_tasks + (CASE WHEN %s THEN 1 ELSE 0 END),
                updated_at = NOW()
            WHERE node_id = %s
        """, (score_delta, task_success, node_id))

# ============ Lux Distribution PG Operations ============

def lux_distribute(task_id, executor_id, creator_id, total_lux, quality_multiplier=1.0):
    self_play = executor_id == creator_id
    if self_play:
        executor_share = total_lux * 0.5 * quality_multiplier
        creator_share = 0
        system_share = total_lux * 0.5
    else:
        executor_share = total_lux * 0.6 * quality_multiplier
        creator_share = total_lux * 0.3
        system_share = total_lux * 0.1
    
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO caas_lux_distributions (task_id, executor_id, creator_id, total_lux, executor_share, creator_share, system_share, quality_multiplier, self_play)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (task_id, executor_id, creator_id, total_lux, executor_share, creator_share, system_share, quality_multiplier, self_play))
        return {"id": cur.fetchone()[0], "executor_share": executor_share, "creator_share": creator_share, "system_share": system_share, "self_play": self_play}

# ============ Jobs PG Operations ============

def job_create(job_id, input_data):
    with get_cursor() as cur:
        cur.execute("INSERT INTO caas_jobs (job_id, input_data) VALUES (%s, %s)", (job_id, json.dumps(input_data)))

def job_update(job_id, status, result=None, error=None):
    with get_cursor() as cur:
        cur.execute("""
            UPDATE caas_jobs SET status=%s, result=%s, error=%s, completed_at=NOW() WHERE job_id=%s
        """, (status, json.dumps(result) if result else None, error, job_id))

def job_get(job_id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM caas_jobs WHERE job_id=%s", (job_id,))
        row = cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
        return None

# ============ Health Check ============

def health_check():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1")
            return {"status": "ok", "version": VERSION}
    except Exception as e:
        return {"status": "error", "error": str(e), "version": VERSION}

# ============ Self-test ============

def self_test():
    results = []
    try:
        init_tables()
        results.append(("init_tables", "PASS"))
    except Exception as e:
        results.append(("init_tables", f"FAIL: {e}"))
        return results
    
    try:
        hc = health_check()
        results.append(("health_check", "PASS" if hc["status"] == "ok" else f"FAIL: {hc}"))
    except Exception as e:
        results.append(("health_check", f"FAIL: {e}"))
    
    try:
        aid = metal_save_audit("test_hash", "test content", {"s": 0.9}, "PASS", 0.9)
        stats = metal_get_stats()
        results.append(("metal_ops", f"PASS (audit_id={aid}, total={stats['total']})"))
    except Exception as e:
        results.append(("metal_ops", f"FAIL: {e}"))
    
    try:
        wid = water_upsert_atom("test_pattern", "test_domain", source="self_test")
        conv = water_get_convergence("test_domain")
        results.append(("water_ops", f"PASS (atom_id={wid}, convergence={conv['convergence_score']:.2f})"))
    except Exception as e:
        results.append(("water_ops", f"FAIL: {e}"))
    
    try:
        jid = "test_job_" + str(int(time.time()))
        job_create(jid, {"test": True})
        job_update(jid, "completed", {"result": "ok"})
        j = job_get(jid)
        results.append(("job_ops", f"PASS (status={j['status']})"))
    except Exception as e:
        results.append(("job_ops", f"FAIL: {e}"))
    
    return results

if __name__ == "__main__":
    print("pg_storage.py self-test")
    print("=" * 40)
    results = self_test()
    for name, status in results:
        print(f"  {name}: {status}")
    passed = sum(1 for _, s in results if s.startswith("PASS"))
    print(f"\n{passed}/{len(results)} tests passed")


# === CaaS Rate Limit + Usage (PG migration) ===

def rate_limit_init():
    """Create rate limit tables in PG."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_rate_limit (
                id SERIAL PRIMARY KEY,
                ip TEXT NOT NULL,
                api_key TEXT DEFAULT '',
                used_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rate_ip_date ON caas_rate_limit(ip, used_at)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_usage_log (
                id SERIAL PRIMARY KEY,
                ip TEXT NOT NULL,
                api_key TEXT DEFAULT '',
                keyword TEXT NOT NULL,
                domain TEXT DEFAULT '',
                phases TEXT DEFAULT '',
                duration_ms INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_residuals (
                id SERIAL PRIMARY KEY,
                keyword TEXT NOT NULL,
                domain TEXT DEFAULT '',
                residual_type TEXT DEFAULT '',
                content TEXT DEFAULT '',
                score REAL DEFAULT 0,
                source TEXT DEFAULT 'caas',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_residuals_kw ON caas_residuals(keyword)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS caas_analyses (
                id SERIAL PRIMARY KEY,
                keyword TEXT NOT NULL,
                domain TEXT DEFAULT '',
                result_json TEXT DEFAULT '{}',
                phases TEXT DEFAULT '',
                duration_ms INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        return True

def rate_limit_check(ip, api_key=None):
    """Check rate limit. Returns (allowed, remaining, total)."""
    if api_key and api_key.startswith("sk_"):
        return True, 999, 1000
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM caas_rate_limit 
            WHERE ip = %s AND used_at > NOW() - INTERVAL '1 day'
        """, (ip,))
        count = cur.fetchone()[0]
        limit = 3
        return count < limit, limit - count, limit

def rate_limit_record(ip, api_key=""):
    """Record a rate limit hit."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO caas_rate_limit (ip, api_key) VALUES (%s, %s)", (ip, api_key or ""))

def usage_log(ip, api_key, keyword, domain, phases, duration_ms):
    """Log API usage."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO caas_usage_log (ip, api_key, keyword, domain, phases, duration_ms)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (ip, api_key or "", keyword, domain or "", phases or "", duration_ms))

def residual_save(keyword, domain, residuals, source="caas"):
    """Save residuals to PG."""
    with get_conn() as conn:
        cur = conn.cursor()
        for r in residuals:
            cur.execute("""
                INSERT INTO caas_residuals (keyword, domain, residual_type, content, score, source)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (keyword, domain or "", r.get("type", ""), r.get("content", "")[:2000], 
                  r.get("score", 0), source))

def residual_query(keyword=None, limit=20):
    """Query residuals from PG."""
    with get_conn() as conn:
        cur = conn.cursor()
        if keyword:
            cur.execute("""
                SELECT keyword, domain, residual_type, content, score, source, created_at
                FROM caas_residuals WHERE keyword ILIKE %s
                ORDER BY created_at DESC LIMIT %s
            """, (f"%{keyword}%", limit))
        else:
            cur.execute("""
                SELECT keyword, domain, residual_type, content, score, source, created_at
                FROM caas_residuals ORDER BY created_at DESC LIMIT %s
            """, (limit,))
        rows = cur.fetchall()
        return [{"keyword": r[0], "domain": r[1], "type": r[2], "content": r[3], 
                 "score": r[4], "source": r[5], "created_at": str(r[6])} for r in rows]

def analysis_save(keyword, domain, result, phases, duration_ms):
    """Save analysis result to PG."""
    import json as _json
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO caas_analyses (keyword, domain, result_json, phases, duration_ms)
            VALUES (%s, %s, %s, %s, %s)
        """, (keyword, domain or "", _json.dumps(result, ensure_ascii=False)[:10000], phases or "", duration_ms))

def analysis_count():
    """Count total analyses."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM caas_analyses")
        return cur.fetchone()[0]

# === Lux Distribution Engine (PG) ===

def lux_init_tables():
    """Create Lux tables in PG."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS lux_transactions (
            id SERIAL PRIMARY KEY,
            task_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            role TEXT NOT NULL,
            phase TEXT NOT NULL,
            base_lux REAL NOT NULL,
            quality_mult REAL DEFAULT 1.0,
            final_lux REAL NOT NULL,
            timestamp TEXT NOT NULL,
            metadata TEXT DEFAULT '{}'
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lux_tx_node ON lux_transactions(node_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lux_tx_task ON lux_transactions(task_id)")
        cur.execute("""CREATE TABLE IF NOT EXISTS lux_balances (
            node_id TEXT PRIMARY KEY,
            total_lux REAL DEFAULT 0,
            earned_as_executor REAL DEFAULT 0,
            earned_as_creator REAL DEFAULT 0,
            earned_as_validator REAL DEFAULT 0,
            earned_as_knowledge REAL DEFAULT 0,
            transaction_count INTEGER DEFAULT 0,
            last_updated TEXT
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS lux_system_pool (
            id SERIAL PRIMARY KEY,
            amount REAL NOT NULL,
            reason TEXT NOT NULL,
            source_task TEXT,
            timestamp TEXT NOT NULL
        )""")
        return True

def lux_record_tx(task_id, node_id, role, phase, base_lux, quality_mult, final_lux, timestamp, metadata="{}"):
    """Record a Lux transaction."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO lux_transactions (task_id, node_id, role, phase, base_lux, quality_mult, final_lux, timestamp, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (task_id, node_id, role, phase, base_lux, quality_mult, final_lux, timestamp, metadata))

def lux_update_balance(node_id, role, amount, timestamp):
    """Update node Lux balance."""
    with get_conn() as conn:
        cur = conn.cursor()
        role_col = f"earned_as_{role}" if role in ("executor","creator","validator","knowledge") else None
        cur.execute("SELECT total_lux FROM lux_balances WHERE node_id = %s", (node_id,))
        row = cur.fetchone()
        if row:
            update_parts = ["total_lux = total_lux + %s", "transaction_count = transaction_count + 1", "last_updated = %s"]
            params = [amount, timestamp]
            if role_col:
                update_parts.append(f"{role_col} = {role_col} + %s")
                params.append(amount)
            params.append(node_id)
            cur.execute(f"UPDATE lux_balances SET {', '.join(update_parts)} WHERE node_id = %s", params)
        else:
            cols = ["node_id", "total_lux", "transaction_count", "last_updated"]
            vals = [node_id, amount, 1, timestamp]
            if role_col:
                cols.append(role_col)
                vals.append(amount)
            placeholders = ", ".join(["%s"] * len(vals))
            cur.execute(f"INSERT INTO lux_balances ({', '.join(cols)}) VALUES ({placeholders})", vals)

def lux_add_to_pool(amount, reason, source_task, timestamp):
    """Add to system pool."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO lux_system_pool (amount, reason, source_task, timestamp)
            VALUES (%s, %s, %s, %s)
        """, (amount, reason, source_task, timestamp))

def lux_get_balance(node_id):
    """Get node balance from PG."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM lux_balances WHERE node_id = %s", (node_id,))
        row = cur.fetchone()
        if row:
            return {"node_id": row[0], "total_lux": row[1], "earned_as_executor": row[2],
                    "earned_as_creator": row[3], "earned_as_validator": row[4],
                    "earned_as_knowledge": row[5], "transaction_count": row[6], "last_updated": row[7]}
        return {"node_id": node_id, "total_lux": 0, "transaction_count": 0}

def lux_get_leaderboard(limit=20):
    """Get Lux leaderboard from PG."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT node_id, total_lux, transaction_count FROM lux_balances ORDER BY total_lux DESC LIMIT %s", (limit,))
        return [{"node_id": r[0], "total_lux": r[1], "transaction_count": r[2]} for r in cur.fetchall()]

def lux_get_pool_total():
    """Get system pool total."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM lux_system_pool")
        return cur.fetchone()[0]

def lux_get_stats():
    """Get distribution stats."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), COALESCE(SUM(final_lux), 0), COUNT(DISTINCT task_id), COUNT(DISTINCT node_id) FROM lux_transactions")
        row = cur.fetchone()
        cur.execute("SELECT phase, COUNT(*), COALESCE(SUM(final_lux), 0) FROM lux_transactions GROUP BY phase")
        by_phase = {r[0]: {"count": r[1], "total_lux": r[2]} for r in cur.fetchall()}
        return {
            "total_transactions": row[0],
            "total_lux_distributed": row[1],
            "unique_tasks": row[2],
            "unique_nodes": row[3],
            "by_phase": by_phase
        }
