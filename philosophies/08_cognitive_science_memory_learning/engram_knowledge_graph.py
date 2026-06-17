# -*- coding: utf-8 -*-
"""Engram Knowledge Graph Builder v1.0
Reads existing flywheel data from PostgreSQL + SQLite, builds cross-topic
knowledge graph with bigram similarity connections."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import os
import sqlite3
from collections import defaultdict

sys.path.insert(0, r'D:\ClawMatrix')

def bigram_similarity(s1, s2):
    """Bigram Jaccard similarity between two strings."""
    if not s1 or not s2:
        return 0.0
    bigrams1 = set(s1[i:i+2] for i in range(len(s1)-1))
    bigrams2 = set(s2[i:i+2] for i in range(len(s2)-1))
    if not bigrams1 or not bigrams2:
        return 0.0
    intersection = bigrams1 & bigrams2
    union = bigrams1 | bigrams2
    return len(intersection) / len(union) if union else 0.0

def check_sqlite():
    """Check SQLite fallback database."""
    db_path = r'D:\ClawMatrix\flywheel.db'
    if not os.path.exists(db_path):
        print(f"SQLite DB not found at {db_path}")
        return []
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"SQLite tables: {tables}")
    
    runs = []
    if 'runs' in tables:
        cur.execute("SELECT COUNT(*) FROM runs")
        count = cur.fetchone()[0]
        print(f"SQLite runs: {count}")
        
        cur.execute("SELECT id, topic, status, created_at FROM runs ORDER BY created_at DESC LIMIT 50")
        runs = cur.fetchall()
        for r in runs:
            print(f"  Run {r[0]}: {r[1][:60]} [{r[2]}] {r[3]}")
    conn.close()
    return runs

def check_postgres():
    """Check PostgreSQL main database."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='localhost', port=5432,
            dbname='skycetus', user='postgres'
        )
        cur = conn.cursor()
        
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'runs')")
        has_runs = cur.fetchone()[0]
        print(f"\nPostgreSQL runs table: {has_runs}")
        
        if has_runs:
            cur.execute("SELECT COUNT(*) FROM runs")
            count = cur.fetchone()[0]
            print(f"PG runs: {count}")
            
            cur.execute("SELECT id, topic, status, created_at FROM runs ORDER BY created_at DESC LIMIT 50")
            rows = cur.fetchall()
            for r in rows:
                print(f"  Run {r[0]}: {r[1][:60] if r[1] else '(null)'} [{r[2]}] {r[3]}")
            return rows
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"PostgreSQL error: {e}")
    return []

def build_knowledge_graph(all_runs):
    """Build knowledge graph from run topics."""
    if len(all_runs) < 2:
        print("\nNot enough data for knowledge graph")
        return
    
    print(f"\nBuilding knowledge graph from {len(all_runs)} topics...")
    
    # Extract topics
    topics = []
    for r in all_runs:
        topic = r[1] if len(r) > 1 and r[1] else ''
        if topic and len(topic) > 2:
            topics.append((r[0], topic))
    
    print(f"Valid topics: {len(topics)}")
    
    # Compute pairwise similarity
    edges = []
    for i in range(len(topics)):
        for j in range(i+1, len(topics)):
            sim = bigram_similarity(topics[i][1], topics[j][1])
            if sim >= 0.15:  # Threshold for meaningful connection
                edges.append({
                    "from": topics[i][0],
                    "to": topics[j][0],
                    "similarity": round(sim, 3),
                    "topic_a": topics[i][1][:40],
                    "topic_b": topics[j][1][:40]
                })
    
    edges.sort(key=lambda x: x["similarity"], reverse=True)
    
    print(f"\nKnowledge graph edges (sim >= 0.15): {len(edges)}")
    for e in edges[:10]:
        print(f"  {e['similarity']:.3f} | {e['topic_a']} <-> {e['topic_b']}")
    
    # Save graph
    graph = {
        "nodes": [{"id": t[0], "topic": t[1]} for t in topics],
        "edges": edges,
        "stats": {
            "total_nodes": len(topics),
            "total_edges": len(edges),
            "avg_similarity": round(sum(e["similarity"] for e in edges) / len(edges), 4) if edges else 0
        }
    }
    
    output_path = r'D:\ClawMatrix\engram_knowledge_graph.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    print(f"\nKnowledge graph saved to {output_path}")
    
    return graph

if __name__ == "__main__":
    print("=== Engram Knowledge Graph Builder ===\n")
    
    # Check both data sources
    sqlite_runs = check_sqlite()
    pg_runs = check_postgres()
    
    # Merge
    all_runs = []
    seen_ids = set()
    for r in pg_runs + sqlite_runs:
        if r[0] not in seen_ids:
            all_runs.append(r)
            seen_ids.add(r[0])
    
    print(f"\nTotal unique runs: {len(all_runs)}")
    
    # Build graph
    build_knowledge_graph(all_runs)
