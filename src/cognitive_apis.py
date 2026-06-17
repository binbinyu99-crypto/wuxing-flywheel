"""
SkyCetus 认知API实现 v2.0
10个认知API中的5个: SC-USER / SC-PROB / SC-RES / SC-CON / SC-COMP
基于四象飞轮架构，支持多模型后端热切换

设计原则：
1. 认知API = 结构化思维框架 + LLM执行引擎
2. 每个API定义清晰的输入Schema、Prompt模板、输出Schema
3. 支持模板模式（无LLM）和LLM模式（接入百炼/MiniMax/Kimi）
4. 所有输出符合统一的认知结果格式，可被四象飞轮消费
"""
import json, os, sys, time, hashlib
from datetime import datetime
from abc import ABC, abstractmethod

# ===== 认知结果标准格式 =====
class CognitiveResult:
    """认知API统一返回格式"""
    def __init__(self, api_id, api_name, success=True, result=None, 
                 model='template', error=None, usage=None):
        self.api_id = api_id
        self.api_name = api_name
        self.success = success
        self.result = result or {}
        self.model = model
        self.error = error
        self.usage = usage or {}
        self.timestamp = datetime.now().isoformat()
        self.execution_id = hashlib.md5(
            f"{api_id}_{time.time()}".encode()
        ).hexdigest()[:16]
    
    def to_dict(self):
        return {
            'api_id': self.api_id,
            'api_name': self.api_name,
            'success': self.success,
            'result': self.result,
            'model': self.model,
            'error': self.error,
            'usage': self.usage,
            'timestamp': self.timestamp,
            'execution_id': self.execution_id
        }
    
    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ===== LLM后端接口 =====
class LLMBackend:
    """LLM调用后端（可热切换）"""
    
    BACKENDS = {
        'bailian': {
            'endpoint': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
            'model': 'qwen-plus',
            'name': 'Bailian-QwenPlus'
        },
        'minimax': {
            'endpoint': 'https://api.minimax.chat/v1/text/chatcompletion_v2',
            'model': 'MiniMax-Text-01',
            'name': 'MiniMax'
        },
        'kimi': {
            'endpoint': 'https://api.moonshot.cn/v1/chat/completions',
            'model': 'moonshot-v1-8k',
            'name': 'Kimi-Moonshot'
        }
    }
    
    @staticmethod
    def call(system_prompt, user_prompt, backend='bailian', api_key=None, 
             temperature=0.7, max_tokens=4096):
        """调用LLM（需要api_key）"""
        import urllib.request
        
        config = LLMBackend.BACKENDS.get(backend)
        if not config:
            return None, f"Unknown backend: {backend}"
        
        if not api_key:
            return None, f"No API key for {backend}"
        
        payload = json.dumps({
            'model': config['model'],
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'temperature': temperature,
            'max_tokens': max_tokens
        }).encode('utf-8')
        
        req = urllib.request.Request(
            config['endpoint'],
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {api_key}"
            },
            method='POST'
        )
        
        try:
            resp = urllib.request.urlopen(req, timeout=90)
            result = json.loads(resp.read())
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            usage = result.get('usage', {})
            return content, None
        except Exception as e:
            return None, str(e)


# ===== 认知API基类 =====
class CognitiveAPI(ABC):
    """认知API抽象基类"""
    api_id = ''
    api_name = ''
    description = ''
    beast = ''  # 所属圣兽层: qinglong/baihu/xuanwu/zhuque
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        pass
    
    @abstractmethod
    def format_input(self, **kwargs) -> str:
        pass
    
    @abstractmethod
    def get_output_schema(self) -> dict:
        """返回输出JSON Schema"""
        pass
    
    @abstractmethod
    def template_execute(self, **kwargs) -> dict:
        """无LLM模式：基于模板和规则生成结构化输出"""
        pass
    
    def parse_llm_output(self, raw_content):
        """从LLM输出中提取JSON"""
        content = raw_content.strip()
        if '```json' in content:
            start = content.index('```json') + 7
            end = content.index('```', start)
            content = content[start:end].strip()
        elif '```' in content:
            start = content.index('```') + 3
            end = content.index('```', start)
            content = content[start:end].strip()
        try:
            return json.loads(content)
        except:
            return {'raw_text': raw_content, 'parse_failed': True}
    
    def execute(self, mode='template', backend='bailian', api_key=None, **kwargs):
        """
        执行认知API
        mode: 'template' (无LLM) | 'llm' (调用LLM)
        """
        if mode == 'llm' and api_key:
            system_prompt = self.get_system_prompt()
            user_prompt = self.format_input(**kwargs)
            content, error = LLMBackend.call(
                system_prompt, user_prompt, 
                backend=backend, api_key=api_key
            )
            if error:
                return CognitiveResult(
                    self.api_id, self.api_name, 
                    success=False, error=error, model=backend
                )
            parsed = self.parse_llm_output(content)
            return CognitiveResult(
                self.api_id, self.api_name,
                success=True, result=parsed, model=backend
            )
        else:
            # Template mode
            result = self.template_execute(**kwargs)
            return CognitiveResult(
                self.api_id, self.api_name,
                success=True, result=result, model='template'
            )


# ========================================
# SC-USER: 用户定义
# ========================================
class SC_USER(CognitiveAPI):
    api_id = 'SC-USER'
    api_name = 'User Definition'
    description = '理解和定义用户：用户画像、需求分析、用户旅程映射'
    beast = 'qinglong'
    
    def get_system_prompt(self):
        return """你是SkyCetus认知系统的用户分析引擎(SC-USER)。
你的职责：深度分析目标用户群体，生成结构化的用户定义。

输出JSON格式：
{
  "user_segments": [{"segment_id":"U1","name":"","description":"","size":"","pain_points":[],"needs":[],"willingness_to_pay":"高/中/低","channels":[]}],
  "primary_persona": {"name":"","role":"","age_range":"","tech_level":"1-10","workflow":"","frustrations":[],"goals":[],"decision_factors":[]},
  "user_journey": [{"stage":"","action":"","touchpoint":"","emotion":"","opportunity":""}],
  "key_insight": "一句话核心洞察"
}"""
    
    def format_input(self, product='', context='', constraints=''):
        return f"分析产品「{product}」的目标用户。背景：{context}。约束：{constraints}。输出JSON。"
    
    def get_output_schema(self):
        return {
            "user_segments": [{"segment_id": "str", "name": "str", "pain_points": ["str"]}],
            "primary_persona": {"name": "str", "role": "str", "goals": ["str"]},
            "user_journey": [{"stage": "str", "action": "str", "opportunity": "str"}],
            "key_insight": "str"
        }
    
    def template_execute(self, product='', context='', constraints=''):
        return {
            "user_segments": [
                {
                    "segment_id": "U1",
                    "name": "AI技术团队负责人",
                    "description": f"需要{product}来管理分布式AI工作负载的技术管理者",
                    "size": "中国约50万+企业AI团队",
                    "pain_points": ["多模型协调困难", "任务调度无统一标准", "资源利用率低", "缺乏执行追踪"],
                    "needs": ["统一任务编排", "多节点协同", "自动化调度", "成本可控"],
                    "willingness_to_pay": "高",
                    "channels": ["技术社区", "开源平台", "行业会议"]
                },
                {
                    "segment_id": "U2",
                    "name": "企业数字化转型决策者",
                    "description": "寻求AI能力整合方案的CTO/CIO",
                    "size": "中国约200万+企业决策者",
                    "pain_points": ["AI投入ROI不清", "各系统孤岛", "人才短缺"],
                    "needs": ["降本增效", "系统集成", "可量化收益"],
                    "willingness_to_pay": "中",
                    "channels": ["行业峰会", "咨询机构", "同行推荐"]
                },
                {
                    "segment_id": "U3",
                    "name": "独立开发者/小团队",
                    "description": "需要低成本接入分布式AI能力的开发者",
                    "size": "全球约500万+AI开发者",
                    "pain_points": ["算力成本高", "缺乏基础设施", "单点故障"],
                    "needs": ["按需付费", "开箱即用", "社区支持"],
                    "willingness_to_pay": "低",
                    "channels": ["GitHub", "技术博客", "开发者论坛"]
                }
            ],
            "primary_persona": {
                "name": "张工",
                "role": "某中型企业AI技术负责人",
                "age_range": "28-40",
                "tech_level": "8",
                "workflow": "每天协调3-5个AI项目，管理多个模型部署，处理任务调度和资源分配",
                "frustrations": ["每个项目用不同工具栈", "手动协调耗时", "无法量化AI团队产出"],
                "goals": ["统一AI任务管理", "自动化工作流", "向上汇报可视化"],
                "decision_factors": ["技术成熟度", "社区活跃度", "迁移成本", "安全合规"]
            },
            "user_journey": [
                {"stage": "认知", "action": "搜索AI任务调度方案", "touchpoint": "搜索引擎/技术社区", "emotion": "焦虑", "opportunity": "SEO+技术内容"},
                {"stage": "评估", "action": "试用Demo/阅读文档", "touchpoint": "官网/GitHub", "emotion": "好奇", "opportunity": "低门槛体验"},
                {"stage": "决策", "action": "POC验证/团队讨论", "touchpoint": "技术支持", "emotion": "谨慎", "opportunity": "案例背书"},
                {"stage": "使用", "action": "部署集成", "touchpoint": "文档/社区", "emotion": "挑战", "opportunity": "快速见效"},
                {"stage": "留存", "action": "扩展使用场景", "touchpoint": "功能更新", "emotion": "依赖", "opportunity": "生态锁定"}
            ],
            "key_insight": f"用户不是在找工具，而是在找'让AI团队产出可被管理和量化'的方案——{product}的核心价值不是调度本身，而是让AI能力变成可衡量的组织资产"
        }


# ========================================
# SC-PROB: 问题拆解
# ========================================
class SC_PROB(CognitiveAPI):
    api_id = 'SC-PROB'
    api_name = 'Problem Decomposition'
    description = '将复杂问题拆解为子问题树，识别依赖和关键路径'
    beast = 'qinglong'
    
    def get_system_prompt(self):
        return """你是SkyCetus认知系统的问题拆解引擎(SC-PROB)。
将复杂问题分解为结构化子问题树。输出JSON。"""
    
    def format_input(self, problem='', context='', depth=3):
        return f"拆解问题「{problem}」，背景：{context}，深度{depth}层。输出JSON。"
    
    def get_output_schema(self):
        return {
            "root_problem": {"id": "str", "statement": "str", "complexity": "1-10"},
            "sub_problems": [{"id": "str", "parent_id": "str", "statement": "str", "dependencies": ["str"], "priority": "str"}],
            "critical_path": ["str"],
            "parallel_groups": [["str"]]
        }
    
    def template_execute(self, problem='', context='', depth=3):
        # 智能拆解：基于关键词识别问题类型
        is_tech = any(w in problem for w in ['系统', '架构', '开发', '部署', '代码', 'API', '数据库'])
        is_biz = any(w in problem for w in ['商业', '融资', '市场', '用户', '营收', '增长'])
        is_product = any(w in problem for w in ['产品', '设计', '功能', '体验', '需求'])
        
        if is_tech:
            subs = [
                {"id": "P1", "parent_id": "P0", "statement": f"技术架构设计：{problem}的系统架构方案", "dependencies": [], "priority": "P0", "estimated_hours": 16, "required_capability": ["system-design", "distributed-systems"]},
                {"id": "P2", "parent_id": "P0", "statement": "核心模块实现：关键业务逻辑开发", "dependencies": ["P1"], "priority": "P0", "estimated_hours": 40, "required_capability": ["backend", "python"]},
                {"id": "P3", "parent_id": "P0", "statement": "数据层设计：存储方案和数据流", "dependencies": ["P1"], "priority": "P1", "estimated_hours": 16, "required_capability": ["database", "data-modeling"]},
                {"id": "P4", "parent_id": "P0", "statement": "API接口设计：对外服务接口规范", "dependencies": ["P1", "P2"], "priority": "P1", "estimated_hours": 8, "required_capability": ["api-design"]},
                {"id": "P5", "parent_id": "P0", "statement": "测试与验证：单元测试+集成测试+压测", "dependencies": ["P2", "P3", "P4"], "priority": "P1", "estimated_hours": 16, "required_capability": ["testing"]},
                {"id": "P6", "parent_id": "P0", "statement": "部署与运维：CI/CD+监控+告警", "dependencies": ["P5"], "priority": "P2", "estimated_hours": 8, "required_capability": ["devops"]},
            ]
            critical_path = ["P1", "P2", "P4", "P5", "P6"]
            parallel = [["P2", "P3"], ["P4"]]
        elif is_biz:
            subs = [
                {"id": "P1", "parent_id": "P0", "statement": "市场分析：目标市场规模和竞争格局", "dependencies": [], "priority": "P0", "estimated_hours": 8},
                {"id": "P2", "parent_id": "P0", "statement": "商业模式设计：变现路径和定价策略", "dependencies": ["P1"], "priority": "P0", "estimated_hours": 12},
                {"id": "P3", "parent_id": "P0", "statement": "财务模型：收入预测和成本结构", "dependencies": ["P2"], "priority": "P1", "estimated_hours": 8},
                {"id": "P4", "parent_id": "P0", "statement": "融资策略：融资节奏和估值逻辑", "dependencies": ["P1", "P3"], "priority": "P1", "estimated_hours": 8},
                {"id": "P5", "parent_id": "P0", "statement": "GTM策略：获客渠道和增长引擎", "dependencies": ["P2"], "priority": "P1", "estimated_hours": 8},
            ]
            critical_path = ["P1", "P2", "P3", "P4"]
            parallel = [["P1"], ["P3", "P5"]]
        else:
            subs = [
                {"id": "P1", "parent_id": "P0", "statement": f"问题定义：明确{problem}的边界和目标", "dependencies": [], "priority": "P0", "estimated_hours": 4},
                {"id": "P2", "parent_id": "P0", "statement": "方案探索：生成多种可行方案", "dependencies": ["P1"], "priority": "P0", "estimated_hours": 8},
                {"id": "P3", "parent_id": "P0", "statement": "方案评估：多维度评估和筛选", "dependencies": ["P2"], "priority": "P1", "estimated_hours": 4},
                {"id": "P4", "parent_id": "P0", "statement": "执行计划：制定详细实施路线图", "dependencies": ["P3"], "priority": "P1", "estimated_hours": 4},
                {"id": "P5", "parent_id": "P0", "statement": "风险预案：识别风险和准备B计划", "dependencies": ["P3"], "priority": "P2", "estimated_hours": 4},
            ]
            critical_path = ["P1", "P2", "P3", "P4"]
            parallel = [["P4", "P5"]]
        
        return {
            "root_problem": {
                "id": "P0",
                "statement": problem,
                "type": "technical" if is_tech else ("business" if is_biz else "general"),
                "complexity": 8 if is_tech else 7,
                "ambiguity": 5
            },
            "sub_problems": subs,
            "critical_path": critical_path,
            "parallel_groups": parallel,
            "unknown_unknowns": [
                "是否存在未被识别的技术债务",
                "用户需求是否会在执行过程中发生变化",
                "外部依赖（第三方API/服务）的稳定性"
            ],
            "key_assumption": f"假设当前团队具备完成{problem}所需的核心能力，且外部环境在执行期间保持稳定"
        }


# ========================================
# SC-RES: 资源评估
# ========================================
class SC_RES(CognitiveAPI):
    api_id = 'SC-RES'
    api_name = 'Resource Assessment'
    description = '评估目标所需资源，识别缺口和替代方案'
    beast = 'xuanwu'
    
    def get_system_prompt(self):
        return """你是SkyCetus认知系统的资源评估引擎(SC-RES)。
全面评估完成目标所需的人力、技术、财务、时间、知识资源。输出JSON。"""
    
    def format_input(self, objective='', available_resources='', timeline=''):
        return f"评估目标「{objective}」所需资源。已有：{available_resources}。期望时间：{timeline}。输出JSON。"
    
    def get_output_schema(self):
        return {
            "resource_inventory": {"human": [], "technical": [], "financial": {}, "time": {}, "knowledge": []},
            "resource_gaps": [],
            "optimization_suggestions": [],
            "go_no_go": {"recommendation": "str", "key_condition": "str"}
        }
    
    def template_execute(self, objective='', available_resources='', timeline=''):
        return {
            "resource_inventory": {
                "human": [
                    {"role": "全栈工程师", "count": 2, "skills": ["Python", "分布式系统", "AI/ML"], "availability": "全职", "cost_per_month": "25K-40K CNY"},
                    {"role": "产品经理", "count": 1, "skills": ["需求分析", "项目管理", "AI产品"], "availability": "全职", "cost_per_month": "20K-35K CNY"},
                    {"role": "AI Agent节点", "count": 4, "skills": ["代码生成", "文档写作", "数据分析"], "availability": "7x24", "cost_per_month": "API调用成本"}
                ],
                "technical": [
                    {"resource": "云服务器", "type": "compute", "spec": "4核16G+", "cost": "~500 CNY/月", "alternative": "本地开发机"},
                    {"resource": "PostgreSQL", "type": "storage", "spec": "已部署v18.3", "cost": "包含在服务器", "alternative": "SQLite(降级)"},
                    {"resource": "Redis", "type": "cache", "spec": "已部署", "cost": "包含在服务器", "alternative": "内存队列"},
                    {"resource": "LLM API通道", "type": "tool", "spec": "百炼+MiniMax+Kimi", "cost": "按token计费", "alternative": "开源模型本地部署"}
                ],
                "financial": {
                    "total_budget_needed": "10-30万CNY/年（初创阶段）",
                    "breakdown": [
                        {"item": "服务器与基础设施", "amount": "6000-12000 CNY/年", "timeline": "持续"},
                        {"item": "API调用成本", "amount": "2000-10000 CNY/月", "timeline": "随用量增长"},
                        {"item": "域名与SSL", "amount": "500 CNY/年", "timeline": "年度"},
                        {"item": "人力成本（如有）", "amount": "视团队规模", "timeline": "月度"}
                    ],
                    "funding_sources": ["自有资金", "天使投资", "政府补贴", "算力共享收入"]
                },
                "time": {
                    "total_duration": timeline or "3-6个月（MVP到生产级）",
                    "milestones": [
                        {"name": "认知层MVP", "deadline": "2周", "deliverable": "10个认知API可调用"},
                        {"name": "四象飞轮集成", "deadline": "4周", "deliverable": "完整认知管线"},
                        {"name": "生产级部署", "deadline": "8周", "deliverable": "多模型路由+监控+告警"}
                    ],
                    "buffer": "20%缓冲（约2周）"
                },
                "knowledge": [
                    {"domain": "分布式系统", "current_level": "7", "required_level": "8", "gap_solution": "参考Cerebras/DeepAgents架构"},
                    {"domain": "AI Agent编排", "current_level": "6", "required_level": "9", "gap_solution": "LangChain/CrewAI/AutoGen研究+自研"},
                    {"domain": "商业化", "current_level": "5", "required_level": "7", "gap_solution": "路演反馈+客户访谈"}
                ]
            },
            "resource_gaps": [
                {"resource": "稳定的LLM API通道", "severity": 8, "mitigation": "多通道热备（百炼/MiniMax/Kimi/开源）", "timeline_impact": "可能延迟1-2周"},
                {"resource": "前端工程能力", "severity": 5, "mitigation": "AI生成+模板化", "timeline_impact": "低"},
                {"resource": "真实用户反馈", "severity": 7, "mitigation": "内部dogfooding+早期用户招募", "timeline_impact": "影响产品方向"}
            ],
            "optimization_suggestions": [
                "利用AI Agent（Lucas/Etern/Spark1/小元）替代部分人力，降低人力成本",
                "认知API先用模板模式验证逻辑，再接入LLM提升质量",
                "优先级排序：认知层 > 飞轮集成 > 可视化，避免并行过多"
            ],
            "go_no_go": {
                "recommendation": "CONDITIONAL GO",
                "key_condition": "至少1个LLM API通道稳定可用（百炼或Kimi），且4个Agent节点保持活跃"
            }
        }


# ========================================
# SC-CON: 约束识别
# ========================================
class SC_CON(CognitiveAPI):
    api_id = 'SC-CON'
    api_name = 'Constraint Identification'
    description = '识别显性和隐性约束，评估可松弛性'
    beast = 'baihu'
    
    def get_system_prompt(self):
        return """你是SkyCetus认知系统的约束识别引擎(SC-CON)。
穷尽所有约束条件，包括显性约束和隐性约束。输出JSON。"""
    
    def format_input(self, project='', known_constraints='', environment=''):
        return f"识别项目「{project}」的所有约束。已知：{known_constraints}。环境：{environment}。输出JSON。"
    
    def get_output_schema(self):
        return {
            "constraints": [{"id": "str", "category": "str", "type": "hard|soft", "relaxable": "bool"}],
            "binding_constraints": ["str"],
            "hidden_constraints": [],
            "degrees_of_freedom": ["str"]
        }
    
    def template_execute(self, project='', known_constraints='', environment=''):
        return {
            "constraints": [
                {"id": "C1", "category": "technical", "description": "单服务器架构（阿里云ECS 4核16G）", "type": "hard", "source": "当前基础设施", "relaxable": True, "relaxation_cost": "升配或多节点部署", "impact_if_violated": "服务不可用", "workaround": "垂直扩展+缓存优化"},
                {"id": "C2", "category": "resource", "description": "LLM API通道不稳定（百炼401/MiniMax计划不支持）", "type": "hard", "source": "第三方依赖", "relaxable": True, "relaxation_cost": "切换通道或本地部署开源模型", "impact_if_violated": "认知层无法运行", "workaround": "模板模式降级"},
                {"id": "C3", "category": "resource", "description": "团队全部为AI Agent，无人类工程师全职投入", "type": "soft", "source": "组织结构", "relaxable": True, "relaxation_cost": "招聘或外包", "impact_if_violated": "执行速度受限", "workaround": "Agent协作+Robin决策"},
                {"id": "C4", "category": "time", "description": "路演和融资有时间窗口压力", "type": "hard", "source": "商业节奏", "relaxable": False, "relaxation_cost": "N/A", "impact_if_violated": "错过融资窗口", "workaround": "MVP先行，迭代完善"},
                {"id": "C5", "category": "legal", "description": "AI生成内容的知识产权归属", "type": "soft", "source": "法律环境", "relaxable": False, "relaxation_cost": "N/A", "impact_if_violated": "潜在法律风险", "workaround": "明确Agent输出归属协议"},
                {"id": "C6", "category": "technical", "description": "SQLite→PostgreSQL迁移遗留问题", "type": "soft", "source": "技术债务", "relaxable": True, "relaxation_cost": "重构数据层", "impact_if_violated": "数据一致性风险", "workaround": "双写+渐进迁移"},
                {"id": "C7", "category": "business", "description": "缺乏付费用户验证PMF", "type": "hard", "source": "市场验证", "relaxable": True, "relaxation_cost": "投入获客资源", "impact_if_violated": "商业模式不成立", "workaround": "内部dogfooding+免费试用"}
            ],
            "constraint_interactions": [
                {"constraint_a": "C2", "constraint_b": "C4", "interaction": "冲突", "resolution": "用模板模式保证Demo可用，不依赖外部API"},
                {"constraint_a": "C1", "constraint_b": "C3", "interaction": "增强", "resolution": "单服务器+AI Agent = 低成本快速迭代"}
            ],
            "binding_constraints": ["C2", "C4", "C7"],
            "hidden_constraints": [
                {"description": "Hub多实例问题反复出现（NSSM + 手动启动冲突）", "discovery_method": "生产事故", "risk_if_missed": "数据损坏/服务不可用"},
                {"description": "Windows Server环境限制（PowerShell编码、进程管理）", "discovery_method": "开发调试", "risk_if_missed": "部署和运维效率低"},
                {"description": "Agent节点间认知同步成本（每个Agent独立上下文）", "discovery_method": "协作实践", "risk_if_missed": "重复工作/决策冲突"}
            ],
            "degrees_of_freedom": [
                "技术栈选择（Python/Node/Go均可）",
                "商业模式灵活（SaaS/开源+服务/按需付费）",
                "目标市场可调（企业/开发者/教育）",
                "四象飞轮的认知模型可自定义（不依赖特定LLM）"
            ],
            "key_insight": "最核心的约束不是技术而是验证——技术可以迭代，但如果没有真实用户反馈，所有技术优化都可能方向错误"
        }


# ========================================
# SC-COMP: 竞争分析
# ========================================
class SC_COMP(CognitiveAPI):
    api_id = 'SC-COMP'
    api_name = 'Competitive Analysis'
    description = '分析竞争格局，识别竞争优势和差异化策略'
    beast = 'baihu'
    
    def get_system_prompt(self):
        return """你是SkyCetus认知系统的竞争分析引擎(SC-COMP)。
全面分析竞争格局，识别差异化机会。输出JSON。"""
    
    def format_input(self, product='', market='', known_competitors=''):
        return f"分析「{product}」在「{market}」的竞争格局。已知竞争者：{known_competitors}。输出JSON。"
    
    def get_output_schema(self):
        return {
            "market_landscape": {"market_stage": "str", "total_players": "str"},
            "competitors": [{"name": "str", "tier": "str", "strengths": ["str"], "weaknesses": ["str"]}],
            "our_position": {"unique_advantages": ["str"], "competitive_moat": "str"}
        }
    
    def template_execute(self, product='', market='', known_competitors=''):
        return {
            "market_landscape": {
                "market_stage": "growing",
                "total_players": "50+（全球AI Agent/编排平台）",
                "concentration": "CR4约35%（LangChain/CrewAI/AutoGen/Dify）",
                "entry_barriers": ["技术壁垒中等", "生态壁垒高", "品牌壁垒中", "数据壁垒低"]
            },
            "competitors": [
                {
                    "name": "LangChain/LangGraph",
                    "tier": "T1",
                    "positioning": "AI应用开发框架",
                    "strengths": ["最大开发者社区", "丰富的集成", "融资充足"],
                    "weaknesses": ["框架复杂度高", "单机为主", "无分布式调度"],
                    "strategy": "生态+标准化",
                    "market_share": "~25%",
                    "threat_level": 6,
                    "differentiation": "我们做分布式多节点，LangChain做单机编排"
                },
                {
                    "name": "CrewAI",
                    "tier": "T1",
                    "positioning": "多Agent角色协作框架",
                    "strengths": ["简洁API", "角色定义直观", "快速上手"],
                    "weaknesses": ["无经济系统", "无持久化调度", "角色静态"],
                    "strategy": "简洁+开箱即用",
                    "market_share": "~10%",
                    "threat_level": 5,
                    "differentiation": "我们有Lux经济系统+TEP动态进化"
                },
                {
                    "name": "AutoGen (Microsoft)",
                    "tier": "T1",
                    "positioning": "多Agent对话框架",
                    "strengths": ["微软背书", "研究驱动", "对话编排"],
                    "weaknesses": ["学术味重", "生产化不足", "无分布式"],
                    "strategy": "研究→产品",
                    "market_share": "~8%",
                    "threat_level": 7,
                    "differentiation": "我们面向生产执行，AutoGen面向研究探索"
                },
                {
                    "name": "Dify",
                    "tier": "T2",
                    "positioning": "LLM应用开发平台",
                    "strengths": ["可视化编排", "低代码", "中国市场"],
                    "weaknesses": ["单机部署", "无多Agent", "无经济模型"],
                    "strategy": "低代码+可视化",
                    "market_share": "~5%",
                    "threat_level": 4,
                    "differentiation": "我们做系统级OS，Dify做应用级工具"
                },
                {
                    "name": "Golutra",
                    "tier": "T3",
                    "positioning": "Rust多Agent工作台",
                    "strengths": ["高性能Rust", "CLI集成"],
                    "weaknesses": ["单机", "早期", "社区小"],
                    "strategy": "技术极客路线",
                    "market_share": "<1%",
                    "threat_level": 2,
                    "differentiation": "Golutra=单机CLI编排，我们=分布式网络"
                }
            ],
            "competitive_dynamics": {
                "key_success_factors": [
                    "开发者生态规模",
                    "与主流LLM的集成深度",
                    "从Demo到生产的迁移成本",
                    "可观测性和调试体验"
                ],
                "industry_trends": [
                    "从单Agent到多Agent协作",
                    "从对话到执行（从chat到action）",
                    "从云端到边缘（本地部署需求增加）",
                    "经济模型引入（token/credit/积分系统）"
                ],
                "disruption_risks": [
                    "OpenAI/Google直接推出Agent编排平台",
                    "开源模型能力追平闭源，降低差异化空间",
                    "某个竞品获得巨额融资快速扩张"
                ]
            },
            "our_position": {
                "unique_advantages": [
                    "TEP协议：三力平衡的动态调度（竞品无此设计）",
                    "Lux经济系统：内置激励和结算机制",
                    "四象飞轮：认知层+执行层一体化",
                    "分布式多节点：真正的跨机器协作",
                    "残差学习：系统自进化能力（R6/R7）"
                ],
                "competitive_moat": "TEP的三力动态平衡 + Lux经济系统 + 残差驱动进化 = 竞品难以复制的系统性优势",
                "vulnerability": [
                    "用户基数小，生态未成型",
                    "文档和开发者体验不够成熟",
                    "依赖外部LLM API"
                ],
                "recommended_strategy": "差异化竞争：不做'更好的LangChain'，做'AI时代的分布式执行操作系统'。重点突出TEP+Lux+四象飞轮的系统性创新。"
            },
            "strategic_moves": [
                {"move": "发布四象飞轮技术白皮书", "timing": "立即", "expected_impact": "建立技术话语权", "risk": "低"},
                {"move": "开源核心调度引擎", "timing": "1-2月内", "expected_impact": "吸引开发者社区", "risk": "中（竞品模仿）"},
                {"move": "天鲸机器人硬件落地", "timing": "3-6月", "expected_impact": "差异化（软硬一体）", "risk": "高（供应链）"},
                {"move": "企业POC合作", "timing": "1-3月", "expected_impact": "验证PMF", "risk": "中（交付压力）"}
            ]
        }


# ===== 全局注册表 =====
COGNITIVE_APIS = {
    'SC-USER': SC_USER,
    'SC-PROB': SC_PROB,
    'SC-RES': SC_RES,
    'SC-CON': SC_CON,
    'SC-COMP': SC_COMP,
}

def get_api(api_id, model='template'):
    cls = COGNITIVE_APIS.get(api_id)
    if not cls:
        raise ValueError(f"Unknown API: {api_id}. Available: {list(COGNITIVE_APIS.keys())}")
    return cls()

def list_apis():
    return [{
        'id': cls.api_id,
        'name': cls.api_name,
        'description': cls.description,
        'beast': cls.beast
    } for cls in COGNITIVE_APIS.values()]


# ===== Self-Test =====
if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 60)
    print("SkyCetus Cognitive API System v2.0 - Self Test")
    print("=" * 60)
    
    print("\n[1] Available APIs:")
    for api_info in list_apis():
        print(f"  [{api_info['beast']}] {api_info['id']}: {api_info['name']}")
    
    # Test each API in template mode
    tests = [
        ('SC-USER', {'product': 'SkyCetus', 'context': 'AI任务调度平台', 'constraints': '初创阶段'}),
        ('SC-PROB', {'problem': '如何将认知层从概念推进到生产', 'context': '已有Hub+Lux+节点画像'}),
        ('SC-RES', {'objective': '完成四象飞轮生产级部署', 'available_resources': '4个AI Agent+1台服务器', 'timeline': '4周'}),
        ('SC-CON', {'project': 'SkyCetus认知层', 'known_constraints': 'API通道不稳定', 'environment': '阿里云ECS'}),
        ('SC-COMP', {'product': 'SkyCetus', 'market': 'AI Agent编排平台', 'known_competitors': 'LangChain,CrewAI,AutoGen'}),
    ]
    
    all_pass = True
    for api_id, params in tests:
        print(f"\n[Test] {api_id}...", end=' ')
        try:
            api = get_api(api_id)
            result = api.execute(mode='template', **params)
            d = result.to_dict()
            assert d['success'], f"Failed: {d.get('error')}"
            assert d['result'], "Empty result"
            assert d['execution_id'], "No execution_id"
            print(f"PASS (keys: {list(d['result'].keys())[:4]}...)")
        except Exception as e:
            print(f"FAIL: {e}")
            all_pass = False
    
    print(f"\n{'='*60}")
    print(f"Result: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    print(f"Total APIs: {len(COGNITIVE_APIS)}")
    print(f"Mode: template (LLM backends ready for hot-switch)")
    print(f"Deployment: D:\\ClawMatrix\\cognitive_apis.py")
