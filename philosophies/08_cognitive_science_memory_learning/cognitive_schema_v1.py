"""
认知API统一Schema规范 V1.0
定义所有10个认知API的输入/输出JSON Schema
确保四象飞轮各层之间数据可互操作
"""
import json

COGNITIVE_SCHEMA_V1 = {
    "version": "1.0",
    "description": "SkyCetus Cognitive API Unified Schema Specification",
    "timestamp": "2026-04-25",
    
    # ===== 通用信封格式 =====
    "envelope": {
        "request": {
            "api_id": {"type": "string", "required": True, "enum": [
                "SC-USER", "SC-PROB", "SC-VAL", "SC-SOL", "SC-RISK",
                "SC-RES", "SC-CON", "SC-COMP", "SC-EXEC", "SC-NAR"
            ]},
            "version": {"type": "string", "default": "1.0"},
            "mode": {"type": "string", "enum": ["template", "llm"], "default": "template"},
            "model": {"type": "string", "enum": ["bailian", "minimax", "kimi", "auto"], "default": "auto"},
            "params": {"type": "object", "required": True},
            "context": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "flywheel_round": {"type": "integer"},
                    "parent_api_id": {"type": "string"},
                    "residual_ref": {"type": "string"}
                }
            },
            "metadata": {"type": "object"}
        },
        "response": {
            "api_id": {"type": "string", "required": True},
            "api_name": {"type": "string", "required": True},
            "success": {"type": "boolean", "required": True},
            "result": {"type": "object", "required": True},
            "model": {"type": "string"},
            "error": {"type": "string", "nullable": True},
            "usage": {
                "type": "object",
                "properties": {
                    "prompt_tokens": {"type": "integer"},
                    "completion_tokens": {"type": "integer"},
                    "total_tokens": {"type": "integer"}
                }
            },
            "timestamp": {"type": "string", "format": "iso8601"},
            "execution_id": {"type": "string"},
            "residual": {
                "type": "object",
                "description": "残差数据：predicted vs actual的差异，用于R6学习",
                "properties": {
                    "confidence": {"type": "number", "min": 0, "max": 1},
                    "uncertainty_areas": {"type": "array", "items": {"type": "string"}},
                    "human_override": {"type": "boolean", "default": False},
                    "override_reason": {"type": "string"}
                }
            }
        }
    },
    
    # ===== 10个认知API的参数Schema =====
    "apis": {
        "SC-USER": {
            "name": "User Definition",
            "beast": "qinglong",
            "phase": "diverge",
            "input_schema": {
                "product": {"type": "string", "required": True, "description": "产品/服务名称"},
                "context": {"type": "string", "description": "背景信息"},
                "constraints": {"type": "string", "description": "约束条件"}
            },
            "output_schema": {
                "user_segments": {"type": "array", "items": {"segment_id": "str", "name": "str", "pain_points": ["str"], "needs": ["str"], "willingness_to_pay": "str"}},
                "primary_persona": {"type": "object", "properties": {"name": "str", "role": "str", "goals": ["str"], "frustrations": ["str"]}},
                "user_journey": {"type": "array", "items": {"stage": "str", "action": "str", "touchpoint": "str", "emotion": "str", "opportunity": "str"}},
                "key_insight": {"type": "string"}
            }
        },
        "SC-PROB": {
            "name": "Problem Decomposition",
            "beast": "qinglong",
            "phase": "diverge",
            "input_schema": {
                "problem": {"type": "string", "required": True},
                "context": {"type": "string"},
                "depth": {"type": "integer", "default": 3}
            },
            "output_schema": {
                "root_problem": {"type": "object", "properties": {"id": "str", "statement": "str", "complexity": "int", "ambiguity": "int"}},
                "sub_problems": {"type": "array", "items": {"id": "str", "parent_id": "str", "statement": "str", "dependencies": ["str"], "priority": "str"}},
                "critical_path": {"type": "array", "items": "str"},
                "parallel_groups": {"type": "array", "items": ["str"]},
                "key_assumption": {"type": "string"}
            }
        },
        "SC-VAL": {
            "name": "Value Assessment",
            "beast": "baihu",
            "phase": "evaluate",
            "input_schema": {
                "solution": {"type": "string", "required": True},
                "criteria": {"type": "array", "items": "str"},
                "stakeholders": {"type": "array", "items": "str"}
            },
            "output_schema": {
                "value_dimensions": {"type": "array", "items": {"dimension": "str", "score": "int", "evidence": "str"}},
                "stakeholder_impact": {"type": "array", "items": {"stakeholder": "str", "impact": "str", "sentiment": "str"}},
                "total_value_score": {"type": "number"},
                "value_drivers": {"type": "array", "items": "str"}
            }
        },
        "SC-SOL": {
            "name": "Solution Generation",
            "beast": "qinglong",
            "phase": "diverge",
            "input_schema": {
                "problem_decomposition": {"type": "object", "description": "SC-PROB输出"},
                "constraints": {"type": "object", "description": "SC-CON输出"},
                "resources": {"type": "object", "description": "SC-RES输出"}
            },
            "output_schema": {
                "solutions": {"type": "array", "items": {"id": "str", "name": "str", "category": "str", "description": "str", "feasibility": "int", "risk": "int"}},
                "recommendation": {"type": "object", "properties": {"best": "str", "reason": "str"}},
                "trade_off_matrix": {"type": "array"}
            }
        },
        "SC-RISK": {
            "name": "Risk Analysis",
            "beast": "baihu",
            "phase": "evaluate",
            "input_schema": {
                "project": {"type": "string", "required": True},
                "solutions": {"type": "array", "description": "SC-SOL输出"},
                "known_risks": {"type": "array"}
            },
            "output_schema": {
                "risks": {"type": "array", "items": {"id": "str", "category": "str", "probability": "int", "impact": "int", "mitigation": "str"}},
                "risk_matrix": {"type": "object"},
                "top_risks": {"type": "array", "items": "str"}
            }
        },
        "SC-RES": {
            "name": "Resource Assessment",
            "beast": "xuanwu",
            "phase": "converge",
            "input_schema": {
                "objective": {"type": "string", "required": True},
                "available_resources": {"type": "string"},
                "timeline": {"type": "string"}
            },
            "output_schema": {
                "resource_inventory": {"type": "object", "properties": {"human": "array", "technical": "array", "financial": "object", "time": "object", "knowledge": "array"}},
                "resource_gaps": {"type": "array"},
                "go_no_go": {"type": "object", "properties": {"recommendation": "str", "key_condition": "str"}}
            }
        },
        "SC-CON": {
            "name": "Constraint Identification",
            "beast": "baihu",
            "phase": "evaluate",
            "input_schema": {
                "project": {"type": "string", "required": True},
                "known_constraints": {"type": "string"},
                "environment": {"type": "string"}
            },
            "output_schema": {
                "constraints": {"type": "array", "items": {"id": "str", "category": "str", "type": "str", "relaxable": "bool"}},
                "binding_constraints": {"type": "array", "items": "str"},
                "hidden_constraints": {"type": "array"},
                "degrees_of_freedom": {"type": "array", "items": "str"}
            }
        },
        "SC-COMP": {
            "name": "Competitive Analysis",
            "beast": "baihu",
            "phase": "evaluate",
            "input_schema": {
                "product": {"type": "string", "required": True},
                "market": {"type": "string"},
                "known_competitors": {"type": "string"}
            },
            "output_schema": {
                "market_landscape": {"type": "object"},
                "competitors": {"type": "array"},
                "our_position": {"type": "object", "properties": {"unique_advantages": "array", "competitive_moat": "str"}},
                "strategic_moves": {"type": "array"}
            }
        },
        "SC-EXEC": {
            "name": "Execution Planning",
            "beast": "xuanwu",
            "phase": "converge",
            "input_schema": {
                "solution": {"type": "object", "description": "选定的方案"},
                "resources": {"type": "object", "description": "SC-RES输出"},
                "constraints": {"type": "object", "description": "SC-CON输出"}
            },
            "output_schema": {
                "execution_plan": {"type": "object", "properties": {"phases": "array", "milestones": "array", "dependencies": "array"}},
                "resource_allocation": {"type": "array"},
                "risk_mitigation_plan": {"type": "array"},
                "success_criteria": {"type": "array"}
            }
        },
        "SC-NAR": {
            "name": "Narrative Generation",
            "beast": "zhuque",
            "phase": "output",
            "input_schema": {
                "analysis_results": {"type": "object", "description": "前序API的聚合结果"},
                "audience": {"type": "string"},
                "format": {"type": "string", "enum": ["report", "pitch", "brief", "executive_summary"]}
            },
            "output_schema": {
                "narrative": {"type": "string"},
                "key_messages": {"type": "array", "items": "str"},
                "visualizations": {"type": "array", "items": {"type": "str", "description": "str"}},
                "call_to_action": {"type": "string"}
            }
        }
    },
    
    # ===== 四象飞轮数据流规范 =====
    "flywheel_data_flow": {
        "qinglong_to_baihu": {
            "description": "青龙发散→白虎评估：多方案传递",
            "format": {"solutions": "array", "divergence_score": "number", "source_apis": ["SC-USER", "SC-PROB", "SC-SOL"]}
        },
        "baihu_to_xuanwu": {
            "description": "白虎评估→玄武收敛：评估结果传递",
            "format": {"ranked_solutions": "array", "risk_assessment": "object", "constraints": "object", "source_apis": ["SC-VAL", "SC-RISK", "SC-CON", "SC-COMP"]}
        },
        "xuanwu_to_zhuque": {
            "description": "玄武收敛→朱雀输出：执行计划传递",
            "format": {"execution_plan": "object", "resource_plan": "object", "source_apis": ["SC-RES", "SC-EXEC"]}
        },
        "zhuque_output": {
            "description": "朱雀输出：最终交付物",
            "format": {"narrative": "string", "deliverables": "array", "source_apis": ["SC-NAR"]}
        },
        "residual_feedback": {
            "description": "残差反馈：从输出到输入的学习环",
            "format": {"predicted": "object", "actual": "object", "delta": "object", "lesson": "string", "weight_update": "object"}
        }
    }
}


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 60)
    print("Cognitive API Unified Schema V1.0 - Validation")
    print("=" * 60)
    
    schema = COGNITIVE_SCHEMA_V1
    
    print(f"\nVersion: {schema['version']}")
    print(f"Total APIs: {len(schema['apis'])}")
    
    print("\n[API Distribution by Beast]")
    beast_map = {}
    for api_id, api_def in schema['apis'].items():
        beast = api_def['beast']
        beast_map.setdefault(beast, []).append(api_id)
    for beast, apis in beast_map.items():
        print(f"  {beast}: {apis}")
    
    print("\n[Data Flow Validation]")
    for flow_name, flow_def in schema['flywheel_data_flow'].items():
        print(f"  {flow_name}: {flow_def['description']}")
    
    # Validate all APIs have required fields
    print("\n[Schema Completeness Check]")
    required_fields = ['name', 'beast', 'phase', 'input_schema', 'output_schema']
    all_valid = True
    for api_id, api_def in schema['apis'].items():
        missing = [f for f in required_fields if f not in api_def]
        if missing:
            print(f"  [FAIL] {api_id}: missing {missing}")
            all_valid = False
        else:
            print(f"  [OK] {api_id}: {api_def['name']} ({api_def['beast']}/{api_def['phase']})")
    
    print(f"\nResult: {'ALL VALID' if all_valid else 'SOME INVALID'}")
    
    # Save schema
    schema_json = json.dumps(schema, ensure_ascii=False, indent=2)
    print(f"Schema size: {len(schema_json)} bytes")
