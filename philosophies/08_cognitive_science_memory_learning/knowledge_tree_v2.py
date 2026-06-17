"""
知识树系统 v2 — 用DeepSeek API代替Ollama
T1.3: 回填155条历史run
"""
import sys, json, os, time, hashlib, re
sys.stdout.reconfigure(encoding='utf-8')

import psycopg2
import psycopg2.extras
import httpx

PG_CONF = dict(host="127.0.0.1", port=5432, dbname="skycetus",
               user="skycetus", password="<DB_PASSWORD>")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_KEY = "sk-64ba741ee60d400b98be80ff82189a4b"

EXTRACT_PROMPT = """分析以下飞轮分析结果，提取结构化知识。严格只输出JSON，不要其他文字。

主题：{topic}
分数：{score}

青龙种子：
{seeds}

玄武结论：
{conclusion}

输出格式：
{{"core_conclusion":"一句话核心结论30字以内","domain":"行业领域","entities":[{{"name":"实体名","type":"company|technology|market|concept|product|policy","role":"角色"}}],"relations":[{{"source":"实体名1","target":"实体名2","type":"competes_with|depends_on|part_of|enables|regulates","detail":"简述"}}],"key_findings":["发现1","发现2","发现3"],"confidence":0.8}}

entities最多10个，relations最多8条，key_findings 3-5条。只输出JSON。"""

def call_deepseek(prompt, max_tokens=1500):
    try:
        resp = httpx.post(DEEPSEEK_URL, 
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  ⚠️ DeepSeek error: {e}")
        return None

def extract_knowledge(run_id, topic, score, result):
    eo = result.get('element_outputs', {})
    qinglong = eo.get('qinglong', '')
    if isinstance(qinglong, str):
        try: qinglong = json.loads(qinglong)
        except: pass
    
    seeds_text = ""
    if isinstance(qinglong, dict):
        seeds = qinglong.get('seeds', [])
        for s in seeds[:5]:
            if isinstance(s, dict):
                seeds_text += f"- {s.get('title', '')}: {s.get('hypothesis', '')}\n"
            else:
                seeds_text += f"- {s}\n"
    elif isinstance(qinglong, str):
        seeds_text = qinglong[:500]
    
    xuanwu = eo.get('xuanwu', '')
    if isinstance(xuanwu, str):
        try: xuanwu = json.loads(xuanwu)
        except: pass
    
    conclusion_text = ""
    if isinstance(xuanwu, dict):
        conclusion_text = xuanwu.get('conclusion', str(xuanwu)[:500])
    elif isinstance(xuanwu, str):
        conclusion_text = xuanwu[:500]
    
    if not seeds_text and not conclusion_text:
        # Try getting from top-level fields
        if 'topic' in result:
            seeds_text = f"主题: {result['topic']}"
        if not seeds_text:
            return None
    
    prompt = EXTRACT_PROMPT.format(
        topic=topic[:200], score=score,
        seeds=seeds_text[:800], conclusion=conclusion_text[:800]
    )
    
    raw = call_deepseek(prompt)
    if not raw:
        return None
    
    try:
        # Remove markdown code blocks if present
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*', '', raw)
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            return json.loads(json_match.group())
    except json.JSONDecodeError as e:
        print(f"  ⚠️ JSON parse error: {e}")
    return None

def make_entity_id(name, etype):
    h = hashlib.md5(f"{name}:{etype}".encode()).hexdigest()[:8]
    return f"kte_{h}"

def backfill_all():
    conn = psycopg2.connect(**PG_CONF)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT r.run_id, r.topic, r.score, r.result
        FROM flywheel_api_runs r
        LEFT JOIN kt_conclusions kc ON r.run_id = kc.run_id
        WHERE r.status = 'completed' AND r.result IS NOT NULL AND kc.id IS NULL
        ORDER BY r.score DESC NULLS LAST
    """)
    runs = cur.fetchall()
    print(f"📊 待处理: {len(runs)} runs")
    
    stats = {"ok": 0, "fail": 0, "skip": 0, "entities": 0, "relations": 0}
    
    for i, (run_id, topic, score, result_raw) in enumerate(runs):
        if isinstance(result_raw, str):
            try: result = json.loads(result_raw)
            except: 
                stats["skip"] += 1
                continue
        else:
            result = result_raw
        
        print(f"\n[{i+1}/{len(runs)}] {run_id} | {score} | {topic[:50]}")
        
        knowledge = extract_knowledge(run_id, topic, score, result)
        
        if not knowledge:
            stats["fail"] += 1
            print(f"  ❌ Extraction failed")
            continue
        
        try:
            cur.execute("""
                INSERT INTO kt_conclusions (run_id, topic, score, domain, conclusion_text, 
                    key_findings, confidence, entity_ids)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                run_id, topic[:500], score,
                knowledge.get('domain', 'general'),
                knowledge.get('core_conclusion', ''),
                json.dumps(knowledge.get('key_findings', []), ensure_ascii=False),
                knowledge.get('confidence', 0.5),
                json.dumps([])
            ))
            
            entity_ids = []
            entities = knowledge.get('entities', [])
            for ent in entities[:10]:
                name = ent.get('name', '')
                etype = ent.get('type', 'concept')
                if not name: continue
                
                eid = make_entity_id(name, etype)
                entity_ids.append(eid)
                
                cur.execute("""
                    INSERT INTO kt_entities (entity_id, name, entity_type, domain, 
                        properties, first_seen_run, last_seen_run, mention_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                    ON CONFLICT (entity_id) DO UPDATE SET
                        last_seen_run = EXCLUDED.last_seen_run,
                        mention_count = kt_entities.mention_count + 1,
                        updated_at = NOW()
                """, (
                    eid, name[:256], etype[:64],
                    knowledge.get('domain', 'general'),
                    json.dumps({'role': ent.get('role', '')}, ensure_ascii=False),
                    run_id, run_id
                ))
                stats["entities"] += 1
            
            if entity_ids:
                cur.execute("UPDATE kt_conclusions SET entity_ids = %s WHERE run_id = %s",
                    (json.dumps(entity_ids), run_id))
            
            relations = knowledge.get('relations', [])
            for rel in relations[:8]:
                src_name = rel.get('source', '')
                tgt_name = rel.get('target', '')
                rel_type = rel.get('type', 'relates_to')
                if not src_name or not tgt_name: continue
                
                src_eid = make_entity_id(src_name, 'concept')
                tgt_eid = make_entity_id(tgt_name, 'concept')
                
                for ent in entities:
                    if ent.get('name') == src_name:
                        src_eid = make_entity_id(src_name, ent.get('type', 'concept'))
                    if ent.get('name') == tgt_name:
                        tgt_eid = make_entity_id(tgt_name, ent.get('type', 'concept'))
                
                cur.execute("SELECT 1 FROM kt_entities WHERE entity_id = %s", (src_eid,))
                src_exists = cur.fetchone()
                cur.execute("SELECT 1 FROM kt_entities WHERE entity_id = %s", (tgt_eid,))
                tgt_exists = cur.fetchone()
                
                if src_exists and tgt_exists:
                    cur.execute("""
                        INSERT INTO kt_relations (source_entity_id, target_entity_id, 
                            relation_type, confidence, source_run, properties)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        src_eid, tgt_eid, rel_type[:64],
                        knowledge.get('confidence', 0.5),
                        run_id,
                        json.dumps({'detail': rel.get('detail', '')}, ensure_ascii=False)
                    ))
                    stats["relations"] += 1
            
            conn.commit()
            stats["ok"] += 1
            print(f"  ✅ {len(entities)}e {len([r for r in relations if r.get('source') and r.get('target')])}r | {knowledge.get('core_conclusion', '')[:60]}")
            
            # Rate limit: ~0.5s between calls
            time.sleep(0.5)
            
        except Exception as e:
            conn.rollback()
            stats["fail"] += 1
            print(f"  ❌ DB error: {e}")
    
    # Final stats
    print(f"\n=== 知识树统计 ===")
    for t in ['kt_entities', 'kt_relations', 'kt_conclusions', 'kt_gaps']:
        cur.execute(f"SELECT count(*) FROM {t}")
        print(f"  {t}: {cur.fetchone()[0]} rows")
    
    # Top entities by mention count
    cur.execute("""
        SELECT name, entity_type, mention_count, domain 
        FROM kt_entities ORDER BY mention_count DESC LIMIT 15
    """)
    print(f"\n=== 高频实体 Top 15 ===")
    for name, etype, count, domain in cur.fetchall():
        print(f"  [{count}x] {name} ({etype}) - {domain}")
    
    # Domain distribution
    cur.execute("""
        SELECT domain, count(*) as cnt FROM kt_conclusions 
        GROUP BY domain ORDER BY cnt DESC LIMIT 10
    """)
    print(f"\n=== 领域分布 ===")
    for domain, cnt in cur.fetchall():
        print(f"  {domain}: {cnt}")
    
    conn.close()
    
    print(f"\n=== 回填完成 ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    return stats

if __name__ == "__main__":
    backfill_all()
