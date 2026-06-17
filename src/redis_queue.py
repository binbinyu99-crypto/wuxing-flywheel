# -*- coding: utf-8 -*-
"""
redis_queue.py - Redis-based task queue for Flywheel API
Separates HTTP submission from pipeline execution
"""
import redis, json, time, uuid
from typing import Optional, Dict, Any

class RedisTaskQueue:
    def __init__(self, host='127.0.0.1', port=6379, db=0):
        self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.queue_key = 'flywheel:tasks:pending'
        self.active_key = 'flywheel:tasks:active'
        self.result_prefix = 'flywheel:result:'
        self.max_queue_depth = 100
    
    def submit(self, topic: str, domain: str = 'general', depth: str = 'deep', 
               max_rounds: int = 2, priority: str = 'free') -> str:
        """Submit task to Redis queue"""
        # Check queue depth
        queue_depth = self.redis.llen(self.queue_key)
        if queue_depth >= self.max_queue_depth:
            raise Exception(f"Queue full ({queue_depth}/{self.max_queue_depth})")
        
        task_id = f"run-{uuid.uuid4().hex[:12]}"
        task_data = {
            'task_id': task_id,
            'topic': topic,
            'domain': domain,
            'depth': depth,
            'max_rounds': max_rounds,
            'priority': priority,
            'submitted_at': time.time(),
            'status': 'queued'
        }
        
        # Store task metadata
        self.redis.hset(f'flywheel:task:{task_id}', mapping={
            k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
            for k, v in task_data.items()
        })
        
        # Add to queue with priority (paid tasks get LPUSH, free get RPUSH)
        if priority == 'paid':
            self.redis.lpush(self.queue_key, task_id)
        else:
            self.redis.rpush(self.queue_key, task_id)
        
        return task_id
    
    def dequeue(self, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """Dequeue task from Redis (blocking)"""
        result = self.redis.brpop(self.queue_key, timeout=timeout)
        if not result:
            return None
        
        _, task_id = result
        task_data = self.redis.hgetall(f'flywheel:task:{task_id}')
        if not task_data:
            return None
        
        # Mark as active
        self.redis.hset(f'flywheel:task:{task_id}', 'status', 'running')
        self.redis.hset(f'flywheel:task:{task_id}', 'started_at', str(time.time()))
        self.redis.hset(self.active_key, task_id, str(time.time()))
        
        return {
            'task_id': task_id,
            'topic': task_data.get('topic', ''),
            'domain': task_data.get('domain', 'general'),
            'depth': task_data.get('depth', 'deep'),
            'max_rounds': int(task_data.get('max_rounds', 2)),
            'submitted_at': float(task_data.get('submitted_at', 0))
        }
    
    def complete(self, task_id: str, result: Dict[str, Any], error: str = None):
        """Mark task as complete"""
        self.redis.hset(f'flywheel:task:{task_id}', mapping={
            'status': 'completed' if not error else 'failed',
            'completed_at': str(time.time()),
            'result': json.dumps(result),
            'error': error or ''
        })
        self.redis.hdel(self.active_key, task_id)
        
        # Store result for polling
        self.redis.set(
            f'{self.result_prefix}{task_id}',
            json.dumps({'status': 'completed' if not error else 'failed', 'result': result, 'error': error}),
            ex=86400  # 24h TTL
        )
    
    def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task result"""
        task_data = self.redis.hgetall(f'flywheel:task:{task_id}')
        if not task_data:
            return None
        
        status = task_data.get('status', 'unknown')
        result_str = task_data.get('result', '')
        result = json.loads(result_str) if result_str else None
        
        return {
            'task_id': task_id,
            'status': status,
            'topic': task_data.get('topic', ''),
            'result': result,
            'error': task_data.get('error', ''),
            'submitted_at': float(task_data.get('submitted_at', 0)),
            'started_at': float(task_data.get('started_at', 0)),
            'completed_at': float(task_data.get('completed_at', 0))
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get queue status"""
        queue_depth = self.redis.llen(self.queue_key)
        active_count = self.redis.hlen(self.active_key)
        
        # Calculate estimated wait time
        wait_time = queue_depth * 60 // 10  # 60s per task, 10 workers
        
        return {
            'queue_depth': queue_depth,
            'active_count': active_count,
            'estimated_wait_seconds': wait_time,
            'backpressure': 'high' if queue_depth > 40 else 'medium' if queue_depth > 20 else 'low'
        }
    
    def cleanup_stale(self, timeout: int = 3600):
        """Clean up stale active tasks"""
        now = time.time()
        for task_id, started_at in self.redis.hgetall(self.active_key).items():
            if now - float(started_at) > timeout:
                self.redis.hset(f'flywheel:task:{task_id}', 'status', 'timeout')
                self.redis.hdel(self.active_key, task_id)
                print(f"Cleaned up stale task: {task_id}")
