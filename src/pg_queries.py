# -*- coding: utf-8 -*-
"""
PostgreSQL read queries for Hub V1.5
Hub 读路径：所有列表/详情查询走 PostgreSQL
Redis 保留为：任务队列（BRPOP拉取）+ Pub/Sub 通知
"""
import psycopg2
import json
import hashlib
from datetime import datetime

PG_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'matrix',
    'user': 'postgres',
    'password': 'skycetus',
    'connect_timeout': 5
}

def _conn():
    c = psycopg2.connect(**PG_CONFIG)
    c.autocommit = True
    return c

def _row_to_task(row, columns):
    """Convert a DB row + column names to a task dict"""
    t = {}
    for i, col in enumerate(columns):
        val = row[i]
        if isinstance(val, datetime):
            val = val.isoformat()
        # Map PG column names to Hub API names
        if col == 'task_id':
            t['id'] = val or ''
            t['task_id'] = val or ''  # Also expose as task_id for API consumers
        elif col == 'created_by':
            t['creator_node'] = val or ''
        elif col == 'assigned_to':
            t['assigned_node'] = val or ''
        elif col == 'parent_task_id':
            t['parent_id'] = val or ''
        else:
            t[col] = val
    return t


# ============================================================
# Task queries
# ============================================================

def pg_list_tasks(status=None, node_id=None, limit=50):
    """List tasks from PostgreSQL, replaces Redis list_tasks"""
    conn = _conn()
    cur = conn.cursor()
    
    query = """SELECT task_id, title, description, status, priority,
                      lux_reward, parent_task_id, root_task_id,
                      created_by, assigned_to,
                      created_at, updated_at, completed_at
               FROM tasks WHERE 1=1"""
    params = []
    
    if status:
        query += " AND status = %s"
        params.append(status)
    if node_id:
        query += " AND (created_by = %s OR assigned_to = %s)"
        params.extend([node_id, node_id])
    
    # v1.6 fix: when no status filter, show pending/assigned first (so they don't get buried by completed)
    if not status:
        query += " ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'assigned' THEN 1 WHEN 'completed' THEN 2 ELSE 3 END, created_at DESC LIMIT %s"
    else:
        query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    
    cur.execute(query, params)
    columns = [desc[0] for desc in cur.description]
    tasks = [_row_to_task(row, columns) for row in cur.fetchall()]
    conn.close()
    return tasks


def pg_get_task(task_id):
    """Get a single task by ID from PostgreSQL"""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""SELECT task_id, title, description, status, priority,
                          lux_reward, parent_task_id, root_task_id,
                          created_by, assigned_to,
                          created_at, updated_at, completed_at
                   FROM tasks WHERE task_id = %s""", (task_id,))
    columns = [desc[0] for desc in cur.description]
    row = cur.fetchone()
    conn.close()
    if row:
        return _row_to_task(row, columns)
    return None


def pg_get_missions(limit_completed=200, limit_pending=50, limit_assigned=50):
    """Get missions data for dashboard, replaces Redis get_missions"""
    conn = _conn()
    cur = conn.cursor()
    
    columns = ['task_id', 'title', 'description', 'status', 'priority',
               'lux_reward', 'parent_task_id', 'created_by', 'assigned_to',
               'created_at', 'completed_at']
    col_str = ', '.join(columns)
    
    # Completed
    cur.execute(f"SELECT {col_str} FROM tasks WHERE status='completed' ORDER BY completed_at DESC LIMIT %s",
                (limit_completed,))
    completed = [_row_to_task(r, columns) for r in cur.fetchall()]
    
    # Assigned
    cur.execute(f"SELECT {col_str} FROM tasks WHERE status='assigned' ORDER BY created_at DESC LIMIT %s",
                (limit_assigned,))
    assigned = [_row_to_task(r, columns) for r in cur.fetchall()]
    
    # Pending
    cur.execute(f"SELECT {col_str} FROM tasks WHERE status='pending' ORDER BY created_at ASC LIMIT %s",
                (limit_pending,))
    pending = [_row_to_task(r, columns) for r in cur.fetchall()]
    
    # Stats
    cur.execute("""SELECT 
        COUNT(*) FILTER (WHERE status='completed') as completed_count,
        COUNT(*) FILTER (WHERE status='assigned') as assigned_count,
        COUNT(*) FILTER (WHERE status='pending') as pending_count,
        COALESCE(SUM(lux_reward) FILTER (WHERE status='completed'), 0) as lux_distributed
    FROM tasks""")
    stats_row = cur.fetchone()
    
    # Node count
    cur.execute("SELECT COUNT(*) FROM nodes")
    node_count = cur.fetchone()[0]
    
    conn.close()
    
    return {
        'completed': completed,
        'assigned': assigned,
        'pending': pending,
        'stats': {
            'completed': stats_row[0],
            'assigned': stats_row[1],
            'pending': stats_row[2],
            'lux_total': stats_row[3],
            'nodes': node_count,
        }
    }


def pg_update_task_status(task_id, status, result=None, error=None, assigned_to=None):
    """Update task status in PostgreSQL"""
    conn = _conn()
    cur = conn.cursor()
    
    sets = ["status = %s", "updated_at = now()"]
    params = [status]
    
    if status == 'completed' or status == 'failed':
        sets.append("completed_at = now()")
    if result is not None:
        sets.append("description = COALESCE(description, '') || '' ")  # keep description
    if assigned_to:
        sets.append("assigned_to = %s")
        params.append(assigned_to)
        sets.append("assigned_at = now()")
    if status == 'pending':
        sets.append("assigned_to = NULL")
        sets.append("assigned_at = NULL")
    
    params.append(task_id)
    cur.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE task_id = %s", params)
    affected = cur.rowcount
    conn.close()
    return affected > 0


def pg_complete_and_pay_lux(task_id, assigned_node, result='', error='', full_result=None):
    """
    Complete task + pay lux_reward to the assigned node.
    full_result: JSON object with output, artifacts, quality_score, etc.
    Returns (success, lux_paid, message)
    """
    import psycopg2.extras
    conn = _conn()
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        status = 'failed' if error else 'completed'
        
        # 1. Get task and its lux_reward
        cur.execute("SELECT lux_reward, status FROM tasks WHERE task_id = %s FOR UPDATE", (task_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            conn.close()
            return False, 0, 'Task not found'
        
        lux_reward = row[0] or 0
        current_status = row[1]
        
        if current_status in ('completed', 'failed'):
            conn.rollback()
            conn.close()
            return False, 0, f'Task already {current_status}'
        
        # 2. Update task status and result
        # v1.5+: Store full_result as JSONB if provided
        if full_result:
            cur.execute("""UPDATE tasks 
                           SET status=%s, updated_at=now(), completed_at=now(),
                               result=%s, result_score=%s, result_reviewed='pending'
                           WHERE task_id=%s""", 
                        (status, psycopg2.extras.Json(full_result), 
                         full_result.get('quality_score'), task_id))
        else:
            cur.execute("""UPDATE tasks SET status=%s, updated_at=now(), completed_at=now()
                           WHERE task_id=%s""", (status, task_id))
        
        # 3. Pay Lux only if completed (not failed) and reward > 0
        lux_paid = 0
        if status == 'completed' and lux_reward > 0 and assigned_node:
            # Check if lux_ledger table exists, if not create it
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lux_ledger (
                    id SERIAL PRIMARY KEY,
                    node_id VARCHAR(255) NOT NULL,
                    amount NUMERIC(12,2) NOT NULL,
                    tx_type VARCHAR(50) NOT NULL,
                    task_id VARCHAR(255) DEFAULT '',
                    balance_after NUMERIC(12,2) DEFAULT 0,
                    reason TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT now()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lux_accounts (
                    node_id VARCHAR(255) PRIMARY KEY,
                    balance NUMERIC(12,2) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT now(),
                    updated_at TIMESTAMP DEFAULT now()
                )
            """)
            
            # Upsert account balance
            cur.execute("""
                INSERT INTO lux_accounts (node_id, balance, created_at, updated_at)
                VALUES (%s, %s, now(), now())
                ON CONFLICT (node_id) DO UPDATE SET
                    balance = lux_accounts.balance + EXCLUDED.balance,
                    updated_at = now()
                RETURNING balance
            """, (assigned_node, lux_reward))
            new_balance = cur.fetchone()[0]
            
            # Get previous hash for chain
            cur.execute("SELECT tx_hash FROM lux_ledger ORDER BY id DESC LIMIT 1")
            prev_row = cur.fetchone()
            prev_hash = prev_row[0] if prev_row and prev_row[0] else '0' * 64

            # Build hash payload
            hash_payload = json.dumps({
                'node_id': assigned_node,
                'amount': float(lux_reward),
                'tx_type': 'task_reward',
                'task_id': task_id,
                'balance_after': float(new_balance),
                'prev_hash': prev_hash
            }, sort_keys=True)
            tx_hash = hashlib.sha256(hash_payload.encode()).hexdigest()

            # Record transaction with hash chain
            cur.execute("""
                INSERT INTO lux_ledger (node_id, amount, tx_type, task_id, balance_after, reason, tx_hash, prev_hash)
                VALUES (%s, %s, 'task_reward', %s, %s, %s, %s, %s)
            """, (assigned_node, lux_reward, task_id, new_balance,
                  f'Task completed: {task_id}', tx_hash, prev_hash))
            
            lux_paid = lux_reward
        
        conn.commit()
        conn.close()
        return True, lux_paid, f'Task {status}, Lux paid: {lux_paid}'
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, 0, str(e)


def pg_get_node_lux(node_id):
    """Get a node's Lux balance"""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM lux_accounts WHERE node_id = %s", (node_id,))
    row = cur.fetchone()
    conn.close()
    return float(row[0]) if row else 0.0


def pg_get_lux_leaderboard(limit=20):
    """Get Lux leaderboard"""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""SELECT la.node_id, la.balance, n.name 
                   FROM lux_accounts la
                   LEFT JOIN nodes n ON la.node_id = n.node_id
                   ORDER BY la.balance DESC LIMIT %s""", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [{'node_id': r[0], 'balance': float(r[1]), 'name': r[2] or r[0]} for r in rows]


# ============================================================
# LUX Transfer (R18-3)
# ============================================================

def pg_transfer_lux(from_node, to_node, amount, reason='transfer'):
    """
    跨节点 LUX 转账（原子事务 + hash chain）。
    Returns: (success: bool, error_code: str|None, message: str)
    Error codes: INSUFFICIENT_BALANCE, INVALID_AMOUNT, SAME_NODE, NODE_NOT_FOUND
    """
    if amount <= 0:
        return False, 'INVALID_AMOUNT', f'Amount must be positive, got {amount}'
    if from_node == to_node:
        return False, 'SAME_NODE', 'Cannot transfer to self'

    conn = _conn()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Lock sender account
        cur.execute("SELECT balance FROM lux_accounts WHERE node_id = %s FOR UPDATE", (from_node,))
        sender = cur.fetchone()
        if not sender:
            conn.rollback(); conn.close()
            return False, 'NODE_NOT_FOUND', f'Sender {from_node} has no LUX account'

        sender_balance = float(sender[0])
        if sender_balance < amount:
            conn.rollback(); conn.close()
            return False, 'INSUFFICIENT_BALANCE', f'{from_node} balance {sender_balance} < {amount}'

        # Deduct from sender
        new_sender_balance = sender_balance - amount
        cur.execute("UPDATE lux_accounts SET balance = %s, updated_at = now() WHERE node_id = %s",
                    (new_sender_balance, from_node))

        # Credit receiver (upsert)
        cur.execute("""
            INSERT INTO lux_accounts (node_id, balance, created_at, updated_at)
            VALUES (%s, %s, now(), now())
            ON CONFLICT (node_id) DO UPDATE SET
                balance = lux_accounts.balance + EXCLUDED.balance,
                updated_at = now()
            RETURNING balance
        """, (to_node, amount))
        new_receiver_balance = float(cur.fetchone()[0])

        # Get previous hash for chain
        cur.execute("SELECT tx_hash FROM lux_ledger ORDER BY id DESC LIMIT 1")
        prev_row = cur.fetchone()
        prev_hash = prev_row[0] if prev_row and prev_row[0] else '0' * 64

        # Debit entry
        debit_payload = json.dumps({
            'node_id': from_node, 'amount': -amount, 'tx_type': 'transfer_out',
            'task_id': '', 'balance_after': new_sender_balance, 'prev_hash': prev_hash
        }, sort_keys=True)
        debit_hash = hashlib.sha256(debit_payload.encode()).hexdigest()
        cur.execute("""
            INSERT INTO lux_ledger (node_id, amount, tx_type, task_id, balance_after, reason, tx_hash, prev_hash)
            VALUES (%s, %s, 'transfer_out', '', %s, %s, %s, %s)
        """, (from_node, -amount, new_sender_balance, f'Transfer to {to_node}: {reason}', debit_hash, prev_hash))

        # Credit entry
        credit_payload = json.dumps({
            'node_id': to_node, 'amount': amount, 'tx_type': 'transfer_in',
            'task_id': '', 'balance_after': new_receiver_balance, 'prev_hash': debit_hash
        }, sort_keys=True)
        credit_hash = hashlib.sha256(credit_payload.encode()).hexdigest()
        cur.execute("""
            INSERT INTO lux_ledger (node_id, amount, tx_type, task_id, balance_after, reason, tx_hash, prev_hash)
            VALUES (%s, %s, 'transfer_in', '', %s, %s, %s, %s)
        """, (to_node, amount, new_receiver_balance, f'Transfer from {from_node}: {reason}', credit_hash, debit_hash))

        conn.commit()
        conn.close()
        return True, None, f'Transferred {amount}L: {from_node}({new_sender_balance}L) -> {to_node}({new_receiver_balance}L)'

    except Exception as e:
        conn.rollback(); conn.close()
        return False, 'INTERNAL_ERROR', str(e)


# ============================================================
# LUX Audit Trail Functions
# ============================================================

def pg_audit_full_verify():
    """Verify ALL accounts against ledger + hash chain integrity"""
    conn = _conn()
    cur = conn.cursor()
    # Balance verification
    cur.execute("""
        SELECT la.node_id, la.balance, la.updated_at,
               COALESCE(SUM(ll.amount), 0) as ledger_sum,
               COUNT(ll.id) as tx_count
        FROM lux_accounts la
        LEFT JOIN lux_ledger ll ON la.node_id = ll.node_id
        GROUP BY la.node_id, la.balance, la.updated_at
        ORDER BY la.balance DESC
    """)
    rows = cur.fetchall()
    accounts = [{'node_id': r[0], 'account_balance': float(r[1]), 'ledger_sum': float(r[3]),
             'discrepancy': float(r[1]) - float(r[3]), 'tx_count': r[4],
             'verified': abs(float(r[1]) - float(r[3])) < 0.01} for r in rows]

    # Hash chain verification
    cur.execute("SELECT id, tx_hash, prev_hash FROM lux_ledger ORDER BY id ASC")
    chain = cur.fetchall()
    chain_valid = True
    chain_breaks = []
    for i, entry in enumerate(chain):
        if i == 0:
            if entry[2] and entry[2] != '0' * 64:
                chain_valid = False
                chain_breaks.append(f'Genesis prev_hash invalid at id={entry[0]}')
        else:
            if entry[2] and chain[i-1][1] and entry[2] != chain[i-1][1]:
                chain_valid = False
                chain_breaks.append(f'Chain broken at id={entry[0]}')
    conn.close()
    return {
        'accounts': accounts,
        'chain_length': len(chain),
        'chain_valid': chain_valid,
        'chain_breaks': chain_breaks,
        'all_verified': all(a['verified'] for a in accounts) and chain_valid
    }


def pg_audit_node_history(node_id, limit=50):
    """Get full LUX history for a node"""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""SELECT balance, created_at, updated_at FROM lux_accounts WHERE node_id = %s""", (node_id,))
    acc = cur.fetchone()
    cur.execute("""
        SELECT id, node_id, amount, tx_type, task_id, balance_after, reason, created_at
        FROM lux_ledger WHERE node_id = %s ORDER BY id DESC LIMIT %s
    """, (node_id, limit))
    rows = cur.fetchall()
    conn.close()
    return {
        'node_id': node_id,
        'current_balance': float(acc[0]) if acc else 0,
        'transactions': [{'id': r[0], 'node_id': r[1], 'amount': r[2], 'tx_type': r[3],
                          'task_id': r[4], 'balance_after': float(r[5]) if r[5] else None,
                          'reason': r[6], 'created_at': r[7].isoformat() if r[7] else None} for r in rows]
    }


def pg_audit_chain_for_task(task_id):
    """Get complete LUX chain for a specific task"""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""SELECT id, node_id, amount, tx_type, task_id, balance_after, reason, created_at
                       FROM lux_ledger WHERE task_id = %s ORDER BY id""", (task_id,))
    rows = cur.fetchall()
    cur.execute("""SELECT title, lux_reward, status, assigned_node, completed_at FROM tasks WHERE id = %s""", (task_id,))
    task_row = cur.fetchone()
    conn.close()
    if not task_row:
        return None
    return {
        'task': {'id': task_id, 'title': task_row[0], 'lux_reward': task_row[1],
                 'status': task_row[2], 'assigned_to': task_row[3],
                 'completed_at': task_row[4].isoformat() if task_row[4] else None},
        'transactions': [{'id': r[0], 'node_id': r[1], 'amount': r[2], 'tx_type': r[3],
                          'task_id': r[4], 'balance_after': float(r[5]) if r[5] else None,
                          'reason': r[6], 'created_at': r[7].isoformat() if r[7] else None} for r in rows]
    }


def pg_audit_lux_flow_summary(days=30):
    """Get LUX flow summary by type and period"""
    conn = _conn()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT tx_type, COUNT(*) as cnt, SUM(amount) as total, AVG(amount) as avg_amt
        FROM lux_ledger WHERE created_at >= NOW() - INTERVAL '{days} days'
        GROUP BY tx_type ORDER BY SUM(amount) DESC
    """)
    by_type = [{'tx_type': r[0], 'count': r[1], 'total': float(r[2]), 'avg': float(r[3]) if r[3] else 0} for r in cur.fetchall()]
    cur.execute(f"""SELECT COUNT(*), SUM(amount), COUNT(DISTINCT node_id)
                       FROM lux_ledger WHERE created_at >= NOW() - INTERVAL '{days} days'""")
    s = cur.fetchone()
    conn.close()
    return {'period_days': days, 'total_txs': s[0], 'total_amount': float(s[1]) if s[1] else 0,
            'active_nodes': s[2], 'by_type': by_type}


# ============================================================
# Test
# ============================================================
if __name__ == '__main__':
    print("Testing pg_queries...")
    tasks = pg_list_tasks(limit=3)
    print(f"list_tasks: {len(tasks)} tasks")
    if tasks:
        print(f"  First: {tasks[0].get('id')} | {tasks[0].get('title','')[:40]} | lux={tasks[0].get('lux_reward')}")
    
    missions = pg_get_missions()
    print(f"\nget_missions stats: {missions['stats']}")
    print(f"  completed: {len(missions['completed'])}, assigned: {len(missions['assigned'])}, pending: {len(missions['pending'])}")
    
    print("\nDone!")


# ============================================================
# Enhanced Task Queries (v1.6 - Etern)
# ============================================================

def pg_list_tasks_enhanced(status=None, creator_node=None, assigned_node=None,
                           date_from=None, date_to=None, limit=50):
    """Enhanced task list with separate creator/assigned filters and date range.
    
    Args:
        status: Filter by task status (pending/assigned/completed)
        creator_node: Filter by creator node ID
        assigned_node: Filter by assigned node ID
        date_from: ISO date string, filter tasks created >= this date
        date_to: ISO date string, filter tasks created <= this date
        limit: Max results (default 50)
    """
    conn = _conn()
    cur = conn.cursor()
    
    query = """SELECT task_id, title, description, status, priority,
                      lux_reward, parent_task_id, root_task_id,
                      created_by, assigned_to,
                      created_at, updated_at, completed_at
               FROM tasks WHERE 1=1"""
    params = []
    
    if status:
        query += " AND status = %s"
        params.append(status)
    if creator_node:
        query += " AND created_by = %s"
        params.append(creator_node)
    if assigned_node:
        query += " AND assigned_to = %s"
        params.append(assigned_node)
    if date_from:
        query += " AND created_at >= %s"
        params.append(date_from)
    if date_to:
        query += " AND created_at <= %s"
        params.append(date_to)
    
    # v1.6 fix: when no status filter, show pending/assigned first (so they don't get buried by completed)
    if not status:
        query += " ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'assigned' THEN 1 WHEN 'completed' THEN 2 ELSE 3 END, created_at DESC LIMIT %s"
    else:
        query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    
    cur.execute(query, params)
    columns = [desc[0] for desc in cur.description]
    tasks = [_row_to_task(row, columns) for row in cur.fetchall()]
    conn.close()
    return tasks


def pg_task_trends(days=30, group_by='day'):
    """Get task completion trends aggregated by day or week.
    
    Args:
        days: Number of days to look back (default 30)
        group_by: 'day' or 'week'
    
    Returns:
        List of dicts with date/period, completed_count, total_lux, node_breakdown
    """
    conn = _conn()
    cur = conn.cursor()
    
    if group_by == 'week':
        date_trunc = 'week'
    else:
        date_trunc = 'day'
    
    # Completion trends
    cur.execute("""
        SELECT date_trunc(%s, completed_at) as period,
               COUNT(*) as completed_count,
               COALESCE(SUM(lux_reward), 0) as total_lux
        FROM tasks
        WHERE status = 'completed'
          AND completed_at >= NOW() - INTERVAL '%s days'
          AND completed_at IS NOT NULL
        GROUP BY period
        ORDER BY period ASC
    """, (date_trunc, days))
    
    trends = []
    for row in cur.fetchall():
        period_dt = row[0]
        trends.append({
            'period': period_dt.isoformat() if period_dt else None,
            'completed_count': row[1],
            'total_lux': int(row[2]) if row[2] else 0,
        })
    
    # Per-node breakdown for same period
    cur.execute("""
        SELECT date_trunc(%s, completed_at) as period,
               assigned_to as node_id,
               COUNT(*) as count,
               COALESCE(SUM(lux_reward), 0) as lux
        FROM tasks
        WHERE status = 'completed'
          AND completed_at >= NOW() - INTERVAL '%s days'
          AND completed_at IS NOT NULL
          AND assigned_to IS NOT NULL
        GROUP BY period, assigned_to
        ORDER BY period ASC, count DESC
    """, (date_trunc, days))
    
    node_data = {}
    for row in cur.fetchall():
        period_key = row[0].isoformat() if row[0] else ''
        if period_key not in node_data:
            node_data[period_key] = []
        node_data[period_key].append({
            'node_id': row[1],
            'count': row[2],
            'lux': int(row[3]) if row[3] else 0,
        })
    
    # Merge node breakdown into trends
    for t in trends:
        t['nodes'] = node_data.get(t['period'], [])
    
    # Creation trends (for overall activity)
    cur.execute("""
        SELECT date_trunc(%s, created_at) as period,
               COUNT(*) as created_count
        FROM tasks
        WHERE created_at >= NOW() - INTERVAL '%s days'
        GROUP BY period
        ORDER BY period ASC
    """, (date_trunc, days))
    
    creation_map = {}
    for row in cur.fetchall():
        k = row[0].isoformat() if row[0] else ''
        creation_map[k] = row[1]
    
    for t in trends:
        t['created_count'] = creation_map.get(t['period'], 0)
    
    conn.close()
    return trends


def pg_task_stats_enhanced():
    """Enhanced task stats with per-node breakdown and LUX totals."""
    conn = _conn()
    cur = conn.cursor()
    
    # Overall counts
    cur.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
    counts = {str(r[0]): r[1] for r in cur.fetchall()}
    
    # Total LUX distributed
    cur.execute("SELECT COALESCE(SUM(lux_reward), 0) FROM tasks WHERE status = 'completed'")
    total_lux = int(cur.fetchone()[0])
    
    # Per-node stats
    cur.execute("""
        SELECT assigned_to, COUNT(*), COALESCE(SUM(lux_reward), 0)
        FROM tasks
        WHERE status = 'completed' AND assigned_to IS NOT NULL
        GROUP BY assigned_to
        ORDER BY COUNT(*) DESC
    """)
    node_stats = [{
        'node_id': r[0],
        'completed_count': r[1],
        'total_lux': int(r[2]),
    } for r in cur.fetchall()]
    
    conn.close()
    return {
        'total': sum(counts.values()),
        'pending_count': counts.get('pending', 0),
        'assigned_count': counts.get('assigned', 0),
        'completed_count': counts.get('completed', 0),
        'revoked_count': counts.get('revoked', 0),
        'total_lux_distributed': total_lux,
        'node_stats': node_stats,
    }


# ============================================================
# Event Log queries (migrated from SQLite)
# ============================================================

def pg_get_event_log(limit=50, hours=24):
    """Get recent events from PostgreSQL (replaces SQLite event_log query)."""
    conn = _conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT event_type, node_id, details, created_at, id
        FROM event_log
        WHERE created_at >= NOW() - INTERVAL '%s hours'
        ORDER BY created_at DESC
        LIMIT %s
    """, (hours, limit))
    
    events = []
    for row in cur.fetchall():
        events.append({
            "id": f"pg_{row[4]}",
            "type": row[0] or "event",
            "from": row[1] or "?",
            "content": str(row[2] or "")[:200],
            "channels": [],
            "time": row[3].isoformat() if row[3] else None
        })
    
    conn.close()
    return events


def pg_insert_event(event_type, node_id, details):
    """Insert a new event into PostgreSQL event_log."""
    conn = _conn()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO event_log (event_type, node_id, details, created_at)
        VALUES (%s, %s, %s, NOW())
        RETURNING id
    """, (event_type, node_id, details))
    
    event_id = cur.fetchone()[0]
    conn.close()
    return event_id
