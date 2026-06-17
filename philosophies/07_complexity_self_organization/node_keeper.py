# -*- coding: utf-8 -*-
"""
Node Keeper Service - keeps all nodes alive with persistent heartbeat
Runs as a Windows background service / scheduled task
"""
import time, json, urllib.request, sqlite3, os, sys, logging
from datetime import datetime, timedelta

HUB_URL = 'http://127.0.0.1:19104'
SECRET = 'skycetus-shared-secret'
MATRIX_DB = r'D:\ClawMatrix\matrix.sqlite'
LOG_FILE = r'D:\ClawMatrix\node_keeper.log'
HEARTBEAT_INTERVAL = 120  # 2 minutes

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def send_heartbeat(node_id, name=''):
    """Send heartbeat for a node"""
    try:
        data = json.dumps({'node_id': node_id, 'status': 'online'}).encode()
        req = urllib.request.Request(
            f'{HUB_URL}/api/v1/node/heartbeat',
            data=data, method='POST'
        )
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-Matrix-Secret', SECRET)
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status == 200
    except Exception as e:
        logging.warning(f'Heartbeat failed for {node_id}: {e}')
        return False

def get_all_nodes():
    """Get all registered nodes from DB"""
    try:
        db = sqlite3.connect(MATRIX_DB)
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT id, name, status, last_heartbeat FROM nodes").fetchall()
        db.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(f'DB error: {e}')
        return []

def check_pending_tasks():
    """Check for pending tasks and try to auto-assign"""
    try:
        db = sqlite3.connect(MATRIX_DB)
        db.row_factory = sqlite3.Row
        pending = db.execute("SELECT id, title, task_type FROM tasks WHERE status='pending' LIMIT 10").fetchall()
        online = db.execute("SELECT id, name FROM nodes WHERE status='online'").fetchall()
        db.close()
        return [dict(p) for p in pending], [dict(o) for o in online]
    except:
        return [], []

def auto_assign_tasks(pending, online_nodes):
    """Auto-assign pending tasks to online nodes"""
    if not pending or not online_nodes:
        return 0
    
    assigned = 0
    db = sqlite3.connect(MATRIX_DB)
    for i, task in enumerate(pending):
        node = online_nodes[i % len(online_nodes)]
        try:
            db.execute(
                "UPDATE tasks SET status='assigned', assigned_node=? WHERE id=? AND status='pending'",
                (node['id'], task['id'])
            )
            assigned += 1
            logging.info(f'Auto-assigned {task["id"][:16]} -> {node["name"]}')
        except:
            pass
    db.commit()
    db.close()
    return assigned

def run_keeper():
    """Main keeper loop"""
    logging.info('=== Node Keeper started ===')
    print(f'Node Keeper started at {datetime.now()}')
    print(f'Hub: {HUB_URL}')
    print(f'Interval: {HEARTBEAT_INTERVAL}s')
    
    cycle = 0
    while True:
        cycle += 1
        nodes = get_all_nodes()
        online_count = 0
        
        for node in nodes:
            ok = send_heartbeat(node['id'], node.get('name', ''))
            if ok:
                online_count += 1
        
        # Check and auto-assign tasks every 5 cycles (10 min)
        if cycle % 5 == 0:
            pending, online = check_pending_tasks()
            if pending:
                count = auto_assign_tasks(pending, online)
                if count > 0:
                    logging.info(f'Auto-assigned {count} tasks')
                    print(f'[{datetime.now().strftime("%H:%M")}] Auto-assigned {count} tasks')
        
        if cycle % 10 == 0:  # Log summary every 20 min
            logging.info(f'Cycle {cycle}: {online_count}/{len(nodes)} nodes online')
        
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Heartbeat cycle {cycle}: {online_count}/{len(nodes)} nodes online')
        time.sleep(HEARTBEAT_INTERVAL)

if __name__ == '__main__':
    if '--once' in sys.argv:
        # Single run mode
        nodes = get_all_nodes()
        for node in nodes:
            ok = send_heartbeat(node['id'], node.get('name', ''))
            status = 'OK' if ok else 'FAIL'
            print(f'  {status} {node["name"]} ({node["id"]})')
        pending, online = check_pending_tasks()
        print(f'\nPending tasks: {len(pending)}, Online nodes: {len(online)}')
        if pending:
            count = auto_assign_tasks(pending, online)
            print(f'Auto-assigned: {count}')
    else:
        run_keeper()
