"""
evolution_actions.py — 自动修复模块
evolution_engine检测到问题后，这里执行修复
"""
import sys, os, json, time, glob, re, psycopg2, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

WEBSITE_ROOT = r'C:\SkyCetus-2.0\content'

def get_conn():
    return psycopg2.connect(host='127.0.0.1', dbname='skycetus', user='postgres', password='<DB_PASSWORD>')

def action_cleanup_orphaned_runs():
    """Mark stuck runs as error."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE flywheel_api_runs 
        SET status='error', error='Auto-cleanup: orphaned run detected by evolution engine',
            finished_at=NOW()
        WHERE status='running' AND started_at < NOW() - INTERVAL '2 hours'
        RETURNING run_id
    """)
    orphaned = [r[0] for r in cur.fetchall()]
    conn.commit()
    conn.close()
    print(f"Cleaned {len(orphaned)} orphaned runs: {orphaned}")
    return len(orphaned)

def action_cleanup_tiny_pages():
    """List tiny pages (<500 bytes) for review, don't auto-delete."""
    html_files = glob.glob(os.path.join(WEBSITE_ROOT, '**', '*.html'), recursive=True)
    tiny = []
    for f in html_files:
        size = os.path.getsize(f)
        if size < 200:  # Very tiny = likely broken
            tiny.append((os.path.relpath(f, WEBSITE_ROOT), size))
    
    print(f"\n=== TINY PAGES (<200 bytes) ===")
    for path, size in sorted(tiny):
        print(f"  {size:>5}B  {path}")
    print(f"Total: {len(tiny)} very tiny pages")
    return tiny

def action_build_knowledge_tree():
    """Build a knowledge tree index from flywheel reports."""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get all completed runs with topics
    cur.execute("""
        SELECT run_id, topic, domain, score, grade, 
               started_at::text, feishu_doc_url
        FROM flywheel_api_runs 
        WHERE status='completed' AND score IS NOT NULL
        ORDER BY score DESC
    """)
    runs = cur.fetchall()
    conn.close()
    
    # Build domain tree
    tree = {}
    for run_id, topic, domain, score, grade, started_at, doc_url in runs:
        domain = domain or 'general'
        if domain not in tree:
            tree[domain] = []
        tree[domain].append({
            'run_id': run_id,
            'topic': topic[:80] if topic else 'Unknown',
            'score': float(score) if score else 0,
            'grade': grade or '?',
            'date': started_at[:10] if started_at else '',
            'doc_url': doc_url or ''
        })
    
    # Generate HTML index
    html_parts = ['''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>珑珠知识树 - SkyCetus Knowledge Tree</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0a0e27; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 40px 20px; }
.container { max-width: 1200px; margin: 0 auto; }
h1 { font-size: 2.5em; background: linear-gradient(135deg, #00d4ff, #7b2fef); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }
.subtitle { color: #888; margin-bottom: 40px; font-size: 1.1em; }
.stats { display: flex; gap: 20px; margin-bottom: 40px; flex-wrap: wrap; }
.stat-card { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 20px; min-width: 150px; }
.stat-value { font-size: 2em; font-weight: bold; color: #00d4ff; }
.stat-label { color: #888; font-size: 0.9em; }
.domain { margin-bottom: 30px; }
.domain-header { font-size: 1.4em; color: #7b2fef; margin-bottom: 15px; border-bottom: 1px solid rgba(123,47,239,0.3); padding-bottom: 8px; }
.report { display: flex; align-items: center; padding: 10px 15px; margin: 5px 0; background: rgba(255,255,255,0.03); border-radius: 8px; border-left: 3px solid; transition: background 0.2s; }
.report:hover { background: rgba(255,255,255,0.08); }
.report.grade-A { border-color: #00ff88; }
.report.grade-B { border-color: #ffd700; }
.report.grade-C { border-color: #ff6b6b; }
.report .grade { font-weight: bold; width: 30px; text-align: center; margin-right: 15px; }
.report .score { color: #888; width: 50px; text-align: right; margin-right: 15px; }
.report .topic { flex: 1; }
.report .date { color: #666; font-size: 0.85em; width: 90px; text-align: right; }
.report a { color: inherit; text-decoration: none; }
.report a:hover { color: #00d4ff; }
.footer { margin-top: 40px; color: #555; font-size: 0.85em; text-align: center; }
</style>
</head>
<body>
<div class="container">
<h1>🌳 珑珠知识树</h1>
<p class="subtitle">SkyCetus Knowledge Tree — 五行飞轮认知分析索引</p>
''']
    
    total_runs = len(runs)
    a_count = sum(1 for r in runs if r[4] == 'A')
    avg_score = sum(float(r[3]) for r in runs) / max(total_runs, 1)
    domains_count = len(tree)
    
    html_parts.append(f'''
<div class="stats">
    <div class="stat-card"><div class="stat-value">{total_runs}</div><div class="stat-label">分析报告</div></div>
    <div class="stat-card"><div class="stat-value">{a_count}</div><div class="stat-label">A级报告</div></div>
    <div class="stat-card"><div class="stat-value">{avg_score:.2f}</div><div class="stat-label">平均得分</div></div>
    <div class="stat-card"><div class="stat-value">{domains_count}</div><div class="stat-label">知识领域</div></div>
</div>
''')
    
    # Sort domains by report count
    for domain in sorted(tree.keys(), key=lambda d: -len(tree[d])):
        reports = tree[domain]
        domain_label = {
            'general': '综合分析', 'technology': '科技', 'industry': '产业',
            'finance': '金融', 'semiconductor': '半导体', 'trading': '交易',
            'test': '测试', 'science_history': '科学史'
        }.get(domain, domain)
        
        html_parts.append(f'<div class="domain"><div class="domain-header">{domain_label} ({len(reports)})</div>')
        
        for r in sorted(reports, key=lambda x: -x['score'])[:30]:  # Top 30 per domain
            grade = r['grade']
            grade_class = f'grade-{grade}' if grade in ('A','B','C') else ''
            topic_display = r['topic']
            if r['doc_url']:
                topic_display = f'<a href="{r["doc_url"]}" target="_blank">{r["topic"]}</a>'
            
            html_parts.append(f'''<div class="report {grade_class}">
    <span class="grade">{grade}</span>
    <span class="score">{r['score']:.2f}</span>
    <span class="topic">{topic_display}</span>
    <span class="date">{r['date']}</span>
</div>''')
        
        html_parts.append('</div>')
    
    html_parts.append(f'''
<div class="footer">
    自动生成于 {time.strftime("%Y-%m-%d %H:%M")} | 由进化引擎驱动 | SkyCetus 天鲸之城
</div>
</div></body></html>''')
    
    output = os.path.join(WEBSITE_ROOT, 'knowledge-tree.html')
    with open(output, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_parts))
    
    size = os.path.getsize(output)
    print(f"\nKnowledge tree generated: {output} ({size} bytes)")
    print(f"  {total_runs} reports across {domains_count} domains")
    return output

if __name__ == '__main__':
    print("=== Running Evolution Actions ===")
    action_cleanup_orphaned_runs()
    action_cleanup_tiny_pages()
    action_build_knowledge_tree()
