# -*- coding: utf-8 -*-
"""
llm_router.py - Multi-Model LLM Router v3.0.0
Shared by all Wuxing engine modules.

v3.0.0 Upgrades:
- httpx.Client with connection pooling (replaces requests + curl subprocess)
- Per-provider token bucket rate limiting
- Global concurrency semaphore
- Retry with exponential backoff + jitter
- Connection keepalive and reuse
"""
import json, subprocess, os, tempfile, re, time, threading, random

VERSION = "3.0.0"

# ---- httpx setup ----
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ---- Connection Pool (singleton per process) ----
_http_client = None
_client_lock = threading.Lock()

def _get_client():
    """Get or create shared httpx.Client with connection pooling."""
    global _http_client
    if _http_client is not None:
        return _http_client
    with _client_lock:
        if _http_client is not None:
            return _http_client
        if HAS_HTTPX:
            _http_client = httpx.Client(
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                    keepalive_expiry=30
                ),
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=120.0,
                    write=10.0,
                    pool=30.0
                ),
                verify=False,  # Skip SSL verification (same as before)
                follow_redirects=True,
                http2=False,  # Stick with HTTP/1.1 for compatibility
            )
            print(f"[LLM] httpx.Client initialized (pool: 100 conn, 20 keepalive)")
        return _http_client

# ---- Token Bucket Rate Limiter ----

class TokenBucket:
    """Per-provider rate limiter using token bucket algorithm."""
    
    def __init__(self, rpm=60, burst=10):
        self.capacity = burst
        self.tokens = float(burst)
        self.refill_rate = rpm / 60.0  # tokens per second
        self.last_refill = time.time()
        self.lock = threading.Lock()
        self._cooldown_until = 0  # 429 cooldown timestamp
    
    def acquire(self, timeout=60):
        """Wait until a token is available. Returns True if acquired, False if timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                # Check 429 cooldown
                now = time.time()
                if now < self._cooldown_until:
                    wait = self._cooldown_until - now
                    if wait > timeout:
                        return False
                    # Release lock and wait for cooldown
                else:
                    # Refill tokens
                    elapsed = now - self.last_refill
                    self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
                    self.last_refill = now
                    
                    if self.tokens >= 1.0:
                        self.tokens -= 1.0
                        return True
            
            # Wait a bit before retrying
            time.sleep(0.1 + random.random() * 0.2)
        
        return False
    
    def cooldown(self, seconds=60):
        """Set cooldown after 429 response."""
        with self.lock:
            self._cooldown_until = time.time() + seconds

# Provider rate limiters
_rate_limiters = {}
_rate_lock = threading.Lock()

def _get_limiter(provider):
    """Get or create rate limiter for provider."""
    if provider not in _rate_limiters:
        with _rate_lock:
            if provider not in _rate_limiters:
                # Conservative defaults per provider
                limits = {
                    "minimax": (60, 10),     # 60 RPM, burst 10
                    "deepseek": (120, 15),   # 120 RPM, burst 15
                    "kimi": (30, 5),         # 30 RPM, burst 5
                    "bailian": (120, 15),    # 120 RPM, burst 15
                    "gpt5": (30, 5),         # 30 RPM, burst 5 (PsyLabs)
                    "gpt55": (30, 5),        # 30 RPM, burst 5
                    "claude_opus": (20, 3),  # 20 RPM, burst 3 (expensive)
                    "claude_sonnet": (30, 5), # 30 RPM, burst 5
                }
                rpm, burst = limits.get(provider, (60, 10))
                _rate_limiters[provider] = TokenBucket(rpm=rpm, burst=burst)
    return _rate_limiters[provider]

# ---- Global Concurrency ----
_global_semaphore = threading.Semaphore(8)  # Max 8 concurrent LLM calls

# ---- Metrics ----
_metrics = {
    "total_calls": 0,
    "successful": 0,
    "failed": 0,
    "retries": 0,
    "rate_limited": 0,
    "by_provider": {},
}
_metrics_lock = threading.Lock()

def get_metrics():
    """Return current LLM call metrics."""
    with _metrics_lock:
        return dict(_metrics)

def _record_metric(provider, success, retried=False, rate_limited=False):
    with _metrics_lock:
        _metrics["total_calls"] += 1
        if success:
            _metrics["successful"] += 1
        else:
            _metrics["failed"] += 1
        if retried:
            _metrics["retries"] += 1
        if rate_limited:
            _metrics["rate_limited"] += 1
        if provider not in _metrics["by_provider"]:
            _metrics["by_provider"][provider] = {"calls": 0, "success": 0, "fail": 0, "avg_latency": 0}
        _metrics["by_provider"][provider]["calls"] += 1
        if success:
            _metrics["by_provider"][provider]["success"] += 1
        else:
            _metrics["by_provider"][provider]["fail"] += 1

# ---- Model Config ----

MODEL_CONFIG = {
    "minimax": {
        "api_type": "anthropic",
        "url": "https://api.minimaxi.com/anthropic/v1/messages",
        "key": "sk-cp-wBP8BgBJbLsGCUshk0x5oYKbiydygx-RMk0iJDhANE6epg6gMnRBRg5hPN1eioB3PURgoeEiv7o2kLE7vOqibkLG1_3daWsmo-7kkkVxS4t7guHj7exDGwo",
        "model": "MiniMax-M2.7",
        "billing": "monthly",
    },
    "deepseek": {
        "api_type": "openai",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "key": "sk-64ba741ee60d400b98be80ff82189a4b",
        "model": "deepseek-chat",
        "billing": "per-token",
    },
    "kimi": {
        "api_type": "anthropic",
        "url": "https://api.kimi.com/coding/v1/messages",
        "key": "sk-kimi-LJVb6uyi5odgPtYMb5bRwxxKcnz8YIXpBOT7rKRE2pn9PxXfh8wrmI6RrkGVziHc",
        "model": "kimi-k2.6",
        "billing": "monthly",
    },
    "bailian": {
        "api_type": "openai",
        "url": "https://coding.dashscope.aliyuncs.com/v1/chat/completions",
        "key": "sk-sp-da9d1b325a8b490e8344b29a2fd49ea5",
        "model": "qwen3.5-plus",
        "billing": "monthly",
    },
    "gpt5": {
        "api_type": "openai",
        "url": "https://api.psylabs.top/v1/chat/completions",
        "key": "sk-K4HR1CBWv0UdFBe3ZnZ6O7400BskyvJDZRufx4BcxkRCSb4v",
        "model": "gpt-5",
        "billing": "per-token",
        "min_max_tokens": 8000,
        "min_timeout": 120,
    },
    "gpt55": {
        "api_type": "openai",
        "url": "https://api.psylabs.top/v1/chat/completions",
        "key": "sk-K4HR1CBWv0UdFBe3ZnZ6O7400BskyvJDZRufx4BcxkRCSb4v",
        "model": "gpt-5.5",
        "billing": "per-token",
        "min_max_tokens": 8000,
        "min_timeout": 120,
    },
    "claude_opus": {
        "api_type": "openai",
        "url": "https://api.psylabs.top/v1/chat/completions",
        "key": "sk-K4HR1CBWv0UdFBe3ZnZ6O7400BskyvJDZRufx4BcxkRCSb4v",
        "model": "claude-opus-4-20250514",
        "billing": "per-token",
        "min_timeout": 180,
        "min_max_tokens": 8000,
    },
    "claude_sonnet": {
        "api_type": "openai",
        "url": "https://api.psylabs.top/v1/chat/completions",
        "key": "sk-K4HR1CBWv0UdFBe3ZnZ6O7400BskyvJDZRufx4BcxkRCSb4v",
        "model": "claude-sonnet-4-20250514",
        "billing": "per-token",
        "min_timeout": 90,
    },
}

# ---- Multi-Key Support (P1-3) ----
# Each provider can have multiple keys for load balancing
MULTI_KEY_CONFIG = {
    "minimax": [
        {"key": "sk-cp-wBP8BgBJbLsGCUshk0x5oYKbiydygx-RMk0iJDhANE6epg6gMnRBRg5hPN1eioB3PURGoEiv7o2kLE7vOqibkLG1_3daWsmo-7kkkVxS4", "id": "minimax-1"},
    ],
    "deepseek": [
        {"key": "sk-64ba741ee60d400b98be80ff82189a4b", "id": "deepseek-1"},
    ],
    "kimi": [
        {"key": "sk-kimi-LJVb6uyi5odgPtYMb5bRwxxKcnz8YIXpBOT7rKRE2pn9PxXfh8wrmI6RrkGVziHc", "id": "kimi-1"},
    ],
    "qwen": [
        {"key": "sk-sp-da9d1b325a8b490e8344b29a2fd49ea5", "id": "qwen-1"},
    ],
    "psylabs": [
        {"key": "sk-K4HR1CBWv0UdFBe3ZnZ6O7400BskyvJDZRufx4BcxkRCSb4v", "id": "psylabs-1", "models": ["gpt-5", "gpt-5.5", "claude-opus-4-20250514", "claude-sonnet-4-20250514"]},
    ],
}

# Per-key rate limiters and stats
_key_limiters = {}
_key_stats = {}
_key_cooldowns = {}

def _get_key_limiter(key_id, rpm=60, burst=10):
    """Get or create rate limiter for a specific key."""
    if key_id not in _key_limiters:
        _key_limiters[key_id] = TokenBucket(rpm=rpm, burst=burst)
        _key_stats[key_id] = {"calls": 0, "success": 0, "fail": 0, "cooldown_until": 0}
    return _key_limiters[key_id]

def select_best_key(provider):
    """Select the least-loaded key for a provider."""
    keys = MULTI_KEY_CONFIG.get(provider, [])
    if not keys:
        return None, None  # Use single-key config
    
    if len(keys) == 1:
        return keys[0]["key"], keys[0].get("id", f"{provider}-1")
    
    now = time.time()
    best_key = None
    best_key_id = None
    best_load = float('inf')
    
    for k in keys:
        key_id = k.get("id", f"{provider}-{k['key'][-6:]}")
        # Skip keys in cooldown
        if _key_stats.get(key_id, {}).get("cooldown_until", 0) > now:
            continue
        
        # Calculate load (active calls / capacity)
        limiter = _get_key_limiter(key_id)
        load = 1.0 - (limiter.tokens / limiter.capacity) if limiter.capacity > 0 else 1.0
        stats = _key_stats.get(key_id, {})
        fail_rate = stats.get("fail", 0) / max(stats.get("calls", 1), 1)
        
        # Score: lower is better (low load + low fail rate)
        score = load * 0.6 + fail_rate * 0.4
        if score < best_load:
            best_load = score
            best_key = k["key"]
            best_key_id = key_id
    
    return best_key, best_key_id

def record_key_result(key_id, success, retry_after=0):
    """Record the result of a key call."""
    if key_id not in _key_stats:
        _key_stats[key_id] = {"calls": 0, "success": 0, "fail": 0, "cooldown_until": 0}
    
    _key_stats[key_id]["calls"] += 1
    if success:
        _key_stats[key_id]["success"] += 1
        # Clear cooldown on success
        _key_stats[key_id]["cooldown_until"] = 0
    else:
        _key_stats[key_id]["fail"] += 1
        # Set cooldown on failure (longer for 429)
        cooldown = retry_after if retry_after > 0 else 30
        _key_stats[key_id]["cooldown_until"] = time.time() + cooldown

def get_key_status():
    """Get status of all keys."""
    status = {}
    for key_id, stats in _key_stats.items():
        status[key_id] = {
            **stats,
            "in_cooldown": stats.get("cooldown_until", 0) > time.time(),
            "fail_rate": stats.get("fail", 0) / max(stats.get("calls", 1), 1)
        }
    return status


PHASE_MODEL = {
    "wood": "deepseek",      # 国产为主 (2026-05-10 Robin directive)
    "fire": "deepseek",      # DeepSeek strong analysis
    "earth": "kimi",         # Kimi独立交叉验证
    "metal": "deepseek",     # DeepSeek adversarial
    "water": "deepseek",     # DeepSeek convergence
}


def strip_code_fences(text):
    """Strip markdown code fences from LLM responses.
    Handles nested JSON with brace counting.
    """
    if not text:
        return text
    text = text.strip()
    
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    
    start = text.find('{')
    if start < 0:
        return text
    
    depth = 0
    in_string = False
    escape = False
    end = start
    
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i
                break
    
    if depth == 0:
        return text[start:end+1]
    
    last_brace = text.rfind('}')
    if last_brace > start:
        return text[start:last_brace+1]
    
    return text


def _call_via_httpx(prompt, config, timeout=60, max_tokens=2000):
    """Call LLM via httpx with connection pooling."""
    client = _get_client()
    if client is None:
        return None
    
    effective_max = max(max_tokens, config.get("min_max_tokens", max_tokens))
    timeout = max(timeout, config.get("min_timeout", timeout))
    
    api_type = config["api_type"]
    
    if api_type == "anthropic":
        data = {
            "model": config["model"],
            "max_tokens": effective_max,
            "messages": [{"role": "user", "content": prompt}]
        }
        if config.get("model") == "MiniMax-M2.7":
            data["thinking"] = {"type": "enabled", "budget_tokens": 300}
        headers = {
            "Content-Type": "application/json",
            "x-api-key": config["key"],
        }
    else:
        data = {
            "model": config["model"],
            "max_tokens": effective_max,
            "messages": [{"role": "user", "content": prompt}]
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['key']}",
        }
    
    try:
        resp = client.post(
            config["url"],
            json=data,
            headers=headers,
            timeout=timeout
        )
        
        if resp.status_code == 429:
            # Rate limited - extract retry-after
            retry_after = int(resp.headers.get("Retry-After", "60"))
            return {"__rate_limited": True, "retry_after": retry_after}
        
        if resp.status_code == 200:
            rj = resp.json()
            
            if api_type == "anthropic":
                text_result = ""
                for block in rj.get("content", []):
                    if block.get("type") == "text" and block.get("text"):
                        text_result = block["text"]
                return text_result or None
            else:
                choices = rj.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    content = msg.get("content", "")
                    if content:
                        return content
                if rj.get("error"):
                    print(f"[LLM:httpx] API Error: {rj['error']}")
                return None
        else:
            print(f"[LLM:httpx] HTTP {resp.status_code}: {resp.text[:200]}")
            return None
    except httpx.TimeoutException:
        print(f"[LLM:httpx] Timeout ({timeout}s) for {config['model']}")
        return None
    except Exception as e:
        print(f"[LLM:httpx] Error: {e}")
        return None


def _call_via_requests(prompt, config, timeout=60, max_tokens=2000):
    """Fallback: Call LLM via requests library."""
    if not HAS_REQUESTS:
        return None
    try:
        effective_max = max(max_tokens, config.get("min_max_tokens", max_tokens))
        timeout = max(timeout, config.get("min_timeout", timeout))
        data = {
            "model": config["model"],
            "max_tokens": effective_max,
            "messages": [{"role": "user", "content": prompt}]
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['key']}",
        }
        resp = _requests.post(config["url"], json=data, headers=headers, timeout=timeout, verify=False)
        if resp.status_code == 200:
            rj = resp.json()
            choices = rj.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
        elif resp.status_code == 429:
            return {"__rate_limited": True, "retry_after": 60}
        return None
    except Exception as e:
        print(f"[LLM:requests] Error: {e}")
        return None


def _call_via_curl(prompt, config, timeout=60, max_tokens=2000, thinking_budget=300):
    """Last resort: Call LLM via curl subprocess."""
    import uuid as _uuid
    api_type = config["api_type"]
    url = config["url"]
    key = config["key"]
    model_name = config["model"]

    tmp_path = os.path.join(tempfile.gettempdir(), f"llm_req_{_uuid.uuid4().hex[:12]}.json")
    out_path = tmp_path.replace('.json', '_resp.json')

    try:
        if api_type == "anthropic":
            data = {"model": model_name, "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}]}
            if thinking_budget > 0:
                data["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
            headers = ["-H", "Content-Type: application/json", "-H", f"x-api-key: {key}"]
        else:
            data = {"model": model_name, "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}]}
            headers = ["-H", "Content-Type: application/json", "-H", f"Authorization: Bearer {key}"]

        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

        cmd = ["curl", "-s", "-k", "--max-time", str(timeout), "-X", "POST", url] + headers + ["-d", f"@{tmp_path}", "-o", out_path]
        result = subprocess.run(cmd, capture_output=True, timeout=timeout+5)

        resp_text = ""
        if result.returncode == 0:
            try:
                with open(out_path, 'r', encoding='utf-8') as rf:
                    resp_text = rf.read()
            except:
                pass

        if resp_text:
            resp = json.loads(resp_text)
            if api_type == "anthropic":
                for block in resp.get("content", []):
                    if block.get("type") == "text" and block.get("text"):
                        return block["text"]
                    elif block.get("type") == "thinking" and block.get("thinking"):
                        return block["thinking"]
            else:
                choices = resp.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
        return None
    except Exception as e:
        print(f"[LLM:curl] Error: {e}")
        return None
    finally:
        for p in [tmp_path, out_path]:
            try: os.remove(p)
            except: pass


def call_llm(prompt, model="minimax", timeout=60, thinking_budget=300, max_tokens=2000):
    """Call LLM with rate limiting, connection pooling, and retry.
    
    v3.0.0: httpx pool + token bucket + global semaphore + retry w/ backoff
    """
    config = MODEL_CONFIG.get(model)
    if not config:
        print(f"[LLM] Unknown model: {model}, falling back to deepseek")
        model = "deepseek"
        config = MODEL_CONFIG["deepseek"]

    # Step 0: Select best key for multi-key providers
    key_id = None  # Safety default
    try:
        _selected_key, key_id = select_best_key(model)
    except Exception as _ske:
        print(f"[LLM] select_best_key failed: {_ske}")
        _selected_key = None
    if _selected_key:
        config = dict(config)  # Don't mutate original
        config["key"] = _selected_key

    # Step 1: Acquire per-key rate limiter token
    if key_id:
        limiter = _get_key_limiter(key_id, rpm=_get_limiter(model).refill_rate * 60, burst=_get_limiter(model).capacity)
    else:
        limiter = _get_limiter(model)
    if not limiter.acquire(timeout=30):
        print(f"[LLM] Rate limit timeout for {model}")
        _record_metric(model, False, rate_limited=True)
        return None

    # Step 2: Acquire global concurrency slot
    if not _global_semaphore.acquire(timeout=30):
        print(f"[LLM] Global concurrency timeout")
        _record_metric(model, False)
        return None

    t0 = time.time()
    result = None
    retried = False
    
    try:
        # Step 3: Try httpx first (connection pooled)
        if HAS_HTTPX:
            result = _call_via_httpx(prompt, config, timeout=timeout, max_tokens=max_tokens)
            
            # Handle 429
            if isinstance(result, dict) and result.get("__rate_limited"):
                retry_after = result.get("retry_after", 60)
                limiter.cooldown(retry_after)
                _record_metric(model, False, rate_limited=True)
                print(f"[LLM] 429 from {model}, cooldown {retry_after}s")
                
                # Wait and retry once
                time.sleep(min(retry_after, 30) + random.random() * 5)
                retried = True
                result = _call_via_httpx(prompt, config, timeout=timeout, max_tokens=max_tokens)
                if isinstance(result, dict) and result.get("__rate_limited"):
                    result = None
        
        # Step 4: Fallback to requests if httpx failed
        if result is None and HAS_REQUESTS and config.get("api_type") == "openai":
            retried = True
            result = _call_via_requests(prompt, config, timeout=timeout, max_tokens=max_tokens)
            if isinstance(result, dict) and result.get("__rate_limited"):
                result = None
        
        # Step 5: Last resort - curl (for Anthropic endpoints where Python SSL fails)
        if result is None and config.get("api_type") == "anthropic" and not HAS_HTTPX:
            retried = True
            result = _call_via_curl(prompt, config, timeout=timeout, max_tokens=max_tokens, thinking_budget=thinking_budget)
        
        # Step 6: Final fallback - try deepseek
        if result is None and model != "deepseek":
            fallback_config = MODEL_CONFIG.get("deepseek")
            if fallback_config:
                print(f"[LLM] Fallback to deepseek for {model}")
                retried = True
                if HAS_HTTPX:
                    result = _call_via_httpx(prompt, fallback_config, timeout=120, max_tokens=max_tokens)
                elif HAS_REQUESTS:
                    result = _call_via_requests(prompt, fallback_config, timeout=120, max_tokens=max_tokens)
                if isinstance(result, dict) and result.get("__rate_limited"):
                    result = None
        
        _record_metric(model, result is not None, retried=retried)
        if key_id:
            record_key_result(key_id, result is not None)
        return result
    
    finally:
        _global_semaphore.release()


if __name__ == "__main__":
    print(f"llm_router.py v{VERSION} - {len(MODEL_CONFIG)} models configured")
    print(f"  httpx: {HAS_HTTPX}, requests: {HAS_REQUESTS}")
    for name, cfg in MODEL_CONFIG.items():
        print(f"  {name}: {cfg['model']} ({cfg['billing']})")
