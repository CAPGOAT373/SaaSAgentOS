import urllib.request
import json

base = "http://localhost:9002"

# Create tenant
data = json.dumps({"name": "AlphaCorp", "slug": "alpha-corp-v4", "tier": "free"}).encode()
req = urllib.request.Request(
    f"{base}/api/v1/tenant/create",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    r = urllib.request.urlopen(req)
    t = json.loads(r.read())
    print("Tenant:", t["tenant_id"][:8])
except urllib.error.HTTPError as e:
    print("Tenant Error:", e.code, e.read().decode()[:1000])
    exit(1)

# Register user
data2 = json.dumps({
    "tenant_id": t["tenant_id"],
    "username": "admin",
    "email": "admin@alpha.com",
    "password": "pass123",
}).encode()
req2 = urllib.request.Request(
    f"{base}/api/v1/auth/register",
    data=data2,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    r2 = urllib.request.urlopen(req2)
    u = json.loads(r2.read())
    print("User:", u["user_id"][:8])
except urllib.error.HTTPError as e:
    print("Register Error:", e.code, e.read().decode()[:500])
    exit(1)

# Login
data3 = json.dumps({
    "tenant_id": t["tenant_id"],
    "email": "admin@alpha.com",
    "password": "pass123",
}).encode()
req3 = urllib.request.Request(
    f"{base}/api/v1/auth/login",
    data=data3,
    headers={"Content-Type": "application/json"},
    method="POST",
)
r3 = urllib.request.urlopen(req3)
login = json.loads(r3.read())
tok = login["access_token"]
print("Token:", tok[:30] + "...")

# Auth/me
req4 = urllib.request.Request(
    f"{base}/api/v1/auth/me",
    headers={"Authorization": f"Bearer {tok}"},
)
r4 = urllib.request.urlopen(req4)
me = json.loads(r4.read())
print("Auth/me:", me["username"], me["email"])
print("\nALL TESTS PASSED - Swagger Authorize is ready")