"""NPT Validator — 认知不扩散协议的代码化实现
将哲学公理转化为Pydantic模型校验，每个Agent输出必须通过校验才能进入下一环节。

公理零：能力增长永不受限，只治理使用方式
公理一：认知产出必须可追溯
公理二：对抗验证不可跳过
公理三：残差必须被记录
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import json
import re


class NPTViolation(Exception):
    """NPT协议违规异常"""
    def __init__(self, axiom: str, agent: str, detail: str):
        self.axiom = axiom
        self.agent = agent
        self.detail = detail
        super().__init__(f"NPT Violation [{axiom}] by {agent}: {detail}")


class EvidenceGrade(Enum):
    A = "A"      # 多源验证，高置信
    B = "B"      # 单源验证，中置信
    C = "C"      # 推测，低置信
    D = "D"      # 无证据
    UNGRADED = "?"


@dataclass
class TraceableOutput:
    """公理一：认知产出必须可追溯"""
    agent_id: str
    round_num: int
    content: Any
    sources: List[str] = field(default_factory=list)
    evidence_grade: str = "?"
    confidence: float = 0.0
    assumptions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    timestamp: str = ""

    def validate_traceability(self) -> bool:
        """校验输出是否满足可追溯性要求"""
        if not self.agent_id:
            raise NPTViolation("AXIOM_1", "unknown", "Agent ID is required")
        if self.content is None or (isinstance(self.content, str) and len(self.content.strip()) == 0):
            raise NPTViolation("AXIOM_1", self.agent_id, "Empty output is not traceable")
        return True


@dataclass
class AdversarialResult:
    """公理二：对抗验证结果"""
    attacks: List[Dict] = field(default_factory=list)
    residuals: List[Dict] = field(default_factory=list)
    audit_passed: bool = False
    severity_max: float = 0.0
    unresolved_count: int = 0

    def validate_adversarial(self) -> bool:
        """校验对抗验证是否真正执行"""
        if not self.attacks:
            raise NPTViolation("AXIOM_2", "baihu", "No attacks generated — adversarial audit was skipped or empty")
        if self.severity_max == 0 and len(self.attacks) > 0:
            raise NPTViolation("AXIOM_2", "baihu", "All attacks have zero severity — audit may be rubber-stamping")
        return True


@dataclass 
class ResidualRecord:
    """公理三：残差记录"""
    description: str
    residual_type: str  # knowledge_gap, assumption_untested, data_missing, logic_uncertain
    severity: float = 0.5
    source_agent: str = ""
    
    
class NPTValidator:
    """NPT协议校验器 — 所有飞轮输出的守门员
    
    Usage:
        validator = NPTValidator()
        
        # 校验单个Agent输出
        validator.validate_output(traceable_output)
        
        # 校验完整run结果
        validator.validate_run(result_dict)
    """
    
    def __init__(self, strict: bool = True):
        self.strict = strict  # strict=True 抛异常, False 只记录
        self.violations: List[NPTViolation] = []
        self.residuals_collected: List[ResidualRecord] = []
    
    def validate_output(self, output: TraceableOutput) -> bool:
        """校验单个Agent的输出"""
        try:
            output.validate_traceability()
            return True
        except NPTViolation as e:
            self.violations.append(e)
            if self.strict:
                raise
            return False
    
    def validate_adversarial(self, result: AdversarialResult) -> bool:
        """校验对抗验证是否真正执行"""
        try:
            result.validate_adversarial()
            return True
        except NPTViolation as e:
            self.violations.append(e)
            if self.strict:
                raise
            return False
    
    def collect_residual(self, residual: ResidualRecord):
        """公理三：收集残差"""
        self.residuals_collected.append(residual)
    
    def validate_run(self, result: dict) -> Dict[str, Any]:
        """校验完整的飞轮run结果
        
        Returns:
            {
                "valid": bool,
                "violations": list,
                "residuals_collected": int,
                "adversarial_verified": bool,
                "traceability_score": float
            }
        """
        violations = []
        
        # === AXIOM 1: 可追溯性 ===
        element_outputs = result.get('element_outputs', {})
        agents_with_output = 0
        agents_total = 0
        
        for agent_name in ['qinglong', 'zhuque', 'diting', 'baihu', 'xuanwu']:
            agents_total += 1
            output = element_outputs.get(agent_name, '')
            if output and len(str(output).strip()) > 10:
                agents_with_output += 1
            else:
                violations.append({
                    'axiom': 'AXIOM_1',
                    'agent': agent_name,
                    'detail': f'{agent_name} output is empty or trivial'
                })
        
        traceability_score = agents_with_output / max(agents_total, 1)
        
        # === AXIOM 2: 对抗验证不可跳过 ===
        adversarial_verified = False
        baihu_raw = element_outputs.get('baihu', '')
        if baihu_raw:
            baihu_data = _safe_parse(baihu_raw)
            if baihu_data and isinstance(baihu_data, dict):
                attacks = baihu_data.get('attacks', [])
                if attacks and len(attacks) > 0:
                    adversarial_verified = True
                    # Check for rubber-stamping
                    severities = []
                    for atk in attacks:
                        if isinstance(atk, dict):
                            try:
                                severities.append(float(atk.get('severity', 0)))
                            except (ValueError, TypeError):
                                pass
                    if severities and max(severities) == 0:
                        violations.append({
                            'axiom': 'AXIOM_2',
                            'agent': 'baihu',
                            'detail': 'All attacks have zero severity — possible rubber-stamping'
                        })
        
        if not adversarial_verified:
            violations.append({
                'axiom': 'AXIOM_2',
                'agent': 'baihu',
                'detail': 'Adversarial audit was not performed or produced no attacks'
            })
        
        # === AXIOM 3: 残差记录 ===
        kunpeng = result.get('kunpeng', {})
        if isinstance(kunpeng, str):
            kunpeng = _safe_parse(kunpeng) or {}
        
        data_gaps = kunpeng.get('data_gaps', [])
        residuals_count = len(data_gaps) if isinstance(data_gaps, list) else 0
        
        # Also check baihu residuals
        if baihu_raw:
            baihu_data = _safe_parse(baihu_raw) if isinstance(baihu_raw, str) else baihu_raw
            if isinstance(baihu_data, dict):
                baihu_residuals = baihu_data.get('residuals', [])
                residuals_count += len(baihu_residuals) if isinstance(baihu_residuals, list) else 0
        
        if residuals_count == 0:
            violations.append({
                'axiom': 'AXIOM_3',
                'agent': 'system',
                'detail': 'No residuals or data gaps recorded — every analysis has unknowns'
            })
        
        # === Overall verdict ===
        valid = len(violations) == 0
        
        return {
            'valid': valid,
            'violations': violations,
            'violation_count': len(violations),
            'residuals_collected': residuals_count,
            'adversarial_verified': adversarial_verified,
            'traceability_score': traceability_score,
            'agents_reporting': f'{agents_with_output}/{agents_total}'
        }


def _safe_parse(text):
    """Safely parse JSON from text"""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    if not text.startswith('{') and not text.startswith('['):
        # Try to find JSON in text
        idx = text.find('{')
        if idx >= 0:
            text = text[idx:]
        else:
            return None
    try:
        return json.loads(text)
    except:
        try:
            return json.loads(text, strict=False)
        except:
            return None
