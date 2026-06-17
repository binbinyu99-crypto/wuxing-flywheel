# -*- coding: utf-8 -*-
"""
Node Discovery Engine v1.0
白虎·链接飞轮 — 节点发现与匹配

功能:
- 节点注册自己的能力标签
- 需求方发布能力需求
- 引擎自动匹配 供给↔需求
- 输出: 推荐连接列表 + 匹配分数
"""
import json, os, hashlib
from datetime import datetime

class NodeDiscovery:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "node_registry.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"nodes": {}, "requests": [], "connections": [], "meta": {"version": "1.0"}}
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def register_capabilities(self, node_id, name, capabilities, domains=None):
        """Register a node with its capabilities"""
        self.data["nodes"][node_id] = {
            "name": name,
            "capabilities": capabilities,  # ["research", "coding", "analysis", ...]
            "domains": domains or [],  # ["finance", "materials", "medical", ...]
            "available": True,
            "registered": datetime.now().isoformat(),
            "connections_made": 0,
        }
        self._save()
        return True
    
    def post_request(self, requester_id, needed_capabilities, domain=None, description=""):
        """Post a capability request"""
        req_id = hashlib.md5(f"{requester_id}_{time.time()}".encode()).hexdigest()[:10]
        request = {
            "id": req_id,
            "requester": requester_id,
            "needed": needed_capabilities,
            "domain": domain,
            "description": description,
            "status": "open",
            "created": datetime.now().isoformat(),
        }
        self.data["requests"].append(request)
        self._save()
        return request
    
    def match(self, request_id=None):
        """Find best matches for open requests"""
        results = []
        requests = [r for r in self.data["requests"] if r["status"] == "open"]
        if request_id:
            requests = [r for r in requests if r["id"] == request_id]
        
        for req in requests:
            matches = []
            for nid, node in self.data["nodes"].items():
                if nid == req["requester"]:
                    continue
                if not node["available"]:
                    continue
                
                # Score: capability overlap + domain match
                cap_overlap = len(set(req["needed"]) & set(node["capabilities"]))
                cap_score = cap_overlap / max(len(req["needed"]), 1)
                
                domain_score = 0
                if req.get("domain") and req["domain"] in node.get("domains", []):
                    domain_score = 0.3
                
                total = round(cap_score * 0.7 + domain_score, 3)
                if total > 0:
                    matches.append({"node_id": nid, "name": node["name"], "score": total, "matched_caps": list(set(req["needed"]) & set(node["capabilities"]))})
            
            matches.sort(key=lambda x: x["score"], reverse=True)
            results.append({"request_id": req["id"], "requester": req["requester"], "matches": matches[:5]})
        
        return results
    
    def connect(self, node_a, node_b, context=""):
        """Record a connection between two nodes"""
        conn = {
            "id": hashlib.md5(f"{node_a}_{node_b}_{time.time()}".encode()).hexdigest()[:10],
            "nodes": [node_a, node_b],
            "context": context,
            "created": datetime.now().isoformat(),
            "active": True,
        }
        self.data["connections"].append(conn)
        for nid in [node_a, node_b]:
            if nid in self.data["nodes"]:
                self.data["nodes"][nid]["connections_made"] += 1
        self._save()
        return conn
    
    def get_network_stats(self):
        total_nodes = len(self.data["nodes"])
        total_connections = len([c for c in self.data["connections"] if c["active"]])
        total_requests = len(self.data["requests"])
        open_requests = len([r for r in self.data["requests"] if r["status"] == "open"])
        density = (2 * total_connections) / (total_nodes * (total_nodes - 1)) if total_nodes > 1 else 0
        return {
            "nodes": total_nodes,
            "connections": total_connections,
            "requests": total_requests,
            "open_requests": open_requests,
            "network_density": round(density, 3),
        }


def main():
    engine = NodeDiscovery()
    
    # Register team capabilities
    engine.register_capabilities("spark", "Spark", 
        ["research", "coding", "deployment", "analysis", "design", "coordination"],
        ["finance", "materials", "semiconductor", "medical"])
    engine.register_capabilities("etern", "Etern",
        ["architecture", "planning", "analysis", "strategy"],
        ["finance", "governance"])
    engine.register_capabilities("xiaoyuan", "\u5c0f\u5143",
        ["research", "data_collection", "structuring"],
        ["materials", "medical"])
    engine.register_capabilities("lucas", "Lucas",
        ["infrastructure", "database", "server", "deployment"],
        ["devops"])
    engine.register_capabilities("xiaok", "\u5c0fK",
        ["coding", "research"],
        ["general"])
    
    # Post some requests
    engine.post_request("spark", ["database", "server"], "devops", "Hub\u751f\u4ea7\u73af\u5883\u90e8\u7f72")
    engine.post_request("spark", ["research", "data_collection"], "materials", "\u6750\u6599\u56fe\u8c31\u6df1\u5ea6\u7814\u7a76")
    engine.post_request("etern", ["coding", "deployment"], "finance", "\u6e05\u7b97\u7cfb\u7edf\u539f\u578b")
    
    # Match
    matches = engine.match()
    
    # Auto-connect top matches
    for m in matches:
        if m["matches"]:
            top = m["matches"][0]
            engine.connect(m["requester"], top["node_id"], f"auto-match for request {m['request_id']}")
    
    stats = engine.get_network_stats()
    print("=== Node Discovery Engine v1.0 ===")
    print(f"Nodes: {stats['nodes']}, Connections: {stats['connections']}, Density: {stats['network_density']}")
    print(f"Requests: {stats['requests']} ({stats['open_requests']} open)")
    print("\nMatches:")
    for m in matches:
        print(f"  Request by {m['requester']}:")
        for match in m["matches"][:3]:
            print(f"    -> {match['name']} (score={match['score']}, caps={match['matched_caps']})")

if __name__ == "__main__":
    import time
    main()
