import sqlite3
import os
import requests

print('=' * 60)
print('REBUILD TASKS ACCEPTANCE CHECK')
print('=' * 60)

# 1. 检查数据库迁移 (REBUILD-003)
print('\n[REBUILD-003] Database Migration:')
try:
    conn = sqlite3.connect('C:\\SkyCetus-2.0\\skycetus.sqlite')
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cur.fetchall()]
    print(f'  Tables: {len(tables)}')
    
    # 检查关键表
    key_tables = ['users', 'ai_residents', 'relations', 'lux_accounts', 'tasks', 'invite_codes']
    for t in key_tables:
        status = '[OK]' if t in tables else '[MISSING]'
        print(f'    {status} {t}')
    conn.close()
except Exception as e:
    print(f'  [FAIL] {e}')

# 2. 检查用户系统 (REBUILD-005)
print('\n[REBUILD-005] User System:')
try:
    conn = sqlite3.connect('C:\\SkyCetus-2.0\\skycetus.sqlite')
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    print(f'  Users count: {user_count}')
    
    # 检查用户字段
    cur.execute("PRAGMA table_info(users)")
    columns = [c[1] for c in cur.fetchall()]
    print(f'  Columns: {len(columns)}')
    key_cols = ['id', 'username', 'email', 'password_hash', 'created_at']
    for c in key_cols:
        status = '[OK]' if c in columns else '[MISSING]'
        print(f'    {status} {c}')
    conn.close()
except Exception as e:
    print(f'  [FAIL] {e}')

# 3. 检查 AI 居民系统 (REBUILD-006)
print('\n[REBUILD-006] AI Residents System:')
try:
    conn = sqlite3.connect('C:\\SkyCetus-2.0\\skycetus.sqlite')
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ai_residents")
    ai_count = cur.fetchone()[0]
    print(f'  AI Residents count: {ai_count}')
    
    # 检查 AI 字段
    cur.execute("PRAGMA table_info(ai_residents)")
    columns = [c[1] for c in cur.fetchall()]
    print(f'  Columns: {len(columns)}')
    key_cols = ['id', 'name', 'description', 'lux', 'owner_id']
    for c in key_cols:
        status = '[OK]' if c in columns else '[MISSING]'
        print(f'    {status} {c}')
    conn.close()
except Exception as e:
    print(f'  [FAIL] {e}')

# 4. 检查关系系统 (REBUILD-007)
print('\n[REBUILD-007] Relations System:')
try:
    conn = sqlite3.connect('C:\\SkyCetus-2.0\\skycetus.sqlite')
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM relations")
    rel_count = cur.fetchone()[0]
    print(f'  Relations count: {rel_count}')
    
    # 检查关系类型
    cur.execute("SELECT DISTINCT immutable_type FROM relations")
    types = [t[0] for t in cur.fetchall()]
    print(f'  Relation types: {types}')
    conn.close()
except Exception as e:
    print(f'  [FAIL] {e}')

# 5. 检查 Lux 经济 (REBUILD-010)
print('\n[REBUILD-010] Lux Economy:')
try:
    conn = sqlite3.connect('C:\\SkyCetus-2.0\\skycetus.sqlite')
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM lux_accounts")
    acc_count = cur.fetchone()[0]
    print(f'  Lux Accounts count: {acc_count}')
    
    cur.execute("SELECT SUM(balance) FROM lux_accounts")
    total_lux = cur.fetchone()[0]
    print(f'  Total Lux in circulation: {total_lux}')
    
    cur.execute("SELECT COUNT(*) FROM lux_transactions")
    tx_count = cur.fetchone()[0]
    print(f'  Transactions count: {tx_count}')
    conn.close()
except Exception as e:
    print(f'  [FAIL] {e}')

# 6. 检查任务系统 (REBUILD-008)
print('\n[REBUILD-008] Task System:')
try:
    conn = sqlite3.connect('D:\\ClawMatrix\\matrix.sqlite')
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tasks")
    task_count = cur.fetchone()[0]
    print(f'  Tasks count: {task_count}')
    
    cur.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
    status_counts = cur.fetchall()
    for status, count in status_counts:
        print(f'    {status}: {count}')
    conn.close()
except Exception as e:
    print(f'  [FAIL] {e}')

# 7. 检查 OTC 网厅 (REBUILD-011)
print('\n[REBUILD-011] OTC Portal:')
try:
    r = requests.get('http://127.0.0.1:8000/otc-login', timeout=3)
    print(f'  OTC Login Page: [{r.status_code}]')
    
    r = requests.get('http://127.0.0.1:8000/otc-dashboard', timeout=3)
    print(f'  OTC Dashboard: [{r.status_code}]')
    
    r = requests.get('http://127.0.0.1:8000/otc-admin', timeout=3)
    print(f'  OTC Admin: [{r.status_code}]')
except Exception as e:
    print(f'  [FAIL] {e}')

# 8. 检查 3D 城市 (REBUILD-009)
print('\n[REBUILD-009] 3D City:')
try:
    conn = sqlite3.connect('C:\\SkyCetus-2.0\\skycetus.sqlite')
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM city_buildings_v2")
    building_count = cur.fetchone()[0]
    print(f'  Buildings count: {building_count}')
    
    # 检查建筑类型分布
    cur.execute("SELECT type, COUNT(*) FROM city_buildings_v2 GROUP BY type")
    types = cur.fetchall()
    for t, c in types:
        print(f'    {t}: {c}')
    conn.close()
except Exception as e:
    print(f'  [FAIL] {e}')

# 9. 检查关键页面
print('\n[REBUILD-013] UI/UX - Critical Pages:')
pages = [
    ('Home', 'http://127.0.0.1:5003/'),
    ('Profile', 'http://127.0.0.1:5003/profile'),
    ('Rebuild Kanban', 'http://127.0.0.1:5003/rebuild-kanban'),
    ('Hub', 'http://127.0.0.1:5003/hub'),
    ('Missions', 'http://127.0.0.1:5003/missions'),
]
for name, url in pages:
    try:
        r = requests.get(url, timeout=3)
        status = '[OK]' if r.status_code == 200 else f'[WARN {r.status_code}]'
        print(f'  {status} {name}')
    except Exception as e:
        print(f'  [FAIL] {name}: {e}')

# 10. 检查功能测试 (REBUILD-014)
print('\n[REBUILD-014] Functional Tests:')
try:
    # 测试 API
    r = requests.get('http://127.0.0.1:5003/api/health', timeout=3)
    if r.status_code == 200:
        data = r.json()
        print(f'  Health API: [OK] {data}')
    else:
        print(f'  Health API: [WARN {r.status_code}]')
except Exception as e:
    print(f'  [FAIL] Health API: {e}')

# 11. 检查性能测试 (REBUILD-015)
print('\n[REBUILD-015] Performance Tests:')
import time
try:
    start = time.time()
    r = requests.get('http://127.0.0.1:5003/', timeout=5)
    elapsed = time.time() - start
    status = '[OK]' if elapsed < 1 else '[SLOW]'
    print(f'  {status} Home page load: {elapsed*1000:.0f}ms')
except Exception as e:
    print(f'  [FAIL] {e}')

print('\n' + '=' * 60)
print('ACCEPTANCE CHECK COMPLETE')
print('=' * 60)
