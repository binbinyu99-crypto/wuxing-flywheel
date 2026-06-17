"""Adversarial Enforcer — 白虎审计强制化 V2 (校准版)
白虎（金/弗洛伊德精神分析）的对抗验证是pipeline的强制环节，不是可选步骤。

V2 核心理念变更：
- 高质量对抗攻击是认知价值，不是惩罚
- 只惩罚结构性失败（没审计、橡皮图章）
- 未解决的严重攻击 = 轻微扣分（上限封顶），不是毁灭性打击
- 总扣分上限 -0.15
"""

from typing import Dict, List, Any, Optional, Tuple
import json


class AuditResult:
    """白虎审计结果"""

    def __init__(self):
        self.attacks: List[Dict] = []
        self.residuals: List[Dict] = []
        self.passed: bool = False
        self.score_adjustment: float = 0.0
        self.blocking_issues: List[str] = []

    @property
    def max_severity(self) -> float:
        severities = []
        for atk in self.attacks:
            try:
                severities.append(float(atk.get('severity', 0)))
            except (ValueError, TypeError):
                pass
        return max(severities) if severities else 0.0

    @property
    def unresolved_count(self) -> int:
        return sum(1 for a in self.attacks if isinstance(a, dict) and a.get('unresolved', False))

    @property
    def is_rubber_stamp(self) -> bool:
        """检测橡皮图章审计：所有攻击严重度都很低"""
        if not self.attacks:
            return True
        return self.max_severity < 0.2 and len(self.attacks) >= 3


class AdversarialEnforcer:
    """强制对抗验证器 V2

    在飞轮pipeline中的位置：
    青龙(种子) → 朱雀(深度分析) → 谛听(交叉验证) → [白虎审计] → 玄武(收敛)

    白虎审计是gate，不通过则：
    1. 降低最终评分（上限封顶）
    2. 在报告中标注"未经充分对抗验证"
    3. 严重情况下阻止自动发布
    """

    # V2 评分调整规则 — 对抗攻击是认知价值，不是惩罚
    SCORE_PENALTIES = {
        'no_audit': -0.10,           # 完全没有审计 — 结构缺失
        'rubber_stamp': -0.08,       # 橡皮图章审计 — 白虎没有真正挑战
        'high_unresolved': -0.03,    # >50%攻击未解决 — 轻微扣分
        'critical_unresolved': -0.05, # 严重度>0.9的攻击未解决 — 最多扣一次
    }

    # V2: 总扣分上限 — 防止对抗扣分碾压内容评分
    MAX_TOTAL_DEDUCTION = -0.15

    # 阻止自动发布的条件 — 提高阈值，只有极端情况才阻止
    BLOCK_PUBLISH_THRESHOLD = 0.90

    def __init__(self, strict: bool = True):
        self.strict = strict

    def enforce(self, baihu_output: Any, current_score: float = 0.0) -> AuditResult:
        """执行强制审计检查

        Args:
            baihu_output: 白虎Agent的原始输出（str或dict）
            current_score: 当前飞轮评分

        Returns:
            AuditResult with pass/fail status and score adjustments
        """
        result = AuditResult()

        # Parse baihu output
        if isinstance(baihu_output, str):
            parsed = self._safe_parse(baihu_output)
        elif isinstance(baihu_output, dict):
            parsed = baihu_output
        else:
            parsed = None

        # === Check 1: Did audit happen? ===
        if not parsed:
            result.passed = False
            result.score_adjustment = self.SCORE_PENALTIES['no_audit']
            result.blocking_issues.append("白虎审计未执行或输出无法解析")
            return result

        # Extract attacks and residuals
        result.attacks = parsed.get('attacks', [])
        result.residuals = parsed.get('residuals', [])

        if not result.attacks:
            result.passed = False
            result.score_adjustment = self.SCORE_PENALTIES['no_audit']
            result.blocking_issues.append("白虎未生成任何攻击 — 审计无效")
            return result

        # === Check 2: Is it a rubber stamp? ===
        if result.is_rubber_stamp:
            result.score_adjustment += self.SCORE_PENALTIES['rubber_stamp']
            result.blocking_issues.append("所有攻击严重度<0.2 — 疑似橡皮图章审计")

        # === Check 3: Unresolved attacks ===
        total_attacks = len(result.attacks)
        unresolved = result.unresolved_count

        if total_attacks > 0 and unresolved / total_attacks > 0.5:
            result.score_adjustment += self.SCORE_PENALTIES['high_unresolved']

        # === Check 4: Critical unresolved attacks (V2: cap at ONE penalty) ===
        _critical_found = False
        for atk in result.attacks:
            if not isinstance(atk, dict):
                continue
            try:
                severity = float(atk.get('severity', 0))
            except (ValueError, TypeError):
                severity = 0

            if severity >= self.BLOCK_PUBLISH_THRESHOLD and atk.get('unresolved', False):
                if not _critical_found:
                    result.score_adjustment += self.SCORE_PENALTIES['critical_unresolved']
                    _critical_found = True
                result.blocking_issues.append(
                    f"严重攻击未解决 (severity={severity:.2f}): {str(atk.get('attack', ''))[:100]}"
                )

        # V2: Enforce total deduction cap
        if result.score_adjustment < self.MAX_TOTAL_DEDUCTION:
            result.score_adjustment = self.MAX_TOTAL_DEDUCTION

        # === Final verdict ===
        # Audit passes if there are real attacks (not rubber stamp)
        # V2: Unresolved critical attacks no longer block — they're noted but not fatal
        result.passed = not result.is_rubber_stamp

        return result

    def adjust_score(self, original_score: float, audit_result: AuditResult) -> Tuple[float, str]:
        """根据审计结果调整评分

        Returns:
            (adjusted_score, explanation)
        """
        adjusted = original_score + audit_result.score_adjustment
        adjusted = max(0.0, min(1.0, adjusted))  # Clamp to [0, 1]

        if audit_result.score_adjustment == 0:
            return adjusted, "审计通过，评分不变"

        parts = []
        if audit_result.score_adjustment < 0:
            parts.append(f"审计扣分 {audit_result.score_adjustment:+.2f}")
        if audit_result.blocking_issues:
            parts.append(f"问题: {'; '.join(audit_result.blocking_issues[:3])}")

        explanation = ' | '.join(parts)
        return adjusted, explanation

    def should_block_publish(self, audit_result: AuditResult) -> bool:
        """判断是否应该阻止自动发布
        V2: 只在完全没有审计或橡皮图章时阻止
        """
        if not audit_result.passed and self.strict:
            return True
        return False  # V2: 不再因为未解决攻击数量阻止

    def _safe_parse(self, text: str) -> Optional[dict]:
        if not text:
            return None
        text = text.strip()
        if not text.startswith('{'):
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


def _safe_float(val) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0
