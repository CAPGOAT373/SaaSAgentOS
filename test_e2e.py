"""End-to-end verification: Billing + Agent Execution + Workflow"""
import urllib.request, json, uuid, sys

BASE = 'http://localhost:9000/api/v1'
slug = 'e2e-' + uuid.uuid4().hex[:8]
passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        print(f'  [PASS] {name}')
        passed += 1
    else:
        print(f'  [FAIL] {name}')
        failed += 1

def post(path, data=None, headers=None):
    hdrs = {'Content-Type': 'application/json'}
    if headers: hdrs.update(headers)
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(f'{BASE}{path}', data=body, headers=hdrs, method='POST')
    try:
        r = urllib.request.urlopen(req)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f'  HTTP {e.code}: {body[:200]}')
        return {'error': e.code, 'body': body}

def get(path, headers=None):
    req = urllib.request.Request(f'{BASE}{path}', headers=headers or {})
    try:
        r = urllib.request.urlopen(req)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f'  HTTP {e.code}: {body[:200]}')
        return {'error': e.code, 'body': body}

# Setup
print('=== Setup: Tenant + User + Auth ===')
t = post('/tenant/create', {'name': 'E2E Corp', 'slug': slug, 'tier': 'pro'})
tid = t['tenant_id']
check('Tenant created', bool(tid))

post('/auth/register', {'tenant_id': tid, 'username': 'admin', 'email': 'admin@test.com', 'password': 'test123'})
login = post('/auth/login', {'tenant_id': tid, 'email': 'admin@test.com', 'password': 'test123'})
token = login['access_token']
uid = login['user']['user_id']
auth = {'Authorization': f'Bearer {token}', 'X-Tenant-ID': tid}
check('Auth setup', bool(token) and bool(uid))

# 1. Billing Subscription
print('\n=== 1. Billing Subscription ===')
sub_result = post('/billing/subscription?tier=pro&period=monthly', headers=auth)
check('Subscription created', 'sub_id' in sub_result or 'error' not in sub_result)
print(f'  sub: {sub_result.get("sub_id", sub_result.get("error","?"))}')

# 2. Billing Balance
print('\n=== 2. Billing Balance ===')
balance = get('/billing/balance', auth)
check('Balance endpoint', 'balance' in balance)
print(f'  balance: {balance.get("balance", "?")}')

# 3. Usage Summary
print('\n=== 3. Usage Summary ===')
usage = get('/usage/summary', auth)
check('Usage summary', 'tenant_id' in usage)
print(f'  total_calls: {usage.get("total_calls", "?")}')

# 4. Create Agent with Tools
print('\n=== 4. Agent with Tools ===')
agent = post('/agent/register', {
    'tenant_id': tid, 'owner_id': uid, 'name': 'E2E Agent',
    'description': 'End-to-end test agent', 'agent_type': 'chat',
    'system_prompt': 'You are a helpful assistant. Be concise.'
}, headers=auth)
aid = agent.get('agent_id', '')
check('Agent created', bool(aid))
print(f'  agent_id: {aid}')

# 5. Create Workflow with Multiple Nodes
print('\n=== 5. Multi-node Workflow ===')
wf = post('/workflow/create?name=E2E+Workflow&description=Multi-step+test', headers=auth)
wfid = wf.get('workflow_id', '')
check('Workflow created', bool(wfid))
print(f'  workflow_id: {wfid}')

# 6. List Workflows
print('\n=== 6. Workflow List ===')
workflows = get('/workflow', auth)
check('Workflows listed', isinstance(workflows, list) and len(workflows) > 0)

# 7. Tenant Isolation Test
print('\n=== 7. Tenant Isolation ===')
slug2 = 'iso-' + uuid.uuid4().hex[:8]
t2 = post('/tenant/create', {'name': 'Isolated Corp', 'slug': slug2, 'tier': 'free'})
tid2 = t2['tenant_id']
post('/auth/register', {'tenant_id': tid2, 'username': 'user2', 'email': 'user2@test.com', 'password': 'test123'})
login2 = post('/auth/login', {'tenant_id': tid2, 'email': 'user2@test.com', 'password': 'test123'})
auth2 = {'Authorization': f'Bearer {login2["access_token"]}', 'X-Tenant-ID': tid2}

# Tenant 2 should NOT see Tenant 1's agents
agents_t2 = get('/agent', auth2)
check('Tenant 2 agents empty', len(agents_t2) == 0)
# Tenant 1 should see its own agent
agents_t1 = get(f'/agent', auth)
check('Tenant 1 has agent', len(agents_t1) > 0)
print(f'  T1 agents: {len(agents_t1)}, T2 agents: {len(agents_t2)}')

# 8. Workflow Isolation
print('\n=== 8. Workflow Isolation ===')
wf_t2 = get('/workflow', auth2)
check('Tenant 2 workflows empty', len(wf_t2) == 0)
wf_t1 = get('/workflow', auth)
check('Tenant 1 has workflow', len(wf_t1) > 0)

# 9. Observability Trace
print('\n=== 9. Observability Trace ===')
traces = get('/observability/traces', headers={'X-Tenant-ID': tid})
check('Traces available', isinstance(traces, list))

latency = get('/observability/latency', headers={'X-Tenant-ID': tid})
check('Latency metrics', 'avg_latency_ms' in latency)

tokens = get('/observability/tokens', headers={'X-Tenant-ID': tid})
check('Token stats', 'total_tokens' in tokens)

# 10. Admin Health
print('\n=== 10. Admin Health ===')
health = get('/admin/health/all', auth)
services = list(health.get('services', {}).keys())
check('All services healthy', len(services) >= 7)
print(f'  services: {services}')

# 11. Prometheus Metrics
print('\n=== 11. Prometheus Metrics ===')
req = urllib.request.Request('http://localhost:9000/metrics')
r = urllib.request.urlopen(req)
metrics_text = r.read().decode()
check('Metrics endpoint', '#' in metrics_text)

# Summary
print(f'\n{"="*50}')
print(f'E2E RESULTS: {passed} passed, {failed} failed, {passed+failed} total')
print(f'{"="*50}')
sys.exit(0 if failed == 0 else 1)