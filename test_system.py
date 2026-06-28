import urllib.request, urllib.error, json, sys, uuid

BASE = 'http://localhost:9000/api/v1'

def post(path, data=None, headers=None):
    hdrs = {'Content-Type': 'application/json'}
    if headers:
        hdrs.update(headers)
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

# Use unique slug
slug = f'test-{uuid.uuid4().hex[:8]}'

# 1. Create tenant
print('=== 1. Create Tenant ===')
t = post('/tenant/create', {'name': 'Test Corp', 'slug': slug, 'tier': 'pro'})
tid = t.get('tenant_id', '')
check('Tenant created', bool(tid))
print(f'  tenant_id: {tid}')

# 2. Register user
print('\n=== 2. Register User ===')
u = post('/auth/register', {'tenant_id': tid, 'username': 'admin', 'email': 'admin@test.com', 'password': 'test123'})
check('User registered', 'user_id' in u or 'error' not in u)

# 3. Login
print('\n=== 3. Login ===')
login = post('/auth/login', {'tenant_id': tid, 'email': 'admin@test.com', 'password': 'test123'})
token = login.get('access_token', '')
uid = login.get('user', {}).get('user_id', '')
check('Login success', bool(token))
print(f'  token: {token[:30]}...')

auth = {'Authorization': f'Bearer {token}', 'X-Tenant-ID': tid}

# 4. Create agent (needs auth headers)
print('\n=== 4. Create Agent ===')
agent = post('/agent/register', {
    'tenant_id': tid, 'owner_id': uid, 'name': 'Test Agent',
    'description': 'A test agent', 'agent_type': 'chat',
    'system_prompt': 'You are a helpful assistant.'
}, headers=auth)
aid = agent.get('agent_id', '')
check('Agent created', bool(aid))
print(f'  agent_id: {aid}')

# 5. Get agent (needs auth headers)
print('\n=== 5. Get Agent ===')
ag = get(f'/agent/{aid}', headers=auth)
check('Get agent', ag.get('name') == 'Test Agent')

# 6. List agents
print('\n=== 6. List Agents ===')
agents = get(f'/agent?tenant_id={tid}', headers=auth)
check('List agents', len(agents) > 0)
print(f'  count: {len(agents)}')

# 7. Create workflow (needs auth headers)
print('\n=== 7. Create Workflow ===')
wf = post('/workflow/create?name=Test+Workflow&description=A+test+workflow', headers=auth)
check('Workflow created', bool(wf.get('workflow_id')))
print(f'  workflow_id: {wf.get("workflow_id", "")}')

# 8. List workflows
print('\n=== 8. List Workflows ===')
workflows = get('/workflow', headers=auth)
check('List workflows', isinstance(workflows, list))
print(f'  count: {len(workflows)}')

# 9. Observability
print('\n=== 9. Observability ===')
traces = get('/observability/traces', headers={'X-Tenant-ID': tid})
check('Traces list', isinstance(traces, list))

latency = get('/observability/latency', headers={'X-Tenant-ID': tid})
check('Latency metrics', 'avg_latency_ms' in latency)

tokens = get('/observability/tokens', headers={'X-Tenant-ID': tid})
check('Token stats', 'total_tokens' in tokens)

# 10. Admin health
print('\n=== 10. Admin Health ===')
health = get('/admin/health/all', auth)
services = list(health.get('services', {}).keys())
check('Admin health', len(services) > 0)
print(f'  services: {services}')

# 11. Metrics
print('\n=== 11. Prometheus Metrics ===')
req = urllib.request.Request('http://localhost:9000/metrics')
try:
    r = urllib.request.urlopen(req)
    metrics_text = r.read().decode()
    check('Metrics endpoint', '#' in metrics_text or 'http_requests_total' in metrics_text)
except urllib.error.HTTPError as e:
    print(f'  HTTP {e.code}: {e.read().decode()[:200]}')
    check('Metrics endpoint', False)

# 12. Billing
print('\n=== 12. Billing ===')
balance = get('/billing/balance', auth)
check('Billing balance', 'balance' in balance)

usage = get('/usage/summary', auth)
check('Usage summary', 'total_requests' in usage or 'tenant_id' in usage)

print(f'\n{"="*50}')
print(f'RESULTS: {passed} passed, {failed} failed, {passed+failed} total')
print(f'{"="*50}')
sys.exit(0 if failed == 0 else 1)