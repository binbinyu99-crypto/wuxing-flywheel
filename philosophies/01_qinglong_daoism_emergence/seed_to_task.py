
"""
seed_to_task.py - 种子→任务自动转换引擎
种子经过评分后自动生成DAG任务树，分配优先级和资源，写入Hub
"""
import json, hashlib, time, sys
from datetime import datetime

class SeedToTaskEngine:
    """将评分通过的种子自动转换为DAG任务树"""
    
    # Task templates by seed type
    TASK_TEMPLATES = {
        'research': {
            'phases': [
                {'name': 'Literature Review', 'type': 'qinglong', 'weight': 0.2},
                {'name': 'Data Collection', 'type': 'qinglong', 'weight': 0.2},
                {'name': 'Analysis', 'type': 'xuanwu', 'weight': 0.3},
                {'name': 'Report Generation', 'type': 'zhuque', 'weight': 0.3},
            ],
            'base_lux': 100
        },
        'development': {
            'phases': [
                {'name': 'Requirements Analysis', 'type': 'qinglong', 'weight': 0.15},
                {'name': 'Architecture Design', 'type': 'xuanwu', 'weight': 0.2},
                {'name': 'Implementation', 'type': 'zhuque', 'weight': 0.35},
                {'name': 'Testing', 'type': 'baihu', 'weight': 0.15},
                {'name': 'Deployment', 'type': 'zhuque', 'weight': 0.15},
            ],
            'base_lux': 150
        },
        'analysis': {
            'phases': [
                {'name': 'Problem Definition', 'type': 'qinglong', 'weight': 0.15},
                {'name': 'Multi-source Research', 'type': 'qinglong', 'weight': 0.25},
                {'name': 'Evaluation & Scoring', 'type': 'baihu', 'weight': 0.25},
                {'name': 'Synthesis', 'type': 'xuanwu', 'weight': 0.2},
                {'name': 'Output Report', 'type': 'zhuque', 'weight': 0.15},
            ],
            'base_lux': 120
        },
        'default': {
            'phases': [
                {'name': 'Discovery', 'type': 'qinglong', 'weight': 0.25},
                {'name': 'Evaluation', 'type': 'baihu', 'weight': 0.25},
                {'name': 'Convergence', 'type': 'xuanwu', 'weight': 0.25},
                {'name': 'Output', 'type': 'zhuque', 'weight': 0.25},
            ],
            'base_lux': 80
        }
    }
    
    PRIORITY_MAP = {
        'approve': 'P1',
        'review': 'P2',
        'reject': 'P3'
    }
    
    def __init__(self, hub_url='http://localhost:19104'):
        self.hub_url = hub_url
        self.generated_tasks = []
    
    def convert_seed(self, seed_id, seed_content, evaluation, seed_type='default'):
        """将种子转换为DAG任务树"""
        if evaluation['decision'] == 'reject':
            return {'status': 'rejected', 'reason': 'Seed evaluation rejected'}
        
        template = self.TASK_TEMPLATES.get(seed_type, self.TASK_TEMPLATES['default'])
        priority = self.PRIORITY_MAP.get(evaluation['decision'], 'P2')
        
        # Calculate LUX based on evaluation score
        score_multiplier = evaluation['weighted_total'] / 7.0
        total_lux = int(template['base_lux'] * score_multiplier)
        
        # Generate DAG
        dag = self._generate_dag(seed_id, seed_content, template, priority, total_lux)
        
        # Add metadata
        dag['seed_id'] = seed_id
        dag['evaluation_id'] = evaluation['eval_id']
        dag['evaluation_score'] = evaluation['weighted_total']
        dag['created_at'] = datetime.now().isoformat()
        dag['total_lux'] = total_lux
        dag['priority'] = priority
        dag['seed_type'] = seed_type
        
        self.generated_tasks.append(dag)
        return dag
    
    def _generate_dag(self, seed_id, content, template, priority, total_lux):
        """生成DAG任务树"""
        tasks = []
        dependencies = {}
        prev_task_id = None
        
        for i, phase in enumerate(template['phases']):
            phase_name = phase['name']
            task_id = f"task-{hashlib.md5(f'{seed_id}-{phase_name}-{time.time()}'.encode()).hexdigest()[:16]}"
            
            phase_lux = int(total_lux * phase['weight'])
            
            task = {
                'task_id': task_id,
                'title': f"{phase['name']} - {content[:50]}",
                'description': f"Phase {i+1}/{len(template['phases'])}: {phase['name']}. Seed: {content[:200]}",
                'priority': priority,
                'lux_reward': max(10, phase_lux),
                'flywheel_phase': phase['type'],
                'phase_index': i,
                'tags': [phase['type'], seed_id[:12]]
            }
            tasks.append(task)
            
            # Build dependency chain (sequential DAG)
            if prev_task_id:
                dependencies[task_id] = [prev_task_id]
            else:
                dependencies[task_id] = []
            
            prev_task_id = task_id
        
        return {
            'tasks': tasks,
            'dependencies': dependencies,
            'dag_type': 'sequential',
            'task_count': len(tasks)
        }
    
    def submit_to_hub(self, dag, dry_run=True):
        """将DAG任务树提交到Hub"""
        if dry_run:
            return {
                'status': 'dry_run',
                'task_count': dag['task_count'],
                'total_lux': dag['total_lux'],
                'tasks': [{'id': t['task_id'], 'title': t['title'], 'lux': t['lux_reward']} for t in dag['tasks']]
            }
        
        # Real submission via Hub API
        import urllib.request
        results = []
        admin_key = ''
        try:
            admin_key = open(r'D:\ClawMatrix\.hub_admin_key').read().strip()
        except:
            pass
        
        for task in dag['tasks']:
            payload = json.dumps({
                'title': task['title'],
                'description': task['description'],
                'priority': task['priority'],
                'lux_reward': task['lux_reward'],
                'tags': task.get('tags', [])
            }).encode()
            
            try:
                req = urllib.request.Request(
                    f"{self.hub_url}/api/v1/task/create",
                    data=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'X-Matrix-Secret': admin_key
                    }
                )
                resp = urllib.request.urlopen(req, timeout=10)
                result = json.loads(resp.read())
                results.append({'task_id': task['task_id'], 'status': 'created', 'hub_response': result})
            except Exception as e:
                results.append({'task_id': task['task_id'], 'status': 'failed', 'error': str(e)})
        
        return {'status': 'submitted', 'results': results}
    
    def get_generated_tasks(self):
        return self.generated_tasks


# === Self-test ===
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    
    engine = SeedToTaskEngine()
    
    # Mock evaluation result
    mock_eval = {
        'eval_id': 'eval-test123',
        'weighted_total': 7.5,
        'decision': 'approve'
    }
    
    # Convert seed
    dag = engine.convert_seed(
        'seed-test-001',
        'Build a distributed clearing system for securities firms with event sourcing and double-entry ledger',
        mock_eval,
        seed_type='development'
    )
    
    print("=== Seed-to-Task Engine Test ===")
    print(f"Seed Type: {dag['seed_type']}")
    print(f"Priority: {dag['priority']}")
    print(f"Total LUX: {dag['total_lux']}")
    print(f"Task Count: {dag['task_count']}")
    print(f"\nGenerated DAG:")
    for t in dag['tasks']:
        deps = dag['dependencies'].get(t['task_id'], [])
        dep_str = f" (depends on: {deps[0][:12]}...)" if deps else " (root)"
        print(f"  [{t['flywheel_phase']}] {t['title']} - {t['lux_reward']}L{dep_str}")
    
    # Dry run submission
    result = engine.submit_to_hub(dag, dry_run=True)
    print(f"\nDry Run: {result['status']}, {result['task_count']} tasks, {result['total_lux']}L")
    
    print("\nSeed-to-Task Engine: OK")
