
"""
cognitive_gateway.py - 认知API统一网关
标准JSON schema、鉴权、计量、错误处理、重试
"""
import json, time, hashlib, traceback
from datetime import datetime
from functools import wraps

class CognitiveGateway:
    """
    Unified gateway for 10 cognitive APIs (SC-USER through SC-NAR).
    Features: JSON schema validation, auth, metering, error handling, retry.
    """
    
    # Standard schema for all cognitive APIs
    SCHEMA = {
        'SC-USER': {'required': ['query'], 'optional': ['context', 'history']},
        'SC-PROB': {'required': ['description'], 'optional': ['domain', 'constraints']},
        'SC-VAL': {'required': ['options'], 'optional': ['criteria', 'weights']},
        'SC-SOL': {'required': ['problem_id', 'constraints'], 'optional': ['budget', 'timeline']},
        'SC-RISK': {'required': ['scenario'], 'optional': ['risk_tolerance', 'domain']},
        'SC-RES': {'required': ['task_id', 'resources'], 'optional': ['priority', 'constraints']},
        'SC-CON': {'required': ['inputs'], 'optional': ['strategy', 'threshold']},
        'SC-COMP': {'required': ['task_a', 'task_b'], 'optional': ['dimensions', 'weights']},
        'SC-EXEC': {'required': ['plan'], 'optional': ['nodes', 'deadline']},
        'SC-NAR': {'required': ['data'], 'optional': ['audience', 'format', 'tone']},
    }
    
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    
    def __init__(self, auth_key=None):
        self.auth_key = auth_key or 'default-gateway-key'
        self.handlers = {}
        self.metrics = {
            'total_calls': 0,
            'successful': 0,
            'failed': 0,
            'retried': 0,
            'by_api': {},
        }
        self.call_log = []
    
    def register_handler(self, api_name, handler_fn):
        """Register a handler function for a cognitive API"""
        if api_name not in self.SCHEMA:
            raise ValueError(f"Unknown API: {api_name}. Valid: {list(self.SCHEMA.keys())}")
        self.handlers[api_name] = handler_fn
    
    def validate_input(self, api_name, payload):
        """Validate input against schema"""
        if api_name not in self.SCHEMA:
            return False, f"Unknown API: {api_name}"
        
        schema = self.SCHEMA[api_name]
        missing = [f for f in schema['required'] if f not in payload]
        if missing:
            return False, f"Missing required fields: {missing}"
        
        return True, "OK"
    
    def authenticate(self, provided_key):
        """Simple auth check"""
        return provided_key == self.auth_key
    
    def call(self, api_name, payload, auth_key=None, retry=True):
        """
        Main gateway entry point.
        Returns: {status, data, api, latency_ms, call_id}
        """
        call_id = f"call-{hashlib.md5(f'{api_name}{time.time()}'.encode()).hexdigest()[:12]}"
        start = time.time()
        
        self.metrics['total_calls'] += 1
        if api_name not in self.metrics['by_api']:
            self.metrics['by_api'][api_name] = {'calls': 0, 'success': 0, 'fail': 0}
        self.metrics['by_api'][api_name]['calls'] += 1
        
        # Auth
        if auth_key and not self.authenticate(auth_key):
            return self._error_response(call_id, api_name, 'AUTH_FAILED', 'Invalid authentication key', start)
        
        # Validate
        valid, msg = self.validate_input(api_name, payload)
        if not valid:
            return self._error_response(call_id, api_name, 'VALIDATION_ERROR', msg, start)
        
        # Check handler
        if api_name not in self.handlers:
            return self._error_response(call_id, api_name, 'NO_HANDLER', f'No handler registered for {api_name}', start)
        
        # Execute with retry
        last_error = None
        attempts = self.MAX_RETRIES if retry else 1
        
        for attempt in range(attempts):
            try:
                result = self.handlers[api_name](payload)
                latency = (time.time() - start) * 1000
                
                self.metrics['successful'] += 1
                self.metrics['by_api'][api_name]['success'] += 1
                
                response = {
                    'status': 'success',
                    'call_id': call_id,
                    'api': api_name,
                    'data': result,
                    'latency_ms': round(latency, 1),
                    'attempt': attempt + 1,
                    'timestamp': datetime.now().isoformat()
                }
                
                self._log_call(response)
                return response
                
            except Exception as e:
                last_error = str(e)
                if attempt < attempts - 1:
                    self.metrics['retried'] += 1
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
        
        # All retries exhausted
        self.metrics['failed'] += 1
        self.metrics['by_api'][api_name]['fail'] += 1
        return self._error_response(call_id, api_name, 'HANDLER_ERROR', last_error, start)
    
    def _error_response(self, call_id, api_name, error_code, message, start_time):
        latency = (time.time() - start_time) * 1000
        response = {
            'status': 'error',
            'call_id': call_id,
            'api': api_name,
            'error': {'code': error_code, 'message': message},
            'latency_ms': round(latency, 1),
            'timestamp': datetime.now().isoformat()
        }
        self._log_call(response)
        return response
    
    def _log_call(self, response):
        self.call_log.append(response)
        if len(self.call_log) > 1000:
            self.call_log = self.call_log[-500:]
    
    def get_metrics(self):
        return self.metrics
    
    def get_recent_calls(self, limit=10):
        return self.call_log[-limit:]
    
    def list_apis(self):
        return {
            name: {
                'schema': schema,
                'handler_registered': name in self.handlers
            }
            for name, schema in self.SCHEMA.items()
        }


# === Flask route integration ===
def create_gateway_routes(app, gateway):
    from flask import jsonify, request as req
    
    @app.route('/api/v1/cognitive/<api_name>', methods=['POST'])
    def cognitive_call(api_name):
        data = req.get_json() or {}
        auth = req.headers.get('X-Cognitive-Key', '')
        result = gateway.call(api_name.upper(), data, auth_key=auth if auth else None)
        status_code = 200 if result['status'] == 'success' else 400
        return jsonify(result), status_code
    
    @app.route('/api/v1/cognitive/metrics')
    def cognitive_metrics():
        return jsonify(gateway.get_metrics())
    
    @app.route('/api/v1/cognitive/apis')
    def cognitive_list():
        return jsonify(gateway.list_apis())


# === Self-test ===
if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    gw = CognitiveGateway(auth_key='test-key')
    
    # Register a test handler
    def mock_handler(payload):
        return {'result': 'processed', 'input_keys': list(payload.keys())}
    
    for api in CognitiveGateway.SCHEMA:
        gw.register_handler(api, mock_handler)
    
    # Test calls
    r1 = gw.call('SC-USER', {'query': 'test question'}, auth_key='test-key')
    assert r1['status'] == 'success', f"Expected success, got {r1['status']}"
    
    r2 = gw.call('SC-USER', {})  # Missing required field
    assert r2['status'] == 'error'
    
    r3 = gw.call('SC-INVALID', {'x': 1})  # Unknown API
    assert r3['status'] == 'error'
    
    metrics = gw.get_metrics()
    print("=== Cognitive Gateway Test ===")
    print(f"Total calls: {metrics['total_calls']}")
    print(f"Successful: {metrics['successful']}")
    print(f"Failed: {metrics['failed']}")
    print(f"APIs registered: {len(gw.handlers)}/10")
    print(f"Recent call: {r1['call_id']} ({r1['latency_ms']}ms)")
    print("Cognitive Gateway: OK")
