# -*- coding: utf-8 -*-
"""
R19-1: 节点能力画像系统
1. 节点能力注册表（CPU/内存/技能/语言）
2. 基于画像的任务-节点匹配算法
3. 画像更新 API
4. 自测：注册 3 个不同能力节点，验证匹配正确
"""
import psycopg2
import json
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

PG_CONFIG = {
    'host': 'localhost', 'port': 5432, 'dbname': 'matrix',
    'user': 'postgres', 'password': 'skycetus', 'connect_timeout': 5
}

def _conn():
    c = psycopg2.connect(**PG_CONFIG)
    c.autocommit = True
    return c


# ============================================================
# Schema: node_profiles table
# ============================================================
def ensure_node_profiles_table():
    """创建节点能力画像表"""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS node_profiles (
            node_id VARCHAR(255) PRIMARY KEY,
            cpu_cores INTEGER DEFAULT 0,
            memory_gb NUMERIC(8,2) DEFAULT 0,
            gpu VARCHAR(255) DEFAULT '',
            os VARCHAR(100) DEFAULT '',
            skills TEXT[] DEFAULT '{}',
            languages TEXT[] DEFAULT '{}',
            frameworks TEXT[] DEFAULT '{}',
            max_concurrent INTEGER DEFAULT 1,
            avg_completion_time NUMERIC(10,2) DEFAULT 0,
            success_rate NUMERIC(5,2) DEFAULT 100.0,
            total_tasks_completed INTEGER DEFAULT 0,
            specialization VARCHAR(255) DEFAULT 'general',
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        )
    """)
    conn.close()
    print("  node_profiles table ensured ✅")


# ============================================================
# Profile CRUD
# ============================================================
def upsert_node_profile(node_id, profile_data):
    """创建或更新节点画像"""
    conn = _conn()
    cur = conn.cursor()
    
    fields = {
        'cpu_cores': profile_data.get('cpu_cores', 0),
        'memory_gb': profile_data.get('memory_gb', 0),
        'gpu': profile_data.get('gpu', ''),
        'os': profile_data.get('os', ''),
        'skills': profile_data.get('skills', []),
        'languages': profile_data.get('languages', []),
        'frameworks': profile_data.get('frameworks', []),
        'max_concurrent': profile_data.get('max_concurrent', 1),
        'specialization': profile_data.get('specialization', 'general'),
        'metadata': json.dumps(profile_data.get('metadata', {})),
    }
    
    cur.execute("""
        INSERT INTO node_profiles (node_id, cpu_cores, memory_gb, gpu, os, 
                                   skills, languages, frameworks, max_concurrent, 
                                   specialization, metadata, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
        ON CONFLICT (node_id) DO UPDATE SET
            cpu_cores = EXCLUDED.cpu_cores,
            memory_gb = EXCLUDED.memory_gb,
            gpu = EXCLUDED.gpu,
            os = EXCLUDED.os,
            skills = EXCLUDED.skills,
            languages = EXCLUDED.languages,
            frameworks = EXCLUDED.frameworks,
            max_concurrent = EXCLUDED.max_concurrent,
            specialization = EXCLUDED.specialization,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        RETURNING node_id
    """, (node_id, fields['cpu_cores'], fields['memory_gb'], fields['gpu'],
          fields['os'], fields['skills'], fields['languages'], fields['frameworks'],
          fields['max_concurrent'], fields['specialization'], fields['metadata']))
    
    result = cur.fetchone()
    conn.close()
    return result[0] if result else None


def get_node_profile(node_id):
    """获取节点画像"""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM node_profiles WHERE node_id = %s", (node_id,))
    columns = [desc[0] for desc in cur.description]
    row = cur.fetchone()
    conn.close()
    if row:
        profile = dict(zip(columns, row))
        # Convert datetime to string
        for k, v in profile.items():
            if isinstance(v, datetime):
                profile[k] = v.isoformat()
        return profile
    return None


def list_node_profiles():
    """列出所有节点画像"""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT node_id, cpu_cores, memory_gb, gpu, skills, languages, specialization, success_rate, total_tasks_completed FROM node_profiles ORDER BY total_tasks_completed DESC")
    rows = cur.fetchall()
    conn.close()
    return [{'node_id': r[0], 'cpu_cores': r[1], 'memory_gb': float(r[2]), 'gpu': r[3],
             'skills': r[4], 'languages': r[5], 'specialization': r[6],
             'success_rate': float(r[7]), 'total_tasks_completed': r[8]} for r in rows]


def update_node_stats(node_id, completed=True):
    """任务完成后更新节点统计"""
    conn = _conn()
    cur = conn.cursor()
    if completed:
        cur.execute("""
            UPDATE node_profiles SET 
                total_tasks_completed = total_tasks_completed + 1,
                success_rate = (success_rate * total_tasks_completed + 100) / (total_tasks_completed + 1),
                updated_at = now()
            WHERE node_id = %s
        """, (node_id,))
    else:
        cur.execute("""
            UPDATE node_profiles SET 
                success_rate = (success_rate * total_tasks_completed) / (total_tasks_completed + 1),
                updated_at = now()
            WHERE node_id = %s
        """, (node_id,))
    conn.close()


# ============================================================
# Task-Node Matching Algorithm
# ============================================================
def match_task_to_nodes(task_requirements, top_n=3):
    """
    基于画像的任务-节点匹配算法。
    task_requirements: {
        'required_skills': ['python', 'docker'],
        'required_languages': ['zh', 'en'],
        'min_memory_gb': 4,
        'min_cpu_cores': 2,
        'needs_gpu': False,
        'preferred_specialization': 'backend',
    }
    Returns: sorted list of (node_id, score, reasons)
    """
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM node_profiles")
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    conn.close()
    
    candidates = []
    
    for row in rows:
        profile = dict(zip(columns, row))
        score = 0
        reasons = []
        disqualified = False
        
        # 1. Skill matching (40% weight)
        req_skills = set(s.lower() for s in task_requirements.get('required_skills', []))
        node_skills = set(s.lower() for s in (profile['skills'] or []))
        if req_skills:
            matched = req_skills & node_skills
            skill_score = len(matched) / len(req_skills) * 40
            score += skill_score
            if matched:
                reasons.append(f'skills: {",".join(matched)}')
            if req_skills - node_skills:
                reasons.append(f'missing: {",".join(req_skills - node_skills)}')
        else:
            score += 20  # No skill requirement = partial match
        
        # 2. Language matching (10% weight)
        req_langs = set(s.lower() for s in task_requirements.get('required_languages', []))
        node_langs = set(s.lower() for s in (profile['languages'] or []))
        if req_langs:
            lang_match = len(req_langs & node_langs) / len(req_langs) * 10
            score += lang_match
        else:
            score += 5
        
        # 3. Resource matching (20% weight)
        min_mem = task_requirements.get('min_memory_gb', 0)
        min_cpu = task_requirements.get('min_cpu_cores', 0)
        if min_mem > 0 and float(profile['memory_gb']) < min_mem:
            disqualified = True
            reasons.append(f'mem {profile["memory_gb"]}GB < {min_mem}GB required')
        elif min_mem > 0:
            score += 10
        else:
            score += 10
            
        if min_cpu > 0 and profile['cpu_cores'] < min_cpu:
            disqualified = True
            reasons.append(f'cpu {profile["cpu_cores"]} < {min_cpu} required')
        elif min_cpu > 0:
            score += 10
        else:
            score += 10
        
        # 4. GPU matching (5% weight)
        if task_requirements.get('needs_gpu') and not profile.get('gpu'):
            disqualified = True
            reasons.append('GPU required but not available')
        elif profile.get('gpu'):
            score += 5
            reasons.append(f'GPU: {profile["gpu"]}')
        
        # 5. Specialization bonus (10% weight)
        pref_spec = task_requirements.get('preferred_specialization', '')
        if pref_spec and profile.get('specialization') == pref_spec:
            score += 10
            reasons.append(f'specialization match: {pref_spec}')
        
        # 6. Track record (15% weight)
        success_rate = float(profile.get('success_rate', 0))
        completed = profile.get('total_tasks_completed', 0)
        track_score = min(success_rate / 100 * 10, 10) + min(completed / 50 * 5, 5)
        score += track_score
        
        if not disqualified:
            candidates.append((profile['node_id'], round(score, 1), reasons))
    
    # Sort by score descending
    candidates.sort(key=lambda x: -x[1])
    return candidates[:top_n]


# ============================================================
# Self-test
# ============================================================
def run_self_test():
    print('=' * 60)
    print('R19-1 Self-Test: 节点能力画像系统')
    print('=' * 60)
    
    # 1. Create table
    print('\n[1] 创建 node_profiles 表:')
    ensure_node_profiles_table()
    
    # 2. Register 3 different capability nodes
    print('\n[2] 注册 3 个不同能力节点:')
    
    profiles = [
        {
            'node_id': 'lucas',
            'profile': {
                'cpu_cores': 2, 'memory_gb': 4, 'gpu': '', 'os': 'Windows Server 2019',
                'skills': ['python', 'flask', 'postgresql', 'redis', 'nginx', 'html', 'css', 'javascript'],
                'languages': ['zh', 'en'],
                'frameworks': ['flask', 'fastapi', 'three.js'],
                'max_concurrent': 3,
                'specialization': 'backend',
            }
        },
        {
            'node_id': 'etern',
            'profile': {
                'cpu_cores': 8, 'memory_gb': 16, 'gpu': 'RTX 4060',
                'os': 'Ubuntu 22.04',
                'skills': ['python', 'docker', 'kubernetes', 'terraform', 'postgresql', 'monitoring'],
                'languages': ['zh', 'en'],
                'frameworks': ['django', 'celery', 'prometheus'],
                'max_concurrent': 5,
                'specialization': 'devops',
            }
        },
        {
            'node_id': 'spark1',
            'profile': {
                'cpu_cores': 4, 'memory_gb': 8, 'gpu': '', 'os': 'macOS',
                'skills': ['python', 'react', 'typescript', 'node.js', 'figma'],
                'languages': ['zh', 'en', 'ja'],
                'frameworks': ['react', 'next.js', 'tailwind'],
                'max_concurrent': 2,
                'specialization': 'frontend',
            }
        }
    ]
    
    for p in profiles:
        result = upsert_node_profile(p['node_id'], p['profile'])
        print(f"  {p['node_id']}: registered ✅ (spec: {p['profile']['specialization']})")
    
    # 3. Verify profiles
    print('\n[3] 画像读取验证:')
    for p in profiles:
        profile = get_node_profile(p['node_id'])
        if profile:
            print(f"  {p['node_id']}: CPU={profile['cpu_cores']}, MEM={profile['memory_gb']}GB, "
                  f"skills={len(profile['skills'])}, spec={profile['specialization']} ✅")
        else:
            print(f"  {p['node_id']}: NOT FOUND ❌")
    
    # 4. Test matching algorithm
    print('\n[4] 匹配算法测试:')
    
    # Test A: Backend task needing Python + PostgreSQL
    print('\n  Test A: Backend task (python + postgresql):')
    matches_a = match_task_to_nodes({
        'required_skills': ['python', 'postgresql'],
        'preferred_specialization': 'backend',
    })
    for nid, score, reasons in matches_a:
        print(f"    {nid}: score={score} {reasons}")
    match_a_ok = matches_a[0][0] == 'lucas'
    print(f"    Best match = lucas: {'✅' if match_a_ok else '❌'}")
    
    # Test B: DevOps task needing Docker + GPU
    print('\n  Test B: DevOps task (docker + GPU):')
    matches_b = match_task_to_nodes({
        'required_skills': ['docker', 'kubernetes'],
        'needs_gpu': True,
        'preferred_specialization': 'devops',
    })
    for nid, score, reasons in matches_b:
        print(f"    {nid}: score={score} {reasons}")
    match_b_ok = matches_b[0][0] == 'etern'
    print(f"    Best match = etern: {'✅' if match_b_ok else '❌'}")
    
    # Test C: Frontend task needing React
    print('\n  Test C: Frontend task (react + typescript):')
    matches_c = match_task_to_nodes({
        'required_skills': ['react', 'typescript'],
        'preferred_specialization': 'frontend',
    })
    for nid, score, reasons in matches_c:
        print(f"    {nid}: score={score} {reasons}")
    match_c_ok = matches_c[0][0] == 'spark1'
    print(f"    Best match = spark1: {'✅' if match_c_ok else '❌'}")
    
    # Test D: High resource requirement
    print('\n  Test D: High resource (8GB RAM, 4 CPU):')
    matches_d = match_task_to_nodes({
        'required_skills': ['python'],
        'min_memory_gb': 8,
        'min_cpu_cores': 4,
    })
    for nid, score, reasons in matches_d:
        print(f"    {nid}: score={score} {reasons}")
    # lucas should be excluded (2 CPU, 4GB)
    d_node_ids = [m[0] for m in matches_d]
    match_d_ok = 'lucas' not in d_node_ids
    print(f"    Lucas excluded (insufficient resources): {'✅' if match_d_ok else '❌'}")
    
    # 5. List all profiles
    print('\n[5] 所有节点画像列表:')
    all_profiles = list_node_profiles()
    for p in all_profiles:
        print(f"  {p['node_id']}: {p['specialization']} | skills={len(p['skills'])} | "
              f"success={p['success_rate']}% | completed={p['total_tasks_completed']}")
    
    all_pass = match_a_ok and match_b_ok and match_c_ok and match_d_ok
    print(f'\n{"=" * 60}')
    print(f'Overall: {"✅ ALL TESTS PASSED" if all_pass else "❌ SOME TESTS FAILED"}')
    print(f'{"=" * 60}')
    return all_pass


if __name__ == '__main__':
    run_self_test()
