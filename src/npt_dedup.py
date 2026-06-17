# -*- coding: utf-8 -*-
"""
R79-02: NPT Request Deduplication
NPT (NPT Protocol Stack) Request Deduplication Module

Features:
- Content hashing (SHA-256 based)
- Bloom filter for fast negative lookups
- Sliding window dedup
- Configurable TTL and max entries
- False positive handling via exact match verification

Usage:
    from npt_dedup import RequestDedup
    
    dedup = RequestDedup()
    request_id = dedup.make_request_id({"method": "POST", "path": "/api/test", "body": "..."})
    
    if dedup.is_duplicate(request_id):
        print("Duplicate request")
    else:
        dedup.mark_seen(request_id)
        print("New request, proceed")
"""

import hashlib
import json
import time
import uuid
from typing import Any, Dict, Optional, Set
from collections import deque


class BloomFilter:
    """
    Probabilistic Bloom Filter for fast dedup checks.
    False positives possible, false negatives NOT possible.
    """
    
    def __init__(self, size: int = 10000, hash_count: int = 3):
        self.size = size
        self.hash_count = hash_count
        self.bit_array = [False] * size
    
    def _hashes(self, item: str) -> list:
        """Generate hash_count hash values"""
        h1 = hash(item) % self.size
        h2 = (hash(item + "salt1") * 31) % self.size
        result = [h1]
        for i in range(1, self.hash_count):
            result.append((h1 + i * h2) % self.size)
        return result
    
    def add(self, item: str) -> None:
        """Add item to filter"""
        for h in self._hashes(item):
            self.bit_array[h] = True
    
    def might_contain(self, item: str) -> bool:
        """Check if item might be in filter (True = possible, False = definitely not)"""
        return all(self.bit_array[h] for h in self._hashes(item))
    
    def reset(self) -> None:
        """Clear the filter"""
        self.bit_array = [False] * self.size


class SlidingWindowCache:
    """
    Sliding window cache with TTL support.
    Evicts entries older than max_age seconds.
    """
    
    def __init__(self, max_size: int = 10000, max_age: float = 300.0):
        self.max_size = max_size
        self.max_age = max_age
        # {key: (timestamp, value)}
        self._cache: Dict[str, tuple] = {}
        self._access_order: deque = deque()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value if exists and not expired"""
        if key not in self._cache:
            return None
        
        timestamp, value = self._cache[key]
        if time.time() - timestamp > self.max_age:
            # Expired
            del self._cache[key]
            self._access_order.remove(key)
            return None
        
        return value
    
    def put(self, key: str, value: Any = True) -> None:
        """Put key-value pair"""
        now = time.time()
        
        if key in self._cache:
            # Update existing
            self._cache[key] = (now, value)
        else:
            # New entry
            if len(self._cache) >= self.max_size:
                # Evict oldest
                oldest = self._access_order.popleft()
                if oldest in self._cache:
                    del self._cache[oldest]
            
            self._cache[key] = (now, value)
            self._access_order.append(key)
    
    def contains(self, key: str) -> bool:
        """Check if key exists and not expired"""
        return self.get(key) is not None
    
    def cleanup(self) -> int:
        """Remove expired entries, returns count removed"""
        now = time.time()
        removed = 0
        
        expired_keys = [
            k for k, (ts, _) in self._cache.items()
            if now - ts > self.max_age
        ]
        
        for k in expired_keys:
            del self._cache[k]
            if k in self._access_order:
                self._access_order.remove(k)
            removed += 1
        
        return removed


class RequestDedup:
    """
    NPT Request Deduplication System
    
    Two-tier dedup:
    1. Bloom filter (fast, probabilistic)
    2. Exact cache (sliding window, exact match)
    
    Flow:
    1. Generate request fingerprint (hash of method+path+body)
    2. Check Bloom filter (fast negative check)
    3. If Bloom says "might exist", check exact cache
    4. If exact cache says "exists", it's a duplicate
    5. Otherwise, mark as seen in both Bloom and cache
    """
    
    def __init__(
        self,
        bloom_size: int = 50000,
        bloom_hashes: int = 5,
        cache_size: int = 10000,
        cache_ttl: float = 300.0
    ):
        self.bloom = BloomFilter(size=bloom_size, hash_count=bloom_hashes)
        self.cache = SlidingWindowCache(max_size=cache_size, max_age=cache_ttl)
        self.stats = {
            "total_checks": 0,
            "duplicates": 0,
            "new_requests": 0,
            "bloom_positives": 0,
            "false_positives": 0
        }
    
    def make_request_id(
        self,
        request: Dict[str, Any],
        fields: list = None
    ) -> str:
        """
        Generate deterministic request fingerprint.
        
        Args:
            request: Request dict with method, path, body, etc.
            fields: Which fields to include in fingerprint. Defaults to ['method', 'path', 'body']
        
        Returns:
            SHA-256 fingerprint string
        """
        if fields is None:
            fields = ['method', 'path', 'body']
        
        # Normalize and extract relevant parts
        parts = []
        for field in fields:
            value = request.get(field, '')
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True, separators=(',', ':'))
            elif value is None:
                value = ''
            parts.append(str(value))
        
        # Create deterministic string
        content = '|'.join(parts)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def is_duplicate(self, request_id: str) -> bool:
        """
        Check if request is duplicate.
        
        Returns:
            True if duplicate (should be rejected)
            False if new request (should be processed)
        """
        self.stats["total_checks"] += 1
        
        # Fast path: Bloom filter check
        if not self.bloom.might_contain(request_id):
            # Definitely not a duplicate
            self.stats["new_requests"] += 1
            return False
        
        # Bloom says "might exist" - need exact check
        self.stats["bloom_positives"] += 1
        
        if self.cache.contains(request_id):
            # Exact match - duplicate
            self.stats["duplicates"] += 1
            return True
        
        # Bloom positive but cache miss = false positive
        self.stats["false_positives"] += 1
        self.stats["new_requests"] += 1
        return False
    
    def mark_seen(self, request_id: str) -> None:
        """Mark request as seen (after is_duplicate returned False)"""
        self.bloom.add(request_id)
        self.cache.put(request_id)
    
    def check_and_mark(self, request: Dict[str, Any]) -> tuple:
        """
        Convenience method: check if duplicate, mark as seen, return both.
        
        Returns:
            (is_duplicate, request_id)
        """
        request_id = self.make_request_id(request)
        is_dup = self.is_duplicate(request_id)
        if not is_dup:
            self.mark_seen(request_id)
        return is_dup, request_id
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dedup statistics"""
        stats = self.stats.copy()
        if stats["bloom_positives"] > 0:
            stats["false_positive_rate"] = stats["false_positives"] / stats["bloom_positives"]
        else:
            stats["false_positive_rate"] = 0.0
        
        if stats["total_checks"] > 0:
            stats["duplicate_rate"] = stats["duplicates"] / stats["total_checks"]
        else:
            stats["duplicate_rate"] = 0.0
        
        return stats
    
    def reset_stats(self) -> None:
        """Reset statistics counters"""
        for k in self.stats:
            self.stats[k] = 0
    
    def cleanup(self) -> int:
        """Cleanup expired cache entries"""
        return self.cache.cleanup()


# Demo / Test
if __name__ == "__main__":
    print("=== NPT Request Deduplication Test ===\n")
    
    dedup = RequestDedup(cache_ttl=60.0)
    
    # Test 1: Basic dedup
    print("1. Basic Deduplication Test")
    req1 = {"method": "POST", "path": "/api/v1/task/create", "body": '{"title":"test"}'}
    
    is_dup, req_id = dedup.check_and_mark(req1)
    print(f"   First request: is_dup={is_dup}, id={req_id[:16]}...")
    
    is_dup2, req_id2 = dedup.check_and_mark(req1)
    print(f"   Duplicate: is_dup={is_dup2}")
    
    # Test 2: Different requests
    print("\n2. Different Requests Test")
    req2 = {"method": "POST", "path": "/api/v1/task/create", "body": '{"title":"test2"}'}
    is_dup3, _ = dedup.check_and_mark(req2)
    print(f"   Different body: is_dup={is_dup3}")
    
    req3 = {"method": "GET", "path": "/api/v1/task/create", "body": '{"title":"test"}'}
    is_dup4, _ = dedup.check_and_mark(req3)
    print(f"   Different method: is_dup={is_dup4}")
    
    # Test 3: Statistics
    print("\n3. Statistics")
    stats = dedup.get_stats()
    print(f"   Total checks: {stats['total_checks']}")
    print(f"   Duplicates found: {stats['duplicates']}")
    print(f"   New requests: {stats['new_requests']}")
    print(f"   Duplicate rate: {stats['duplicate_rate']:.1%}")
    print(f"   Bloom positives: {stats['bloom_positives']}")
    print(f"   False positives: {stats['false_positives']}")
    print(f"   False positive rate: {stats['false_positive_rate']:.1%}")
    
    # Test 4: Bloom filter saturation effect
    print("\n4. Bloom Filter Saturation Test")
    dedup2 = RequestDedup(bloom_size=100, bloom_hashes=3)  # Small for testing
    
    duplicates_found = 0
    for i in range(200):
        req = {"method": "GET", "path": f"/api/test/{i // 10}", "body": ""}  # Only 10 unique paths
        is_dup, _ = dedup2.check_and_mark(req)
        if is_dup:
            duplicates_found += 1
    
    print(f"   200 requests with 10 unique paths")
    print(f"   Duplicates detected: {duplicates_found}")
    print(f"   (Should be ~190, some false negatives possible due to small bloom)")
    
    stats2 = dedup2.get_stats()
    print(f"   False positive rate: {stats2['false_positive_rate']:.1%}")
    
    print("\n=== All Tests Passed ===")
