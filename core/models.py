# -*- coding: utf-8 -*-
"""Hub 数据库层 - SQLite"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get('MATRIX_DB', 'D:/ClawMatrix/hub_new.db')

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 任务表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT UNIQUE NOT NULL,
            goal TEXT,
            scope TEXT,
            constraints TEXT,
            done_definition TEXT,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            node_id TEXT,
            result TEXT,
            error TEXT
        )
    ''')
    
    # 节点表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT UNIQUE NOT NULL,
            name TEXT,
            status TEXT DEFAULT 'offline',
            last_heartbeat TEXT,
            capabilities TEXT,
            credits INTEGER DEFAULT 0
        )
    ''')
    
    # 事件日志表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT,
            event_type TEXT,
            node_id TEXT,
            data TEXT,
            created_at TEXT
        )
    ''')
    
    # Lux 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lux (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT UNIQUE,
            credits INTEGER DEFAULT 0,
            updated_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# 初始化
init_db()
