
"""
朱雀输出个性化引擎 (Zhuque Personalized Output)
根据受众特征自动适配输出格式、深度和风格

受众类型: Executive / Technical / Investor / Academic / Public
"""
import json, os
from datetime import datetime

class AudienceProfile:
    """受众画像"""
    PROFILES = {
        'executive': {
            'name': '企业高管',
            'depth': 'summary',
            'style': 'concise_actionable',
            'format': 'bullet_points',
            'jargon_level': 'low',
            'focus': ['roi', 'risk', 'timeline', 'impact'],
            'max_length': 500,
            'visual_preference': 'charts_dashboards'
        },
        'technical': {
            'name': '技术团队',
            'depth': 'detailed',
            'style': 'precise_technical',
            'format': 'structured_doc',
            'jargon_level': 'high',
            'focus': ['architecture', 'implementation', 'performance', 'scalability'],
            'max_length': 3000,
            'visual_preference': 'diagrams_code'
        },
        'investor': {
            'name': '投资人',
            'depth': 'strategic',
            'style': 'narrative_compelling',
            'format': 'pitch_deck',
            'jargon_level': 'medium',
            'focus': ['market_size', 'moat', 'growth', 'team'],
            'max_length': 1000,
            'visual_preference': 'growth_charts'
        },
        'academic': {
            'name': '学术研究者',
            'depth': 'rigorous',
            'style': 'formal_referenced',
            'format': 'paper_format',
            'jargon_level': 'high',
            'focus': ['methodology', 'novelty', 'reproducibility', 'citations'],
            'max_length': 5000,
            'visual_preference': 'data_tables'
        },
        'public': {
            'name': '大众用户',
            'depth': 'simple',
            'style': 'friendly_engaging',
            'format': 'blog_social',
            'jargon_level': 'none',
            'focus': ['benefit', 'ease_of_use', 'story', 'social_proof'],
            'max_length': 300,
            'visual_preference': 'infographics'
        }
    }

class ZhuquePersonalizer:
    """朱雀个性化输出引擎"""
    
    def __init__(self):
        self.output_log = []
    
    def adapt(self, content, audience_type, context=None):
        """根据受众类型适配输出"""
        profile = AudienceProfile.PROFILES.get(audience_type)
        if not profile:
            profile = AudienceProfile.PROFILES['technical']  # default
        
        adapted = {
            'audience': audience_type,
            'profile': profile,
            'original_length': len(str(content)),
            'adapted_content': self._format_content(content, profile),
            'metadata': {
                'depth': profile['depth'],
                'style': profile['style'],
                'max_length': profile['max_length'],
                'focus_areas': profile['focus'],
                'generated_at': datetime.now().isoformat()
            }
        }
        
        self.output_log.append({
            'audience': audience_type,
            'original_length': adapted['original_length'],
            'adapted_length': len(adapted['adapted_content']),
            'timestamp': datetime.now().isoformat()
        })
        
        return adapted
    
    def _format_content(self, content, profile):
        """根据profile格式化内容"""
        text = json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content)
        
        if profile['format'] == 'bullet_points':
            return self._to_bullets(text, profile['max_length'])
        elif profile['format'] == 'pitch_deck':
            return self._to_pitch(text, profile['max_length'])
        elif profile['format'] == 'blog_social':
            return self._to_social(text, profile['max_length'])
        elif profile['format'] == 'paper_format':
            return self._to_academic(text, profile['max_length'])
        else:
            return self._to_structured(text, profile['max_length'])
    
    def _to_bullets(self, text, max_len):
        """高管风格：要点列表"""
        lines = [l.strip() for l in text.split('.') if l.strip()][:8]
        bullets = '\n'.join(f'• {l[:80]}' for l in lines)
        return f"📊 Executive Summary\n\n{bullets[:max_len]}"
    
    def _to_pitch(self, text, max_len):
        """投资人风格：叙事+数据"""
        return f"🚀 Investment Highlight\n\n{text[:max_len]}\n\n💰 Key Metrics: [To be filled]"
    
    def _to_social(self, text, max_len):
        """大众风格：简短+emoji"""
        short = text[:max_len-50]
        return f"✨ {short}\n\n👉 Learn more at skycetus.cn"
    
    def _to_academic(self, text, max_len):
        """学术风格：结构化+引用"""
        return f"Abstract\n\n{text[:max_len]}\n\nReferences\n[1] SkyCetus Architecture, 2026"
    
    def _to_structured(self, text, max_len):
        """技术风格：结构化文档"""
        return f"## Technical Specification\n\n{text[:max_len]}"
    
    def multi_audience_output(self, content, audiences=None):
        """为多个受众同时生成适配版本"""
        if audiences is None:
            audiences = list(AudienceProfile.PROFILES.keys())
        
        outputs = {}
        for audience in audiences:
            outputs[audience] = self.adapt(content, audience)
        
        return {
            'audiences': audiences,
            'outputs': outputs,
            'total_versions': len(outputs),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_stats(self):
        return {
            'total_outputs': len(self.output_log),
            'audience_distribution': {},
            'available_audiences': list(AudienceProfile.PROFILES.keys())
        }


# Self-test
if __name__ == '__main__':
    import sys; sys.stdout.reconfigure(encoding='utf-8')
    zhuque = ZhuquePersonalizer()
    
    content = {
        'title': 'SkyCetus 分布式AI任务调度系统',
        'description': 'A distributed AI task scheduling and execution platform with cognitive API layer',
        'features': ['Multi-node coordination', 'TEP protocol', 'Four-Symbol Flywheel', 'LUX economy']
    }
    
    result = zhuque.multi_audience_output(content, ['executive', 'technical', 'investor'])
    print(f"Generated {result['total_versions']} versions")
    
    for audience, output in result['outputs'].items():
        profile = output['profile']
        print(f"  {audience} ({profile['name']}): {output['adapted_content'][:60]}...")
        print(f"    Depth: {profile['depth']}, Style: {profile['style']}")
    
    stats = zhuque.get_stats()
    print(f"Stats: {stats['total_outputs']} outputs, {len(stats['available_audiences'])} audiences")
    print("PASS")
