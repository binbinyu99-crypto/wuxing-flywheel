#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
白虎红蓝对抗训练系统 v1.0
Baihu Red Team vs Blue Team Training System

功能：
1. 红队攻击模拟 - 模拟各种攻击场景
2. 蓝队防御响应 - 自动防御和响应
3. 对抗评估 - 评估攻防效果
4. 能力提升 - 通过对抗训练提升系统鲁棒性
"""
import sys
import json
import random
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

sys.stdout.reconfigure(encoding='utf-8')

class AttackType(Enum):
    """攻击类型"""
    NODE_DOS = "节点拒绝服务"
    AUTH_BYPASS = "认证绕过"
    PRIVILEGE_ESCALATION = "权限提升"
    DATA_EXFILTRATION = "数据渗出"
    TASK_MANIPULATION = "任务篡改"
    LUX_THEFT = "LUX窃取"
    NODE_SPOOFING = "节点伪装"
    MESSAGE_HIJACK = "消息劫持"

class DefenseType(Enum):
    """防御类型"""
    RATE_LIMITING = "速率限制"
    BEHAVIOR_ANALYSIS = "行为分析"
    ANOMALY_DETECTION = "异常检测"
    ACCESS_CONTROL = "访问控制"
    ENCRYPTION = "加密保护"
    AUDIT_LOGGING = "审计日志"
    ISOLATION = "隔离机制"
    AUTO_RESPONSE = "自动响应"

@dataclass
class AttackScenario:
    """攻击场景"""
    attack_id: str
    attack_type: AttackType
    target: str
    intensity: float  # 0.0 - 1.0
    duration: int  # 秒
    payload: Dict
    timestamp: str
    
@dataclass
class DefenseAction:
    """防御动作"""
    defense_id: str
    defense_type: DefenseType
    target: str
    effectiveness: float  # 0.0 - 1.0
    response_time: int  # 毫秒
    timestamp: str

@dataclass
class BattleResult:
    """对抗结果"""
    battle_id: str
    scenario: AttackScenario
    defenses: List[DefenseAction]
    red_score: float
    blue_score: float
    winner: str
    lessons_learned: List[str]
    timestamp: str


class RedTeam:
    """
    红队 - 攻击模拟
    """
    
    def __init__(self):
        self.attack_scenarios = self._load_attack_scenarios()
        self.attack_history = []
        
    def _load_attack_scenarios(self) -> Dict:
        """加载攻击场景库"""
        return {
            AttackType.NODE_DOS: {
                'description': '模拟节点拒绝服务攻击',
                'indicators': ['high_cpu', 'memory_spike', 'response_timeout'],
                'stealth': 0.3,
                'impact': 0.8
            },
            AttackType.AUTH_BYPASS: {
                'description': '模拟认证绕过攻击',
                'indicators': ['auth_failure', 'token_reuse', 'session_hijack'],
                'stealth': 0.8,
                'impact': 0.9
            },
            AttackType.PRIVILEGE_ESCALATION: {
                'description': '模拟权限提升攻击',
                'indicators': ['privilege_change', 'unauthorized_access'],
                'stealth': 0.7,
                'impact': 0.95
            },
            AttackType.DATA_EXFILTRATION: {
                'description': '模拟数据渗出攻击',
                'indicators': ['large_transfer', 'unusual_access_pattern'],
                'stealth': 0.6,
                'impact': 0.85
            },
            AttackType.TASK_MANIPULATION: {
                'description': '模拟任务篡改攻击',
                'indicators': ['task_modify', 'lux_change', 'status_change'],
                'stealth': 0.5,
                'impact': 0.75
            },
            AttackType.LUX_THEFT: {
                'description': '模拟LUX窃取攻击',
                'indicators': ['lux_transfer', 'balance_anomaly'],
                'stealth': 0.4,
                'impact': 0.7
            },
            AttackType.NODE_SPOOFING: {
                'description': '模拟节点伪装攻击',
                'indicators': ['identity_mismatch', 'certificate_anomaly'],
                'stealth': 0.9,
                'impact': 0.8
            },
            AttackType.MESSAGE_HIJACK: {
                'description': '模拟消息劫持攻击',
                'indicators': ['message_delay', 'content_modification'],
                'stealth': 0.75,
                'impact': 0.85
            }
        }
    
    def generate_attack(self, target_node: str = None, 
                       attack_type: AttackType = None) -> AttackScenario:
        """生成攻击场景"""
        if attack_type is None:
            attack_type = random.choice(list(AttackType))
        
        scenario_config = self.attack_scenarios[attack_type]
        
        attack = AttackScenario(
            attack_id=f"ATK-{hashlib.md5(f'{attack_type}{datetime.now()}'.encode()).hexdigest()[:8]}",
            attack_type=attack_type,
            target=target_node or f"node-{random.randint(1, 100)}",
            intensity=random.uniform(0.5, 1.0),
            duration=random.randint(30, 300),
            payload={
                'stealth': scenario_config['stealth'],
                'impact': scenario_config['impact'],
                'indicators': scenario_config['indicators']
            },
            timestamp=datetime.now().isoformat()
        )
        
        self.attack_history.append(attack)
        return attack
    
    def execute_attack(self, attack: AttackScenario) -> Dict:
        """执行攻击"""
        # 模拟攻击执行
        success_rate = attack.intensity * attack.payload['stealth']
        
        return {
            'attack_id': attack.attack_id,
            'attack_type': attack.attack_type.value,
            'target': attack.target,
            'success_rate': success_rate,
            'indicators_triggered': random.sample(
                attack.payload['indicators'],
                k=random.randint(1, len(attack.payload['indicators']))
            ),
            'stealth_score': attack.payload['stealth'],
            'impact_score': attack.payload['impact']
        }


class BlueTeam:
    """
    蓝队 - 防御响应
    """
    
    def __init__(self):
        self.defense_strategies = self._load_defense_strategies()
        self.defense_history = []
        self.detection_rules = self._load_detection_rules()
        
    def _load_defense_strategies(self) -> Dict:
        """加载防御策略"""
        return {
            DefenseType.RATE_LIMITING: {
                'description': '限制请求速率',
                'effectiveness': {'NODE_DOS': 0.9, 'AUTH_BYPASS': 0.3},
                'response_time': 50
            },
            DefenseType.BEHAVIOR_ANALYSIS: {
                'description': '分析用户行为',
                'effectiveness': {'AUTH_BYPASS': 0.8, 'PRIVILEGE_ESCALATION': 0.85},
                'response_time': 200
            },
            DefenseType.ANOMALY_DETECTION: {
                'description': '检测异常行为',
                'effectiveness': {'NODE_DOS': 0.7, 'DATA_EXFILTRATION': 0.75, 'LUX_THEFT': 0.8},
                'response_time': 150
            },
            DefenseType.ACCESS_CONTROL: {
                'description': '访问控制',
                'effectiveness': {'PRIVILEGE_ESCALATION': 0.9, 'DATA_EXFILTRATION': 0.7},
                'response_time': 30
            },
            DefenseType.ENCRYPTION: {
                'description': '加密保护',
                'effectiveness': {'DATA_EXFILTRATION': 0.6, 'MESSAGE_HIJACK': 0.85},
                'response_time': 20
            },
            DefenseType.AUDIT_LOGGING: {
                'description': '审计日志',
                'effectiveness': {'TASK_MANIPULATION': 0.8, 'LUX_THEFT': 0.75},
                'response_time': 10
            },
            DefenseType.ISOLATION: {
                'description': '隔离机制',
                'effectiveness': {'NODE_DOS': 0.85, 'NODE_SPOOFING': 0.8},
                'response_time': 100
            },
            DefenseType.AUTO_RESPONSE: {
                'description': '自动响应',
                'effectiveness': {'ALL': 0.6},
                'response_time': 500
            }
        }
    
    def _load_detection_rules(self) -> List[Dict]:
        """加载检测规则"""
        return [
            {
                'rule_id': 'DET-001',
                'name': '高频率认证失败',
                'pattern': 'auth_failure_count > 5 in 1m',
                'severity': 'high',
                'attack_types': [AttackType.AUTH_BYPASS]
            },
            {
                'rule_id': 'DET-002',
                'name': '异常LUX转移',
                'pattern': 'lux_transfer_amount > threshold',
                'severity': 'critical',
                'attack_types': [AttackType.LUX_THEFT, AttackType.TASK_MANIPULATION]
            },
            {
                'rule_id': 'DET-003',
                'name': '节点性能下降',
                'pattern': 'cpu_usage > 90% or memory_usage > 95%',
                'severity': 'medium',
                'attack_types': [AttackType.NODE_DOS]
            },
            {
                'rule_id': 'DET-004',
                'name': '未授权访问',
                'pattern': 'access_denied_count > 3',
                'severity': 'high',
                'attack_types': [AttackType.PRIVILEGE_ESCALATION]
            },
            {
                'rule_id': 'DET-005',
                'name': '大数据传输',
                'pattern': 'data_transfer > 100MB in 1m',
                'severity': 'medium',
                'attack_types': [AttackType.DATA_EXFILTRATION]
            }
        ]
    
    def detect_attack(self, attack: AttackScenario) -> Tuple[bool, List[Dict]]:
        """检测攻击"""
        triggered_rules = []
        detection_score = 0.0
        
        for rule in self.detection_rules:
            if attack.attack_type in rule['attack_types']:
                # 模拟检测成功率
                detection_probability = 0.7 + (attack.intensity * 0.2) - (attack.payload['stealth'] * 0.3)
                if random.random() < detection_probability:
                    triggered_rules.append(rule)
                    detection_score += 0.2
        
        detected = len(triggered_rules) > 0
        return detected, triggered_rules
    
    def generate_defense(self, attack: AttackScenario, 
                        triggered_rules: List[Dict]) -> List[DefenseAction]:
        """生成防御动作"""
        defenses = []
        attack_type_name = attack.attack_type.name
        
        for defense_type, config in self.defense_strategies.items():
            effectiveness = config['effectiveness'].get(attack_type_name, 
                                                       config['effectiveness'].get('ALL', 0.3))
            
            if effectiveness > 0.5:  # 只使用有效的防御
                defense = DefenseAction(
                    defense_id=f"DEF-{hashlib.md5(f'{defense_type}{datetime.now()}'.encode()).hexdigest()[:8]}",
                    defense_type=defense_type,
                    target=attack.target,
                    effectiveness=effectiveness * random.uniform(0.8, 1.0),
                    response_time=config['response_time'] + random.randint(-20, 50),
                    timestamp=datetime.now().isoformat()
                )
                defenses.append(defense)
                self.defense_history.append(defense)
        
        return defenses
    
    def execute_defense(self, defenses: List[DefenseAction], 
                       attack: AttackScenario) -> Dict:
        """执行防御"""
        total_effectiveness = sum(d.effectiveness for d in defenses) / max(len(defenses), 1)
        avg_response_time = sum(d.response_time for d in defenses) / max(len(defenses), 1)
        
        # 计算防御成功率
        defense_success = total_effectiveness * (1 - attack.payload['stealth'] * 0.5)
        
        return {
            'defense_count': len(defenses),
            'total_effectiveness': total_effectiveness,
            'avg_response_time': avg_response_time,
            'defense_success': defense_success,
            'attack_mitigated': defense_success > 0.6,
            'actions': [d.defense_type.value for d in defenses]
        }


class RedBlueBattle:
    """
    红蓝对抗训练
    """
    
    def __init__(self):
        self.red_team = RedTeam()
        self.blue_team = BlueTeam()
        self.battle_history = []
        self.training_stats = {
            'total_battles': 0,
            'red_wins': 0,
            'blue_wins': 0,
            'draws': 0
        }
    
    def run_battle(self, target_node: str = None, 
                   attack_type: AttackType = None) -> BattleResult:
        """运行一次对抗"""
        print(f"\n{'='*60}")
        print("🔴 红蓝对抗训练开始 🔵")
        print(f"{'='*60}")
        
        # 红队生成攻击
        print("\n🔴 红队生成攻击场景...")
        attack = self.red_team.generate_attack(target_node, attack_type)
        print(f"   攻击ID: {attack.attack_id}")
        print(f"   攻击类型: {attack.attack_type.value}")
        print(f"   目标: {attack.target}")
        print(f"   强度: {attack.intensity:.2f}")
        print(f"   隐蔽性: {attack.payload['stealth']:.2f}")
        print(f"   影响: {attack.payload['impact']:.2f}")
        
        # 执行攻击
        attack_result = self.red_team.execute_attack(attack)
        
        # 蓝队检测
        print("\n🔵 蓝队检测攻击...")
        detected, triggered_rules = self.blue_team.detect_attack(attack)
        
        if detected:
            print(f"   ✅ 检测到攻击! 触发 {len(triggered_rules)} 条规则")
            for rule in triggered_rules:
                print(f"      - {rule['name']} ({rule['severity']})")
        else:
            print("   ❌ 未检测到攻击 (隐蔽成功)")
        
        # 蓝队生成防御
        defenses = []
        if detected:
            defenses = self.blue_team.generate_defense(attack, triggered_rules)
            print(f"\n🔵 蓝队启动 {len(defenses)} 项防御措施:")
            for defense in defenses:
                print(f"   - {defense.defense_type.value} (效果: {defense.effectiveness:.2f})")
        
        # 执行防御
        defense_result = self.blue_team.execute_defense(defenses, attack)
        
        # 计算得分
        red_score = attack_result['success_rate'] * attack.payload['impact']
        blue_score = defense_result['defense_success'] if detected else 0.0
        
        # 判定胜负
        if red_score > blue_score + 0.2:
            winner = "red"
            self.training_stats['red_wins'] += 1
        elif blue_score > red_score + 0.2:
            winner = "blue"
            self.training_stats['blue_wins'] += 1
        else:
            winner = "draw"
            self.training_stats['draws'] += 1
        
        # 生成经验教训
        lessons_learned = self._generate_lessons(attack, detected, defense_result, winner)
        
        # 创建战斗结果
        result = BattleResult(
            battle_id=f"BAT-{hashlib.md5(f'{attack.attack_id}{datetime.now()}'.encode()).hexdigest()[:8]}",
            scenario=attack,
            defenses=defenses,
            red_score=red_score,
            blue_score=blue_score,
            winner=winner,
            lessons_learned=lessons_learned,
            timestamp=datetime.now().isoformat()
        )
        
        self.battle_history.append(result)
        self.training_stats['total_battles'] += 1
        
        # 输出结果
        print(f"\n{'='*60}")
        print("📊 对抗结果")
        print(f"{'='*60}")
        print(f"   红队得分: {red_score:.2f}")
        print(f"   蓝队得分: {blue_score:.2f}")
        print(f"   获胜方: {'🔴 红队' if winner == 'red' else '🔵 蓝队' if winner == 'blue' else '🤝 平局'}")
        print(f"\n📚 经验教训:")
        for lesson in lessons_learned:
            print(f"   • {lesson}")
        
        return result
    
    def _generate_lessons(self, attack: AttackScenario, detected: bool,
                         defense_result: Dict, winner: str) -> List[str]:
        """生成经验教训"""
        lessons = []
        
        if winner == "red":
            if not detected:
                lessons.append(f"攻击隐蔽性过高({attack.payload['stealth']:.2f})，需要增强检测能力")
            else:
                lessons.append(f"防御效果不足({defense_result['total_effectiveness']:.2f})，需要优化响应策略")
        elif winner == "blue":
            lessons.append(f"成功检测并防御{attack.attack_type.value}攻击")
            if defense_result['avg_response_time'] > 200:
                lessons.append(f"响应时间较长({defense_result['avg_response_time']:.0f}ms)，可优化响应速度")
        else:
            lessons.append("攻防势均力敌，双方策略都需要优化")
        
        # 根据攻击类型给出建议
        if attack.attack_type == AttackType.AUTH_BYPASS:
            lessons.append("建议加强多因素认证和行为分析")
        elif attack.attack_type == AttackType.NODE_DOS:
            lessons.append("建议优化资源监控和自动扩容机制")
        elif attack.attack_type == AttackType.LUX_THEFT:
            lessons.append("建议加强交易审计和异常检测")
        
        return lessons
    
    def run_training_session(self, num_battles: int = 5) -> Dict:
        """运行训练会话"""
        print(f"\n{'#'*60}")
        print(f"# 白虎红蓝对抗训练会话")
        print(f"# 训练场次: {num_battles}")
        print(f"{'#'*60}")
        
        attack_types = list(AttackType)
        
        for i in range(num_battles):
            attack_type = attack_types[i % len(attack_types)]
            self.run_battle(attack_type=attack_type)
        
        return self.get_training_report()
    
    def get_training_report(self) -> Dict:
        """获取训练报告"""
        if self.training_stats['total_battles'] == 0:
            return {"error": "No battles completed yet"}
        
        total = self.training_stats['total_battles']
        
        report = {
            'total_battles': total,
            'red_wins': self.training_stats['red_wins'],
            'blue_wins': self.training_stats['blue_wins'],
            'draws': self.training_stats['draws'],
            'red_win_rate': self.training_stats['red_wins'] / total,
            'blue_win_rate': self.training_stats['blue_wins'] / total,
            'draw_rate': self.training_stats['draws'] / total,
            'system_robustness': self.training_stats['blue_wins'] / total + 
                                (self.training_stats['draws'] / total) * 0.5,
            'recent_battles': [
                {
                    'battle_id': b.battle_id,
                    'attack_type': b.scenario.attack_type.value,
                    'winner': b.winner,
                    'red_score': b.red_score,
                    'blue_score': b.blue_score
                }
                for b in self.battle_history[-5:]
            ]
        }
        
        return report
    
    def export_training_data(self, filepath: str):
        """导出训练数据"""
        data = {
            'training_stats': self.training_stats,
            'battle_history': [
                {
                    'battle_id': b.battle_id,
                    'scenario': {
                    'attack_id': b.scenario.attack_id,
                    'attack_type': b.scenario.attack_type.value,
                    'target': b.scenario.target,
                    'intensity': b.scenario.intensity,
                    'duration': b.scenario.duration,
                    'payload': b.scenario.payload,
                    'timestamp': b.scenario.timestamp
                },
                    'defenses': [
                    {
                        'defense_id': d.defense_id,
                        'defense_type': d.defense_type.value,
                        'target': d.target,
                        'effectiveness': d.effectiveness,
                        'response_time': d.response_time,
                        'timestamp': d.timestamp
                    }
                    for d in b.defenses
                ],
                    'red_score': b.red_score,
                    'blue_score': b.blue_score,
                    'winner': b.winner,
                    'lessons_learned': b.lessons_learned,
                    'timestamp': b.timestamp
                }
                for b in self.battle_history
            ]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 训练数据已导出: {filepath}")


# 演示
if __name__ == '__main__':
    print("="*60)
    print("🛡️ 白虎红蓝对抗训练系统 v1.0")
    print("="*60)
    
    # 创建对抗训练实例
    battle = RedBlueBattle()
    
    # 运行训练会话
    report = battle.run_training_session(num_battles=5)
    
    # 输出训练报告
    print(f"\n{'='*60}")
    print("📈 训练总结报告")
    print(f"{'='*60}")
    print(f"总对抗次数: {report['total_battles']}")
    print(f"红队获胜: {report['red_wins']} ({report['red_win_rate']:.1%})")
    print(f"蓝队获胜: {report['blue_wins']} ({report['blue_win_rate']:.1%})")
    print(f"平局: {report['draws']} ({report['draw_rate']:.1%})")
    print(f"\n系统鲁棒性评分: {report['system_robustness']:.2f}/1.0")
    
    if report['system_robustness'] > 0.8:
        print("✅ 系统防御能力优秀")
    elif report['system_robustness'] > 0.6:
        print("⚠️ 系统防御能力良好，仍有提升空间")
    else:
        print("❌ 系统防御能力较弱，需要加强")
    
    # 导出训练数据
    battle.export_training_data('baihu_redblue_training.json')
    
    print("\n✅ 白虎红蓝对抗训练完成")
