# -*- coding: utf-8 -*-
"""ClawMatrix 配置"""
import os

class MatrixConfig:
    # 节点身份
    NODE_ID = os.environ.get('MATRIX_NODE_ID', 'skycetus-hub')
    SECRET = os.environ.get('MATRIX_SECRET', 'skycetus-shared-secret')
    
    # 网络
    LISTEN_HOST = '0.0.0.0'
    LISTEN_PORT = int(os.environ.get('MATRIX_PORT', '19102'))
    
    # 标签
    TAGS = ['hub', 'task-distributor', 'skycetus']
    
    # 数据�?
    DB_PATH = os.environ.get('MATRIX_DB', 'D:/ClawMatrix/hub_new.db')
    
    # 加密
    KEY_DIR = 'D:/ClawMatrix/keys'
    
    # 心跳
    HEARTBEAT_INTERVAL = 30  # �?
    NODE_TIMEOUT = 120  # 超过此时间无心跳视为离线
    
    # 文件传输
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    TRANSFER_DIR = 'D:/ClawMatrix/transfers'
    
    # Gossip
    GOSSIP_INTERVAL = 60  # �?
    MAX_PEERS = 50
