# -*- coding: utf-8 -*-
"""ClawMatrix Hub Database Models - PostgreSQL (MIG-003 migrated from SQLite)

兼容接口: conn.execute("SELECT * FROM t WHERE id=?", (1,))
自动将 ? 转为 %s，支持 sqlite3.Row 风格的 dict 访问
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date

_db_path = os.path.join(os.path.dirname(__file__), "hub_new.db")  # kept for reference


def _convert_value(v):
    """将 PG 返回的 datetime/date 转为 ISO 字符串（兼容 SQLite 行为）"""
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


class RowDict(dict):
    """兼容 sqlite3.Row：支持 dict 访问 + 索引访问，自动转换 datetime"""
    
    def __getitem__(self, key):
        if isinstance(key, int):
            return _convert_value(list(self.values())[key])
        return _convert_value(super().__getitem__(key))
    
    def get(self, key, default=None):
        v = super().get(key, default)
        return _convert_value(v)


class PGCursor:
    """包装 psycopg2 cursor，兼容 sqlite3 游标和 sqlite3.Row"""
    
    def __init__(self, cur):
        self._cur = cur
    
    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        rd = RowDict()
        for k, v in row.items():
            rd[k] = v
        return rd
    
    def fetchall(self):
        rows = self._cur.fetchall()
        result = []
        for row in rows:
            rd = RowDict()
            for k, v in row.items():
                rd[k] = v
            result.append(rd)
        return result
    
    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size else self._cur.fetchmany()
        result = []
        for row in rows:
            rd = RowDict()
            for k, v in row.items():
                rd[k] = v
            result.append(rd)
        return result
    
    @property
    def rowcount(self):
        return self._cur.rowcount
    
    @property
    def lastrowid(self):
        return self._cur.lastrowid


class PGConnection:
    """包装 psycopg2 连接，兼容 sqlite3.Connection 接口"""
    
    def __init__(self, conn):
        self._conn = conn
        self._conn.autocommit = False
        # sqlite3.Row compatibility: always use dict rows
        self._row_factory = None
    
    @property
    def row_factory(self):
        return self._row_factory
    
    @row_factory.setter
    def row_factory(self, value):
        pass  # Ignore - we always return dict-like rows
    
    def execute(self, sql, params=None):
        """执行 SQL，自动 ? -> %s，返回 dict-like 游标"""
        if '?' in sql:
            sql = sql.replace('?', '%s')
        cur = self._conn.cursor(cursor_factory=RealDictCursor)
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        return PGCursor(cur)
    
    def executemany(self, sql, params_list):
        if '?' in sql:
            sql = sql.replace('?', '%s')
        cur = self._conn.cursor()
        cur.executemany(sql, params_list)
        return cur
    
    def commit(self):
        self._conn.commit()
    
    def rollback(self):
        self._conn.rollback()
    
    def close(self):
        self._conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


def get_db():
    """获取 PostgreSQL 连接（兼容 sqlite3 接口）"""
    conn = psycopg2.connect(
        host='127.0.0.1',
        port=5432,
        dbname='hub',
        user='postgres',
        password='<DB_PASSWORD>'
    )
    return PGConnection(conn)


def init_db():
    """No-op for PG (schema already exists)"""
    pass


def close_db(conn):
    """关闭连接"""
    if conn:
        try:
            conn.close()
        except:
            pass
