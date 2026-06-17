# -*- coding: utf-8 -*-
"""npt_access.py - NPT (Non-Proliferation Treaty) v2.0 Access Control for CaaS.

Implements L0-L6 permission levels for flywheel access.

L0: Public read-only (published reports, case studies)
L1: Basic analysis (3/day free tier, compressed output)
L2: Standard analysis (paid, full output, no raw data)
L3: Deep analysis (paid premium, multi-round iteration, raw residuals)
L4: Engine access (API, custom domains, webhook delivery)
L5: Self-modification (can modify flywheel parameters within bounds)
L6: Core access (full pipeline control, defense layer config) - INTERNAL ONLY

Axiom Zero: Capability growth never constrained, only usage governed.
"""

VERSION = "2.0.0"

import time
import hashlib
import json
from datetime import datetime, timedelta

# Level definitions
LEVELS = {
    0: {
        "name": "Public",
        "description": "Read-only access to published reports",
        "max_requests_per_day": None,  # unlimited reads
        "features": ["read_reports", "read_cases"],
        "output_depth": "summary",
        "max_rounds": 0,
        "price_monthly": 0,
    },
    1: {
        "name": "Starter",
        "description": "Basic analysis with rate limits",
        "max_requests_per_day": 3,
        "features": ["read_reports", "read_cases", "run_analysis"],
        "output_depth": "compressed",
        "max_rounds": 1,
        "price_monthly": 0,  # freemium
    },
    2: {
        "name": "Pro",
        "description": "Standard analysis with full output",
        "max_requests_per_day": 20,
        "features": ["read_reports", "read_cases", "run_analysis", "full_output", "export_pdf"],
        "output_depth": "full",
        "max_rounds": 2,
        "price_monthly": 2999,  # RMB
    },
    3: {
        "name": "Enterprise",
        "description": "Deep analysis with multi-round iteration",
        "max_requests_per_day": 100,
        "features": ["read_reports", "read_cases", "run_analysis", "full_output", 
                      "export_pdf", "multi_round", "raw_residuals", "custom_domain"],
        "output_depth": "deep",
        "max_rounds": 5,
        "price_monthly": 9999,
    },
    4: {
        "name": "API",
        "description": "Programmatic engine access",
        "max_requests_per_day": 500,
        "features": ["read_reports", "read_cases", "run_analysis", "full_output",
                      "export_pdf", "multi_round", "raw_residuals", "custom_domain",
                      "api_access", "webhook", "batch_analysis"],
        "output_depth": "deep",
        "max_rounds": 10,
        "price_monthly": 29999,
    },
    5: {
        "name": "Partner",
        "description": "Self-modification within bounds",
        "max_requests_per_day": None,
        "features": ["all", "modify_weights", "modify_thresholds", "custom_prompts"],
        "output_depth": "deep",
        "max_rounds": None,
        "price_monthly": None,  # custom pricing
    },
    6: {
        "name": "Core",
        "description": "Internal only - full pipeline control",
        "max_requests_per_day": None,
        "features": ["all", "defense_config", "model_routing", "pipeline_code"],
        "output_depth": "deep",
        "max_rounds": None,
        "price_monthly": None,  # internal
    },
}

# In-memory rate limiter (would use PG in production)
_rate_cache = {}

class NPTAccessControl:
    """NPT v2.0 access control gate."""
    
    def __init__(self, pg_conn_fn=None):
        self.pg_conn_fn = pg_conn_fn
        self._ensure_table()
    
    def _ensure_table(self):
        if not self.pg_conn_fn:
            return
        try:
            conn = self.pg_conn_fn()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS npt_users (
                    user_id TEXT PRIMARY KEY,
                    level INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT NOW(),
                    requests_today INTEGER DEFAULT 0,
                    last_request_date DATE DEFAULT CURRENT_DATE,
                    api_key TEXT,
                    metadata JSONB DEFAULT '{}'
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS npt_usage_log (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    level INTEGER,
                    action TEXT,
                    topic TEXT,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    allowed BOOLEAN,
                    reason TEXT
                )
            """)
            conn.commit()
            cur.close()
        except Exception as e:
            print(f"[NPT] Table init error: {e}")
    
    def check_access(self, user_id, action, topic=""):
        """Check if user has access to perform action.
        
        Returns: (allowed: bool, reason: str, level_info: dict)
        """
        level = self._get_user_level(user_id)
        level_def = LEVELS.get(level, LEVELS[0])
        
        # Check feature access
        features = level_def["features"]
        if "all" not in features and action not in features:
            return False, f"L{level} ({level_def['name']}) does not include '{action}'. Upgrade required.", level_def
        
        # Check rate limit
        max_req = level_def["max_requests_per_day"]
        if max_req is not None:
            today = datetime.now().strftime("%Y-%m-%d")
            cache_key = f"{user_id}:{today}"
            count = _rate_cache.get(cache_key, 0)
            if count >= max_req:
                return False, f"Rate limit reached ({count}/{max_req} today). Upgrade for more.", level_def
            _rate_cache[cache_key] = count + 1
        
        # Log usage
        self._log_usage(user_id, level, action, topic, True, "OK")
        
        return True, "OK", level_def
    
    def get_pipeline_config(self, user_id):
        """Get pipeline configuration based on user level."""
        level = self._get_user_level(user_id)
        level_def = LEVELS.get(level, LEVELS[0])
        
        return {
            "max_rounds": level_def.get("max_rounds", 1),
            "output_depth": level_def.get("output_depth", "compressed"),
            "include_residuals": "raw_residuals" in level_def.get("features", []),
            "include_defense_metrics": level >= 4,
            "allow_custom_domain": "custom_domain" in level_def.get("features", []),
        }
    
    def _get_user_level(self, user_id):
        if self.pg_conn_fn:
            try:
                conn = self.pg_conn_fn()
                cur = conn.cursor()
                cur.execute("SELECT level FROM npt_users WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                cur.close()
                if row:
                    return row[0]
            except:
                pass
        return 1  # default to Starter
    
    def _log_usage(self, user_id, level, action, topic, allowed, reason):
        if self.pg_conn_fn:
            try:
                conn = self.pg_conn_fn()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO npt_usage_log (user_id, level, action, topic, allowed, reason) VALUES (%s,%s,%s,%s,%s,%s)",
                    (user_id, level, action, topic[:200], allowed, reason)
                )
                conn.commit()
                cur.close()
            except:
                pass
    
    def register_user(self, user_id, level=1, api_key=None):
        """Register or update a user."""
        if not self.pg_conn_fn:
            return False
        try:
            conn = self.pg_conn_fn()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO npt_users (user_id, level, api_key) VALUES (%s, %s, %s) "
                "ON CONFLICT (user_id) DO UPDATE SET level = EXCLUDED.level",
                (user_id, level, api_key or hashlib.md5(user_id.encode()).hexdigest())
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            print(f"[NPT] Register error: {e}")
            return False


def self_test():
    """Quick self-test without PG."""
    npt = NPTAccessControl()
    
    # Test L1 user
    ok, reason, info = npt.check_access("test_user", "run_analysis")
    assert ok, f"L1 should allow run_analysis: {reason}"
    
    # Test rate limit (3/day for L1)
    for _ in range(2):
        npt.check_access("test_rate", "run_analysis")
    ok, reason, info = npt.check_access("test_rate", "run_analysis")
    assert not ok, "Should be rate limited after 3 requests"
    
    # Test feature gate
    ok, reason, info = npt.check_access("test_user2", "api_access")
    assert not ok, "L1 should not have api_access"
    
    # Test pipeline config
    config = npt.get_pipeline_config("test_user")
    assert config["max_rounds"] == 1
    assert config["output_depth"] == "compressed"
    
    print("[NPT] Self-test PASSED: access control, rate limiting, feature gating, pipeline config")
    return True


if __name__ == "__main__":
    self_test()
