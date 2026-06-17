#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
四象飞轮监控与持续推进
"""
import requests
import json
import time

HUB_URL = "http://127.0.0.1:19104"
FLYWHEEL_URL = "http://127.0.0.1:8001"

def check_pipeline_status(run_id):
    """检查pipeline状态"""
    try:
        r = requests.get(f"{FLYWHEEL_URL}/api/v1/pipeline/status/{run_id}", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Error checking pipeline {run_id}: {e}")
    return None

def monitor_and_push():
    """监控并推进"""
    print("=" * 60)
    print("Four Flywheels Monitor & Push")
    print("=" * 60)
    
    # Recent pipeline runs to check
    recent_runs = [
        "run-fccfe362d3b9",
        "run-6ab8f683726e",
        "run-332e2d8fd345",
        "run-c212abee61d1",
        "run-adc9f9a509f2"
    ]
    
    print("\n=== Checking Recent Pipelines ===")
    for run_id in recent_runs:
        status = check_pipeline_status(run_id)
        if status:
            print(f"{run_id[:20]}...: {status.get('status', 'unknown')}")
    
    # Hub status
    print("\n=== Hub Status ===")
    try:
        r = requests.get(f"{HUB_URL}/api/v1/status", timeout=10)
        if r.status_code == 200:
            data = r.json()
            network = data.get('network', {})
            tasks = network.get('tasks', {})
            print(f"Tasks: {tasks.get('total', 0)} total")
            print(f"  Pending: {tasks.get('pending', 0)}")
            print(f"  Completed: {tasks.get('completed', 0)}")
            print(f"Online nodes: {network.get('online_nodes', 0)}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Seeds status
    print("\n=== Seeds Status ===")
    try:
        r = requests.post(f"{FLYWHEEL_URL}/api/v1/seeds/score-all", timeout=15)
        if r.status_code == 200:
            data = r.json()
            seeds = data.get('seeds', [])
            high = len([s for s in seeds if s.get('score', 0) >= 0.5])
            print(f"Total seeds: {len(seeds)}")
            print(f"High quality (>=0.5): {high}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Trigger new pipeline
    print("\n=== Triggering New Pipeline ===")
    try:
        payload = {
            "seed_id": f"auto_push_{int(time.time())}",
            "input_data": {
                "action": "continuous_operation",
                "timestamp": time.time()
            },
            "checkpoint_interval": 3
        }
        r = requests.post(f"{FLYWHEEL_URL}/api/v1/pipeline/run",
                        json=payload, timeout=20)
        if r.status_code == 200:
            data = r.json()
            print(f"New pipeline: {data.get('run_id', 'N/A')[:20]}...")
        else:
            print(f"Failed: {r.status_code}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 60)
    print("Monitor cycle complete")
    print("=" * 60)

if __name__ == "__main__":
    monitor_and_push()
