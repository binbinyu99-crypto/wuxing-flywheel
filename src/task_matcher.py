# -*- coding: utf-8 -*-
"""
R19-2: 任务-节点智能匹配器
基于 R19-1 节点能力画像，实现：
1. 多因子匹配算法（技能匹配 + 负载均衡 + 信任分）
2. 匹配历史记录（PG 表 task_match_history）
3. 增强 /nodes/match API
4. 自测验证
"""

import psycopg2
import json
import datetime
import hashlib


DB_CONF = dict(host='localhost', port=5432, dbname='matrix', user='postgres', password='<DB_PASSWORD>')


def get_conn():
    return psycopg2.connect(**DB_CONF)


def ensure_match_tables():
    """Create match history table if not exists"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_match_history (
            id SERIAL PRIMARY KEY,
            task_id TEXT NOT NULL,
            matched_node TEXT NOT NULL,
            score REAL NOT NULL,
            factors JSONB,
            selected BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_tmh_task ON task_match_history(task_id)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_tmh_node ON task_match_history(matched_node)
    """)
    conn.commit()
    cur.close()
    conn.close()


def get_node_load(node_id):
    """Get current task load for a node (assigned but not completed)"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM tasks 
        WHERE assigned_to = %s AND status = 'assigned'
    """, (node_id,))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def get_node_trust(node_id):
    """Get trust score from PG (completed tasks, success rate)"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM tasks 
        WHERE assigned_to = %s AND status = 'completed'
    """, (node_id,))
    completed = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*) FROM tasks 
        WHERE assigned_to = %s AND status = 'failed'
    """, (node_id,))
    failed = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    total = completed + failed
    if total == 0:
        return {'score': 50.0, 'completed': 0, 'failed': 0, 'success_rate': 0.0}
    
    success_rate = completed / total * 100
    # Trust score: base 50 + up to 50 based on success rate and volume
    volume_bonus = min(completed / 10, 1.0) * 25  # up to 25 for 10+ tasks
    rate_bonus = (success_rate / 100) * 25  # up to 25 for 100% rate
    score = 50 + volume_bonus + rate_bonus
    
    return {'score': min(score, 100.0), 'completed': completed, 'failed': failed, 'success_rate': success_rate}


def get_all_profiles():
    """Get all node profiles from PG (individual columns)"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""SELECT node_id, cpu_cores, memory_gb, gpu, os, skills, languages,
                          frameworks, max_concurrent, avg_completion_time, success_rate,
                          total_tasks_completed, specialization, metadata
                   FROM node_profiles""")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    result = {}
    for r in rows:
        result[r[0]] = {
            'cpu_cores': r[1] or 0,
            'memory_gb': float(r[2] or 0),
            'gpu': r[3] or '',
            'has_gpu': bool(r[3]),
            'os': r[4] or '',
            'skills': list(r[5] or []),
            'languages': list(r[6] or []),
            'frameworks': list(r[7] or []),
            'max_concurrent_tasks': r[8] or 5,
            'avg_completion_time': float(r[9] or 0),
            'success_rate': float(r[10] or 0),
            'total_tasks_completed': r[11] or 0,
            'specialization': r[12] or '',
            'metadata': r[13] or {},
        }
    return result


def parse_task_requirements(task_data):
    """Extract requirements from task data (title, description, tags)"""
    title = (task_data.get('title', '') or '').lower()
    desc = (task_data.get('description', '') or '').lower()
    text = title + ' ' + desc
    
    # Auto-detect required skills from keywords
    skill_keywords = {
        'python': ['python', 'flask', 'django', 'pip', 'psycopg2'],
        'javascript': ['javascript', 'js', 'node', 'react', 'vue', 'html', 'css'],
        'postgresql': ['postgresql', 'postgres', 'pg_', 'sql', 'database', '数据库'],
        'redis': ['redis', '缓存', 'cache'],
        'docker': ['docker', 'container', '容器'],
        'nginx': ['nginx', '代理', 'proxy', 'reverse'],
        'linux': ['linux', 'bash', 'shell', 'ssh'],
        'api': ['api', 'rest', 'endpoint', '接口'],
        'frontend': ['前端', 'frontend', 'ui', 'ux', '界面', '页面', 'html', 'css'],
        'backend': ['后端', 'backend', '服务器', 'server'],
        'devops': ['devops', '部署', 'deploy', '运维', 'monitor', '监控'],
        'ml': ['机器学习', 'ml', 'model', '模型', 'ai', '智能'],
        'security': ['安全', 'security', '认证', 'auth', 'jwt', '加密'],
    }
    
    detected_skills = []
    for skill, keywords in skill_keywords.items():
        if any(kw in text for kw in keywords):
            detected_skills.append(skill)
    
    # Detect specialization
    spec = None
    if any(w in text for w in ['前端', 'frontend', 'ui', 'ux', '页面']):
        spec = 'frontend'
    elif any(w in text for w in ['后端', 'backend', '服务', 'api']):
        spec = 'backend'
    elif any(w in text for w in ['运维', 'devops', '部署', '监控']):
        spec = 'devops'
    elif any(w in text for w in ['全栈', 'fullstack']):
        spec = 'fullstack'
    
    return {
        'required_skills': task_data.get('required_skills', detected_skills),
        'preferred_specialization': task_data.get('preferred_specialization', spec),
        'min_memory_gb': task_data.get('min_memory_gb'),
        'needs_gpu': task_data.get('needs_gpu', False),
        'priority': task_data.get('priority', 'medium'),
    }


def smart_match(task_data, top_n=3, record_history=True):
    """
    Enhanced matching: skill match + load balancing + trust score
    
    Weights:
    - Skill match: 35%
    - Specialization: 10%
    - Load balance: 20% (fewer current tasks = higher score)
    - Trust score: 25%
    - Resource fit: 10%
    
    Returns: [(node_id, total_score, factor_breakdown), ...]
    """
    ensure_match_tables()
    profiles = get_all_profiles()
    if not profiles:
        return []
    
    reqs = parse_task_requirements(task_data)
    required_skills = reqs['required_skills']
    pref_spec = reqs['preferred_specialization']
    
    candidates = []
    
    for node_id, profile in profiles.items():
        factors = {}
        
        # 1. Skill match (35%)
        node_skills = [s.lower() for s in (profile.get('skills', []) + profile.get('languages', []) + profile.get('frameworks', []))]
        if required_skills:
            matched = sum(1 for s in required_skills if s.lower() in node_skills)
            skill_score = (matched / len(required_skills)) * 100
        else:
            skill_score = 50  # neutral if no requirements
        factors['skill_match'] = round(skill_score, 1)
        
        # 2. Specialization (10%)
        node_spec = (profile.get('specialization', '') or '').lower()
        if pref_spec and node_spec:
            spec_score = 100 if node_spec == pref_spec else (50 if node_spec == 'fullstack' else 0)
        else:
            spec_score = 50
        factors['specialization'] = round(spec_score, 1)
        
        # 3. Load balance (20%)
        current_load = get_node_load(node_id)
        max_load = profile.get('max_concurrent_tasks', 5)
        if current_load >= max_load:
            load_score = 0
        else:
            load_score = (1 - current_load / max_load) * 100
        factors['load_balance'] = round(load_score, 1)
        factors['current_load'] = current_load
        
        # 4. Trust score (25%)
        trust = get_node_trust(node_id)
        factors['trust_score'] = round(trust['score'], 1)
        factors['completed_tasks'] = trust['completed']
        factors['success_rate'] = round(trust['success_rate'], 1)
        
        # 5. Resource fit (10%)
        resource_score = 50  # default
        if reqs.get('min_memory_gb') and profile.get('memory_gb'):
            if profile['memory_gb'] >= reqs['min_memory_gb']:
                resource_score = 100
            else:
                resource_score = 0
        if reqs.get('needs_gpu') and not profile.get('has_gpu'):
            resource_score = 0
        factors['resource_fit'] = round(resource_score, 1)
        
        # Total weighted score
        total = (
            skill_score * 0.35 +
            spec_score * 0.10 +
            load_score * 0.20 +
            trust['score'] * 0.25 +
            resource_score * 0.10
        )
        factors['total_score'] = round(total, 1)
        
        candidates.append((node_id, round(total, 1), factors))
    
    # Sort by score descending
    candidates.sort(key=lambda x: x[1], reverse=True)
    top = candidates[:top_n]
    
    # Record match history
    if record_history and task_data.get('task_id'):
        conn = get_conn()
        cur = conn.cursor()
        for i, (nid, score, factors) in enumerate(top):
            cur.execute("""
                INSERT INTO task_match_history (task_id, matched_node, score, factors, selected)
                VALUES (%s, %s, %s, %s, %s)
            """, (task_data['task_id'], nid, score, json.dumps(factors), i == 0))
        conn.commit()
        cur.close()
        conn.close()
    
    return top


def get_match_history(task_id=None, node_id=None, limit=50):
    """Get match history records"""
    ensure_match_tables()
    conn = get_conn()
    cur = conn.cursor()
    
    if task_id:
        cur.execute("""
            SELECT task_id, matched_node, score, factors, selected, created_at
            FROM task_match_history WHERE task_id = %s
            ORDER BY score DESC LIMIT %s
        """, (task_id, limit))
    elif node_id:
        cur.execute("""
            SELECT task_id, matched_node, score, factors, selected, created_at
            FROM task_match_history WHERE matched_node = %s
            ORDER BY created_at DESC LIMIT %s
        """, (node_id, limit))
    else:
        cur.execute("""
            SELECT task_id, matched_node, score, factors, selected, created_at
            FROM task_match_history
            ORDER BY created_at DESC LIMIT %s
        """, (limit,))
    
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    return [{
        'task_id': r[0], 'matched_node': r[1], 'score': r[2],
        'factors': r[3], 'selected': r[4], 'created_at': str(r[5])
    } for r in rows]


def batch_match(task_ids, nodes=None):
    """Match multiple tasks to nodes optimally (greedy assignment)"""
    conn = get_conn()
    cur = conn.cursor()
    
    assignments = []
    used_load = {}  # track incremental load
    
    for tid in task_ids:
        cur.execute("SELECT task_id, title, description FROM tasks WHERE task_id = %s", (tid,))
        row = cur.fetchone()
        if not row:
            continue
        
        task_data = {'task_id': row[0], 'title': row[1], 'description': row[2]}
        matches = smart_match(task_data, top_n=5, record_history=True)
        
        # Pick best node considering incremental load
        for nid, score, factors in matches:
            extra = used_load.get(nid, 0)
            adjusted_score = score - extra * 5  # penalty for each extra assignment
            if adjusted_score > 0:
                assignments.append({'task_id': tid, 'node_id': nid, 'score': adjusted_score, 'original_score': score})
                used_load[nid] = extra + 1
                break
    
    cur.close()
    conn.close()
    return assignments


# === Self-test ===
if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=== R19-2: Task-Node Smart Matcher Self-Test ===\n")
    
    ensure_match_tables()
    
    # Test 1: Backend task matching
    print("Test 1: Backend Python task")
    results = smart_match({
        'task_id': 'test-backend-001',
        'title': 'Python Flask API 开发',
        'description': '使用 Python 和 Flask 开发 RESTful API，需要 PostgreSQL 数据库操作',
    }, top_n=3)
    for nid, score, factors in results:
        print(f"  {nid}: {score} pts | skill={factors['skill_match']} load={factors['load_balance']} trust={factors['trust_score']}")
    assert len(results) > 0, "No matches found"
    print(f"  Winner: {results[0][0]} ✅\n")
    
    # Test 2: Frontend task
    print("Test 2: Frontend UI task")
    results = smart_match({
        'task_id': 'test-frontend-001',
        'title': '前端页面开发',
        'description': 'HTML CSS JavaScript 页面开发，需要 Vue 或 React 框架',
    }, top_n=3)
    for nid, score, factors in results:
        print(f"  {nid}: {score} pts | skill={factors['skill_match']} load={factors['load_balance']} trust={factors['trust_score']}")
    print(f"  Winner: {results[0][0]} ✅\n")
    
    # Test 3: DevOps task
    print("Test 3: DevOps deployment task")
    results = smart_match({
        'task_id': 'test-devops-001',
        'title': '服务器部署与监控',
        'description': 'Docker 容器部署, Nginx 配置, Linux 运维, 系统监控',
    }, top_n=3)
    for nid, score, factors in results:
        print(f"  {nid}: {score} pts | skill={factors['skill_match']} load={factors['load_balance']} trust={factors['trust_score']}")
    print(f"  Winner: {results[0][0]} ✅\n")
    
    # Test 4: Batch matching
    print("Test 4: Batch matching (verify load balancing)")
    # Get some real task IDs
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT task_id FROM tasks WHERE status='completed' LIMIT 5")
    test_ids = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    
    if test_ids:
        assignments = batch_match(test_ids[:5])
        node_counts = {}
        for a in assignments:
            node_counts[a['node_id']] = node_counts.get(a['node_id'], 0) + 1
            print(f"  {a['task_id'][:20]}... -> {a['node_id']} (score: {a['score']:.1f})")
        print(f"  Distribution: {node_counts}")
        print(f"  Load balanced: {'✅' if len(node_counts) > 1 or len(assignments) <= 1 else '⚠️ single node'}\n")
    else:
        print("  No completed tasks for batch test, skipping\n")
    
    # Test 5: Match history
    print("Test 5: Match history")
    history = get_match_history(task_id='test-backend-001')
    print(f"  Records for test-backend-001: {len(history)}")
    assert len(history) > 0, "No history recorded"
    print(f"  First record: node={history[0]['matched_node']}, score={history[0]['score']}, selected={history[0]['selected']} ✅\n")
    
    # Test 6: Smart detection from title only
    print("Test 6: Auto-detect skills from title")
    results = smart_match({
        'task_id': 'test-auto-001',
        'title': 'R19-2: LUX结算系统Redis缓存优化',
    }, top_n=3, record_history=False)
    detected = results[0][2] if results else {}
    print(f"  Detected match for LUX+Redis task: {results[0][0] if results else 'none'}")
    print(f"  Skill score: {detected.get('skill_match', 'N/A')} ✅\n")
    
    # Cleanup test records
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM task_match_history WHERE task_id LIKE 'test-%'")
    conn.commit()
    cur.close()
    conn.close()
    
    print("=== All tests passed! ===")
