"""
evolution_engine.py — 自主进化循环引擎 v1.0
三个进化域：飞轮 / 网站 / Agent自身
定时运行或heartbeat触发
"""
import sys, os, json, time, datetime, hashlib, psycopg2, glob, urllib.request, traceback
sys.stdout.reconfigure(encoding='utf-8')
import subprocess  # for resource discovery

EVOLUTION_LOG = r'D:\ClawMatrix\evolution_log.json'
WEBSITE_ROOT = r'C:\SkyCetus-2.0\content'
ENGINE_FILE = r'D:\ClawMatrix\engine_v2.py'

def get_conn():
    return psycopg2.connect(host='127.0.0.1', dbname='skycetus', user='postgres', password='<DB_PASSWORD>')

def log_evolution(domain, action, detail, result='ok'):
    """Append to evolution log."""
    entry = {
        'timestamp': datetime.datetime.now().isoformat(),
        'domain': domain,
        'action': action,
        'detail': detail,
        'result': result
    }
    try:
        existing = []
        if os.path.exists(EVOLUTION_LOG):
            with open(EVOLUTION_LOG, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        existing.append(entry)
        # Keep last 500 entries
        if len(existing) > 500:
            existing = existing[-500:]
        with open(EVOLUTION_LOG, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except:
        pass
    print(f"[EVOLUTION] [{domain}] {action}: {detail} -> {result}")

# ============================================================
# DOMAIN 1: FLYWHEEL SELF-EVOLUTION
# ============================================================
def evolve_flywheel():
    """Analyze flywheel performance and generate evolution signals."""
    print("\n" + "="*60)
    print("FLYWHEEL EVOLUTION CYCLE")
    print("="*60)
    
    conn = get_conn()
    cur = conn.cursor()
    signals = []
    
    # 1. Error rate check
    cur.execute("""
        SELECT COUNT(*), 
               SUM(CASE WHEN status='error' THEN 1 ELSE 0 END),
               SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END)
        FROM flywheel_api_runs
        WHERE started_at > NOW() - INTERVAL '24 hours'
    """)
    total, errors, completed = cur.fetchone()
    errors = errors or 0
    completed = completed or 0
    
    if total and total > 0:
        error_rate = errors / total
        if error_rate > 0.3:
            signals.append({
                'type': 'HIGH_ERROR_RATE',
                'severity': 'critical',
                'detail': f'{error_rate:.0%} error rate in last 24h ({errors}/{total})',
                'action': 'investigate_errors'
            })
        log_evolution('flywheel', 'error_rate_check', f'{error_rate:.0%} ({errors}/{total})')
    
    # 2. Score trend detection
    cur.execute("""
        SELECT ROUND(AVG(score)::numeric, 3)
        FROM flywheel_api_runs 
        WHERE status='completed' AND started_at > NOW() - INTERVAL '24 hours'
    """)
    recent_avg = cur.fetchone()[0]
    
    cur.execute("""
        SELECT ROUND(AVG(score)::numeric, 3)
        FROM flywheel_api_runs 
        WHERE status='completed' AND started_at > NOW() - INTERVAL '7 days'
    """)
    week_avg = cur.fetchone()[0]
    
    if recent_avg and week_avg:
        drift = float(recent_avg) - float(week_avg)
        if drift < -0.05:
            signals.append({
                'type': 'SCORE_DEGRADATION',
                'severity': 'warning',
                'detail': f'24h avg {recent_avg} vs 7d avg {week_avg} (drift {drift:+.3f})',
                'action': 'check_model_routing'
            })
        log_evolution('flywheel', 'score_trend', f'24h={recent_avg} 7d={week_avg} drift={drift:+.3f}')
    
    # 3. Domain classification quality
    cur.execute("""
        SELECT domain, COUNT(*) 
        FROM flywheel_api_runs WHERE status='completed'
        GROUP BY domain ORDER BY COUNT(*) DESC
    """)
    domains = cur.fetchall()
    if domains:
        general_count = sum(c for d, c in domains if d in ('general', None, ''))
        total_completed = sum(c for _, c in domains)
        general_pct = general_count / max(total_completed, 1)
        if general_pct > 0.6:
            signals.append({
                'type': 'WEAK_DOMAIN_CLASSIFIER',
                'severity': 'info',
                'detail': f'{general_pct:.0%} of runs classified as "general"',
                'action': 'improve_topic_assessment'
            })
    
    # 4. Enrichment fill rate
    cur.execute("""
        SELECT result FROM flywheel_api_runs 
        WHERE status='completed' AND result IS NOT NULL
        ORDER BY started_at DESC LIMIT 20
    """)
    kunpeng_total = 0
    kunpeng_full = 0
    for (result_str,) in cur.fetchall():
        try:
            result = json.loads(result_str) if isinstance(result_str, str) else result_str
            kp = result.get('kunpeng', {})
            if kp:
                kunpeng_total += 1
                filled = sum(1 for v in kp.values() if v and len(str(v)) > 10)
                if filled >= 8:
                    kunpeng_full += 1
        except:
            pass
    
    if kunpeng_total > 0:
        fill_rate = kunpeng_full / kunpeng_total
        if fill_rate < 0.9:
            signals.append({
                'type': 'LOW_ENRICHMENT',
                'severity': 'warning',
                'detail': f'{fill_rate:.0%} full enrichment rate ({kunpeng_full}/{kunpeng_total})',
                'action': 'fix_enrichment_pipeline'
            })
        log_evolution('flywheel', 'enrichment_rate', f'{fill_rate:.0%}')
    
    # 5. Orphaned run detection
    cur.execute("""
        SELECT COUNT(*) FROM flywheel_api_runs 
        WHERE status='running' AND started_at < NOW() - INTERVAL '2 hours'
    """)
    orphaned = cur.fetchone()[0]
    if orphaned > 0:
        signals.append({
            'type': 'ORPHANED_RUNS',
            'severity': 'warning',
            'detail': f'{orphaned} runs stuck in "running" for 2+ hours',
            'action': 'mark_orphaned'
        })
        # Auto-fix: mark them as error
        cur.execute("""
            UPDATE flywheel_api_runs 
            SET status='error', error='Orphaned: auto-detected by evolution engine'
            WHERE status='running' AND started_at < NOW() - INTERVAL '2 hours'
        """)
        conn.commit()
        log_evolution('flywheel', 'orphan_cleanup', f'Marked {orphaned} orphaned runs as error', 'auto-fixed')
    
    conn.close()
    return signals

# ============================================================
# DOMAIN 2: WEBSITE EVOLUTION
# ============================================================
def evolve_website():
    """Scan website health and identify evolution opportunities."""
    print("\n" + "="*60)
    print("WEBSITE EVOLUTION CYCLE")
    print("="*60)
    
    signals = []
    
    # 1. Page count and structure
    html_files = glob.glob(os.path.join(WEBSITE_ROOT, '**', '*.html'), recursive=True)
    flywheel_pages = [f for f in html_files if 'flywheel' in f.lower()]
    
    print(f"Total pages: {len(html_files)}")
    print(f"Flywheel report pages: {len(flywheel_pages)}")
    log_evolution('website', 'page_count', f'{len(html_files)} total, {len(flywheel_pages)} flywheel')
    
    # 2. Broken link detection (internal links only)
    broken_links = []
    import re
    for html_file in html_files[:100]:  # Sample first 100
        try:
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            links = re.findall(r'href="([^"]*\.html)"', content)
            for link in links:
                if link.startswith('http'):
                    continue
                # Resolve relative path
                base_dir = os.path.dirname(html_file)
                target = os.path.normpath(os.path.join(base_dir, link))
                if not os.path.exists(target):
                    # Also check from root
                    target2 = os.path.normpath(os.path.join(WEBSITE_ROOT, link))
                    if not os.path.exists(target2):
                        broken_links.append((os.path.basename(html_file), link))
        except:
            pass
    
    if broken_links:
        signals.append({
            'type': 'BROKEN_LINKS',
            'severity': 'info',
            'detail': f'{len(broken_links)} broken internal links found (sample of 100 pages)',
            'examples': broken_links[:5]
        })
        log_evolution('website', 'broken_links', f'{len(broken_links)} broken links')
    
    # 3. Stale content detection
    now = time.time()
    stale_pages = []
    for html_file in html_files:
        mtime = os.path.getmtime(html_file)
        age_days = (now - mtime) / 86400
        if age_days > 14:
            stale_pages.append((os.path.basename(html_file), int(age_days)))
    
    if stale_pages:
        signals.append({
            'type': 'STALE_CONTENT',
            'severity': 'info',
            'detail': f'{len(stale_pages)} pages older than 14 days',
        })
        log_evolution('website', 'stale_content', f'{len(stale_pages)} stale pages')
    
    # 4. Empty or tiny pages
    tiny_pages = []
    for html_file in html_files:
        size = os.path.getsize(html_file)
        if size < 500:
            tiny_pages.append((os.path.basename(html_file), size))
    
    if tiny_pages:
        signals.append({
            'type': 'TINY_PAGES',
            'severity': 'warning',
            'detail': f'{len(tiny_pages)} pages under 500 bytes (possibly broken)',
            'examples': tiny_pages[:5]
        })
    
    return signals

# ============================================================
# DOMAIN 3: AGENT SELF-EVOLUTION
# ============================================================
def evolve_self():
    """Check agent health and evolution state."""
    print("\n" + "="*60)
    print("AGENT SELF-EVOLUTION CYCLE")
    print("="*60)
    
    signals = []
    
    # 1. Service health check
    services = {
        'flywheel': 'http://127.0.0.1:8100/health',
        'hub': 'http://127.0.0.1:19104/api/v1/health',
    }
    
    for name, url in services.items():
        try:
            resp = urllib.request.urlopen(url, timeout=5)
            status = resp.getcode()
            log_evolution('self', f'health_{name}', f'OK ({status})')
        except Exception as e:
            signals.append({
                'type': 'SERVICE_DOWN',
                'severity': 'critical',
                'detail': f'{name} unreachable: {str(e)[:60]}',
                'action': f'restart_{name}'
            })
            log_evolution('self', f'health_{name}', f'DOWN: {str(e)[:60]}', 'error')
    
    # 2. Evolution log analysis (self-referential)
    if os.path.exists(EVOLUTION_LOG):
        with open(EVOLUTION_LOG, 'r', encoding='utf-8') as f:
            log_entries = json.load(f)
        recent = [e for e in log_entries 
                  if e.get('timestamp', '') > (datetime.datetime.now() - datetime.timedelta(hours=24)).isoformat()]
        print(f"Evolution log: {len(log_entries)} total, {len(recent)} in last 24h")
        
        # Count auto-fixes
        auto_fixes = [e for e in recent if e.get('result') == 'auto-fixed']
        if auto_fixes:
            log_evolution('self', 'auto_fixes', f'{len(auto_fixes)} auto-fixes in last 24h')
    
    return signals


# ============================================================
# RESOURCE ECOSYSTEM EVOLUTION
# ============================================================
RESOURCE_ENGINE = r'D:\ClawMatrix\resource-ecosystem\engine.py'

def evolve_resource():
    """Run resource-ecosystem discovery and check for capability gaps."""
    signals = []
    
    try:
        # Run pre_tick.py which outputs RESOURCE_CTX JSON
        result = subprocess.run(
            ['python', r'D:\ClawMatrix\resource-ecosystem\pre_tick.py'],
            capture_output=True, text=True, timeout=60, encoding='utf-8'
        )
        
        if result.returncode == 0:
            output = result.stdout or ''
            # Parse resource context from output
            for line in output.split('\n'):
                if line.startswith('RESOURCE_CTX:'):
                    ctx = json.loads(line[13:])
                    gaps = ctx.get('gaps', [])
                    
                    if gaps:
                        signals.append({
                            'type': 'capability_gap',
                            'severity': 'warning',
                            'detail': f"Resource gaps: {', '.join(gaps)}",
                            'context': ctx
                        })
                    else:
                        signals.append({
                            'type': 'resource_scan',
                            'severity': 'info',
                            'detail': f"All capabilities covered: {ctx.get('gpu_model', 'unknown')} + {ctx.get('skill_count', 0)} skills"
                        })
                    
                    # Check if new skills needed
                    ollama_models = ctx.get('ollama_models', [])
                    if not any('vision' in m.lower() for m in ollama_models):
                        signals.append({
                            'type': 'model_gap',
                            'severity': 'info',
                            'detail': 'No vision model in Ollama — consider adding for image generation capability'
                        })
        else:
            signals.append({
                'type': 'resource_error',
                'severity': 'warning',
                'detail': f"Resource discovery failed: {result.stderr[:200]}"
            })
    except Exception as e:
        signals.append({
            'type': 'resource_error',
            'severity': 'critical',
            'detail': f"Resource ecosystem error: {str(e)}"
        })
    
    return signals

# ============================================================
# MAIN EVOLUTION CYCLE
# ============================================================
def run_evolution_cycle():
    """Run complete evolution cycle across all three domains."""
    print(f"\n{'#'*60}")
    print(f"# EVOLUTION CYCLE - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")
    
    all_signals = []
    
    try:
        flywheel_signals = evolve_flywheel()
        all_signals.extend(flywheel_signals)
    except Exception as e:
        print(f"Flywheel evolution error: {e}")
        traceback.print_exc()
    
    try:
        website_signals = evolve_website()
        all_signals.extend(website_signals)
    except Exception as e:
        print(f"Website evolution error: {e}")
        traceback.print_exc()
    
    try:
        self_signals = evolve_self()
        all_signals.extend(self_signals)
    except Exception as e:
        print(f"Self evolution error: {e}")
        traceback.print_exc()
    

    try:
        resource_signals = evolve_resource()
        all_signals.extend(resource_signals)
    except Exception as e:
        print(f"Resource evolution error: {e}")
        traceback.print_exc()
    # Summary
    print(f"\n{'='*60}")
    print(f"EVOLUTION CYCLE SUMMARY")
    print(f"{'='*60}")
    
    critical = [s for s in all_signals if s.get('severity') == 'critical']
    warnings = [s for s in all_signals if s.get('severity') == 'warning']
    info = [s for s in all_signals if s.get('severity') == 'info']
    
    print(f"Signals: {len(critical)} critical, {len(warnings)} warning, {len(info)} info")
    
    for s in all_signals:
        icon = {'critical': '🔴', 'warning': '🟡', 'info': '🔵'}.get(s.get('severity'), '⚪')
        print(f"  {icon} [{s['type']}] {s['detail']}")
    
    # Save cycle result
    cycle_result = {
        'timestamp': datetime.datetime.now().isoformat(),
        'signals': all_signals,
        'summary': {
            'critical': len(critical),
            'warnings': len(warnings),
            'info': len(info)
        }
    }
    
    cycle_file = r'D:\ClawMatrix\last_evolution_cycle.json'
    with open(cycle_file, 'w', encoding='utf-8') as f:
        json.dump(cycle_result, f, ensure_ascii=False, indent=2)
    
    return all_signals

if __name__ == '__main__':
    signals = run_evolution_cycle()
