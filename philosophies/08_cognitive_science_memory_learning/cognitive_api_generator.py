
"""
认知API自动生成器 (Cognitive API Auto-Generator)
根据问题域自动生成新的认知API模板，实现飞轮自我扩展

核心: 分析问题 → 识别缺失能力 → 生成新API → 注册到系统
"""
import json, os, hashlib
from datetime import datetime

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'cognitive_templates')
os.makedirs(TEMPLATE_DIR, exist_ok=True)

# 基础API模式库
BASE_PATTERNS = {
    'analysis': {
        'description': '分析型API：拆解输入，输出结构化洞察',
        'input_schema': {'problem': 'str', 'context': 'dict'},
        'output_schema': {'findings': 'list', 'confidence': 'float', 'recommendations': 'list'},
        'beast': 'qinglong',
        'phase': 'diverge'
    },
    'evaluation': {
        'description': '评估型API：对方案打分和排序',
        'input_schema': {'candidates': 'list', 'criteria': 'list'},
        'output_schema': {'scores': 'dict', 'ranking': 'list', 'rationale': 'str'},
        'beast': 'baihu',
        'phase': 'evaluate'
    },
    'synthesis': {
        'description': '综合型API：合并多个输入为统一输出',
        'input_schema': {'inputs': 'list', 'constraints': 'list'},
        'output_schema': {'synthesis': 'dict', 'trade_offs': 'list', 'confidence': 'float'},
        'beast': 'xuanwu',
        'phase': 'converge'
    },
    'output': {
        'description': '输出型API：将内部结果转化为面向受众的交付物',
        'input_schema': {'content': 'dict', 'audience': 'str', 'format': 'str'},
        'output_schema': {'deliverable': 'str', 'metadata': 'dict'},
        'beast': 'zhuque',
        'phase': 'output'
    }
}

class CognitiveAPIGenerator:
    """认知API自动生成器"""
    
    def __init__(self):
        self.registry_path = os.path.join(TEMPLATE_DIR, 'api_registry.json')
        self.registry = self._load_registry()
    
    def _load_registry(self):
        if os.path.exists(self.registry_path):
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'apis': {}, 'version': 1, 'created_at': datetime.now().isoformat()}
    
    def _save_registry(self):
        self.registry['version'] += 1
        self.registry['updated_at'] = datetime.now().isoformat()
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            json.dump(self.registry, f, ensure_ascii=False, indent=2)
    
    def analyze_gap(self, problem_domain, existing_apis=None):
        """分析当前API覆盖的空白"""
        existing = existing_apis or list(self.registry['apis'].keys())
        
        # 基于问题域推断需要的能力
        domain_keywords = problem_domain.lower()
        gaps = []
        
        capability_map = {
            'risk': {'id': 'SC-RISK', 'type': 'evaluation', 'name': 'Risk Assessment'},
            'cost': {'id': 'SC-COST', 'type': 'analysis', 'name': 'Cost Analysis'},
            'timeline': {'id': 'SC-TIME', 'type': 'analysis', 'name': 'Timeline Estimation'},
            'stakeholder': {'id': 'SC-STAKE', 'type': 'analysis', 'name': 'Stakeholder Analysis'},
            'impact': {'id': 'SC-IMPACT', 'type': 'evaluation', 'name': 'Impact Assessment'},
            'feasibility': {'id': 'SC-FEAS', 'type': 'evaluation', 'name': 'Feasibility Check'},
            'integration': {'id': 'SC-INTEG', 'type': 'synthesis', 'name': 'Integration Planning'},
            'communication': {'id': 'SC-COMM', 'type': 'output', 'name': 'Communication Design'},
            'metric': {'id': 'SC-METRIC', 'type': 'analysis', 'name': 'Metrics Definition'},
            'scenario': {'id': 'SC-SCENARIO', 'type': 'evaluation', 'name': 'Scenario Planning'},
        }
        
        for keyword, api_def in capability_map.items():
            if keyword in domain_keywords and api_def['id'] not in existing:
                gaps.append(api_def)
        
        # Always suggest at least one if no specific match
        if not gaps and len(existing) < 15:
            for api_def in capability_map.values():
                if api_def['id'] not in existing:
                    gaps.append(api_def)
                    break
        
        return gaps
    
    def generate_api(self, api_id, api_name, api_type, domain_context=''):
        """生成新的认知API定义"""
        pattern = BASE_PATTERNS.get(api_type, BASE_PATTERNS['analysis'])
        
        api_def = {
            'id': api_id,
            'name': api_name,
            'type': api_type,
            'beast': pattern['beast'],
            'phase': pattern['phase'],
            'description': f'{api_name}: {pattern["description"]}',
            'input_schema': pattern['input_schema'],
            'output_schema': pattern['output_schema'],
            'system_prompt': f'You are a {api_name} specialist. Analyze the given problem and provide structured {api_type} output.',
            'domain_context': domain_context,
            'template_logic': self._generate_template_logic(api_id, api_type),
            'created_at': datetime.now().isoformat(),
            'version': 1
        }
        
        # Register
        self.registry['apis'][api_id] = api_def
        self._save_registry()
        
        return api_def
    
    def _generate_template_logic(self, api_id, api_type):
        """生成模板执行逻辑"""
        if api_type == 'analysis':
            return {
                'steps': ['decompose_input', 'identify_factors', 'assess_each', 'synthesize_findings'],
                'output_format': 'structured_analysis'
            }
        elif api_type == 'evaluation':
            return {
                'steps': ['define_criteria', 'score_candidates', 'rank', 'explain_rationale'],
                'output_format': 'scored_ranking'
            }
        elif api_type == 'synthesis':
            return {
                'steps': ['collect_inputs', 'find_conflicts', 'resolve', 'merge'],
                'output_format': 'unified_output'
            }
        else:
            return {
                'steps': ['format_content', 'adapt_to_audience', 'generate_deliverable'],
                'output_format': 'audience_ready'
            }
    
    def batch_generate(self, problem_domain, existing_apis=None):
        """批量生成缺失的API"""
        gaps = self.analyze_gap(problem_domain, existing_apis)
        generated = []
        for gap in gaps:
            api = self.generate_api(gap['id'], gap['name'], gap['type'], problem_domain)
            generated.append(api)
        return generated
    
    def get_status(self):
        return {
            'registered_apis': len(self.registry['apis']),
            'api_ids': list(self.registry['apis'].keys()),
            'version': self.registry['version'],
            'base_patterns': list(BASE_PATTERNS.keys())
        }


# Self-test
if __name__ == '__main__':
    gen = CognitiveAPIGenerator()
    
    # Test gap analysis
    gaps = gen.analyze_gap('risk assessment and cost timeline feasibility')
    print(f"Gaps found: {len(gaps)}")
    
    # Test batch generate
    generated = gen.batch_generate('risk cost timeline stakeholder impact',
                                    existing_apis=['SC-USER','SC-PROB','SC-CON','SC-COMP','SC-RES'])
    print(f"Generated: {len(generated)} new APIs")
    for api in generated:
        print(f"  {api['id']}: {api['name']} ({api['beast']}/{api['phase']})")
    
    status = gen.get_status()
    print(f"Registry: {status['registered_apis']} APIs, v{status['version']}")
    print("PASS")
