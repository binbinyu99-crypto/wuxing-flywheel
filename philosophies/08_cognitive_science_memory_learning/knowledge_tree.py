"""
知识树系统 — 大循环第一段闭环
T1.1: 建表
T1.2: LLM提取（Ollama本地qwen3:8b, 免费）
T1.3: 回填155条历史run
"""
import sys, json, os, time, hashlib, re
sys.stdout.reconfigure(encoding='utf-8')

import psycopg2
import psycopg2.extras
import httpx

# ========== CONFIG ==========
PG_CONF = dict(host="127.0.0.1", port=5432, dbname="skycetus",
               user="skycetus", password="<DB_PASSWORD>")
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3:8b"

# ========== T1.1: CREATE SCHEMA ==========
SCHEMA_SQL = """
-- 知识树实体表
CREATE TABLE IF NOT EXISTS kt_entities (
    id SERIAL PRIMARY KEY,
    entity_id VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(256) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,  -- company/technology/market/concept/person/product/policy
    domain VARCHAR(128),               -- 行业领域
    properties JSONB DEFAULT '{}',     -- 扩展属性
    first_seen_run VARCHAR(64),
    last_seen_run VARCHAR(64),
    mention_count INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_kt_entities_type ON kt_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_kt_entities_domain ON kt_entities(domain);
CREATE INDEX IF NOT EXISTS idx_kt_entities_name ON kt_entities(name);

-- 知识树关系表
CREATE TABLE IF NOT EXISTS kt_relations (
    id SERIAL PRIMARY KEY,
    source_entity_id VARCHAR(64) REFERENCES kt_entities(entity_id),
    target_entity_id VARCHAR(64) REFERENCES kt_entities(entity_id),
    relation_type VARCHAR(64) NOT NULL,  -- competes_with/depends_on/part_of/enables/regulates/contradicts
    confidence REAL DEFAULT 0.5,
    source_run VARCHAR(64),
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_kt_relations_type ON kt_relations(relation_type);
CREATE INDEX IF NOT EXISTS idx_kt_relations_source ON kt_relations(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_kt_relations_target ON kt_relations(target_entity_id);

-- 知识树结论表（每个run的核心发现）
CREATE TABLE IF NOT EXISTS kt_conclusions (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    topic VARCHAR(512),
    score REAL,
    domain VARCHAR(128),
    conclusion_text TEXT,           -- 一句话核心结论
    key_findings JSONB DEFAULT '[]',  -- 3-5条关键发现
    confidence REAL,
    entity_ids JSONB DEFAULT '[]',  -- 涉及的实体ID列表
    created_at TIMESTAMP DEFAULT NOW(),
    freshness_date TIMESTAMP DEFAULT NOW()  -- 结论的"保鲜期"
);
CREATE INDEX IF NOT EXISTS idx_kt_conclusions_run ON kt_conclusions(run_id);
CREATE INDEX IF NOT EXISTS idx_kt_conclusions_domain ON kt_conclusions(domain);

-- 知识树缺口表（自动触发器用）
CREATE TABLE IF NOT EXISTS kt_gaps (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(128),
    description TEXT,
    gap_type VARCHAR(32) NOT NULL,  -- stale/contradictory/empty/shallow
    priority REAL DEFAULT 0.5,       -- 0-1, 越高越紧急
    detected_at TIMESTAMP DEFAULT NOW(),
    resolved_run_id VARCHAR(64),
    resolved_at TIMESTAMP,
    status VARCHAR(16) DEFAULT 'open'  -- open/resolved/dismissed
);
CREATE INDEX IF NOT EXISTS idx_kt_gaps_status ON kt_gaps(status);
CREATE INDEX IF NOT EXISTS idx_kt_gaps_priority ON kt_gaps(priority DESC);
"""

def create_schema():
    conn = psycopg2.connect(**PG_CONF)
    cur = conn.cursor()
    cur.execute(SCHEMA_SQL)
    conn.commit()
    
    # Check table counts
    for t in ['kt_entities', 'kt_relations', 'kt_conclusions', 'kt_gaps']:
        cur.execute(f"SELECT count(*) FROM {t}")
        print(f"  {t}: {cur.fetchone()[0]} rows")
    conn.close()
    print("✅ Schema created")

# ========== T1.2: LLM EXTRACTION ==========
EXTRACT_PROMPT = """分析以下飞轮分析结果，提取结构化知识。严格按JSON格式输出，不要多余文字。

主题：{topic}
分数：{score}

青龙种子：
{seeds}

玄武结论：
{conclusion}

请提取：
{{
  "core_conclusion": "一句话核心结论（30字以内）",
  "domain": "行业领域（如：合成生物学/半导体/新能源/金融/医疗/AI等）",
  "entities": [
    {{"name": "实体名", "type": "company|technology|market|concept|product|policy", "role": "在分析中的角色"}}
  ],
  "relations": [
    {{"source": "实体名1", "target": "实体名2", "type": "competes_with|depends_on|part_of|enables|regulates", "detail": "简述"}}
  ],
  "key_findings": ["发现1", "发现2", "发现3"],
  "confidence": 0.8
}}

注意：
- entities最多提取10个最重要的
- relations最多提取8条
- key_findings提取3-5条
- 只输出JSON，不要其他文字"""

def call_ollama(prompt, max_tokens=2000):
    """Call local Ollama for extraction"""
    try:
        resp = httpx.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.3,
            },
            "think": False,
        }, timeout=120)
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception as e:
        print(f"  ⚠️ Ollama error: {e}")
        return None

def extract_knowledge(run_id, topic, score, result):
    """Extract structured knowledge from a run result using LLM"""
    # Get seeds from qinglong
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
    
    # Get conclusion from xuanwu
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
        return None
    
    prompt = EXTRACT_PROMPT.format(
        topic=topic[:200],
        score=score,
        seeds=seeds_text[:800],
        conclusion=conclusion_text[:800]
    )
    
    raw = call_ollama(prompt)
    if not raw:
        return None
    
    # Parse JSON from response
    try:
        # Try to find JSON block
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            return json.loads(json_match.group())
    except json.JSONDecodeError:
        pass
    
    return None

def make_entity_id(name, etype):
    h = hashlib.md5(f"{name}:{etype}".encode()).hexdigest()[:8]
    return f"kte_{h}"

# ========== T1.3: BACKFILL ==========
def backfill_all():
    conn = psycopg2.connect(**PG_CONF)
    cur = conn.cursor()
    
    # Get all completed runs not yet in kt_conclusions
    cur.execute("""
        SELECT r.run_id, r.topic, r.score, r.result
        FROM flywheel_api_runs r
        LEFT JOIN kt_conclusions kc ON r.run_id = kc.run_id
        WHERE r.status = 'completed' AND r.result IS NOT NULL AND kc.id IS NULL
        ORDER BY r.score DESC NULLS LAST
    """)
    runs = cur.fetchall()
    print(f"\n📊 待处理: {len(runs)} runs")
    
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
        
        # Extract knowledge via LLM
        knowledge = extract_knowledge(run_id, topic, score, result)
        
        if not knowledge:
            stats["fail"] += 1
            print(f"  ❌ Extraction failed")
            continue
        
        try:
            # Insert conclusion
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
                json.dumps([])  # Will update after entity insertion
            ))
            
            # Insert entities
            entity_ids = []
            entities = knowledge.get('entities', [])
            for ent in entities[:10]:
                name = ent.get('name', '')
                etype = ent.get('type', 'concept')
                if not name:
                    continue
                
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
            
            # Update conclusion with entity_ids
            if entity_ids:
                cur.execute("""
                    UPDATE kt_conclusions SET entity_ids = %s WHERE run_id = %s
                """, (json.dumps(entity_ids), run_id))
            
            # Insert relations
            relations = knowledge.get('relations', [])
            for rel in relations[:8]:
                src_name = rel.get('source', '')
                tgt_name = rel.get('target', '')
                rel_type = rel.get('type', 'relates_to')
                
                if not src_name or not tgt_name:
                    continue
                
                # Find entity IDs
                src_eid = make_entity_id(src_name, 'concept')  # Default type
                tgt_eid = make_entity_id(tgt_name, 'concept')
                
                # Check if entities exist, try with actual types
                for ent in entities:
                    if ent.get('name') == src_name:
                        src_eid = make_entity_id(src_name, ent.get('type', 'concept'))
                    if ent.get('name') == tgt_name:
                        tgt_eid = make_entity_id(tgt_name, ent.get('type', 'concept'))
                
                # Only insert if both entities exist
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
            print(f"  ✅ {len(entities)} entities, {len(relations)} relations")
            
        except Exception as e:
            conn.rollback()
            stats["fail"] += 1
            print(f"  ❌ DB error: {e}")
    
    # Final stats
    for t in ['kt_entities', 'kt_relations', 'kt_conclusions', 'kt_gaps']:
        cur.execute(f"SELECT count(*) FROM {t}")
        count = cur.fetchone()[0]
        print(f"\n  {t}: {count} rows")
    
    conn.close()
    
    print(f"\n=== 回填完成 ===")
    print(f"成功: {stats['ok']}")
    print(f"失败: {stats['fail']}")
    print(f"跳过: {stats['skip']}")
    print(f"实体: {stats['entities']}")
    print(f"关系: {stats['relations']}")
    return stats

# ========== MAIN ==========
if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if action in ("schema", "all"):
        print("=== T1.1: Creating Schema ===")
        create_schema()
    
    if action in ("backfill", "all"):
        print("\n=== T1.3: Backfilling Knowledge Tree ===")
        backfill_all()
