from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from middleware.tenant_rbac import TenantRBACMiddleware
import redis

app = FastAPI()


class MockRedis:
    def __init__(self):
        self.data = {}
        self.is_up = True

    def ping(self):
        if not self.is_up:
            raise redis.ConnectionError("Redis is down")
        return True

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    def incr(self, key):
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    def expire(self, key, time):
        pass


mock_redis = MockRedis()
app.add_middleware(
    TenantRBACMiddleware, redis_client=mock_redis, global_rate_limit=5, cluster_nodes=2
)


@app.get("/test")
async def test_endpoint(request: Request):
    return {"tenant_context": request.state.tenant_context}


client = TestClient(app)


def test_missing_headers():
    response = client.get("/test")
    assert response.status_code == 401
    assert "Missing X-Tenant-ID header" in response.json()["detail"]

    response = client.get("/test", headers={"X-Tenant-ID": "tenant1"})
    assert response.status_code == 401
    assert "Missing Authorization header" in response.json()["detail"]


def test_valid_request():
    response = client.get(
        "/test", headers={"X-Tenant-ID": "tenant1", "Authorization": "token123"}
    )
    assert response.status_code == 200
    assert response.json()["tenant_context"]["tenant_id"] == "tenant1"
    assert response.json()["tenant_context"]["authenticated"] is True
    assert response.json()["tenant_context"]["fallback_mode"] is False


def test_revoked_token():
    mock_redis.set("revoked_token:revoked123", "1")
    response = client.get(
        "/test", headers={"X-Tenant-ID": "tenant1", "Authorization": "revoked123"}
    )
    assert response.status_code == 403
    assert "Token revoked" in response.json()["detail"]


def test_global_rate_limit():
    for _ in range(5):
        client.get(
            "/test", headers={"X-Tenant-ID": "tenant_gl", "Authorization": "token123"}
        )

    response = client.get(
        "/test", headers={"X-Tenant-ID": "tenant_gl", "Authorization": "token123"}
    )
    assert response.status_code == 429
    assert "Global Rate Limit Exceeded" in response.json()["detail"]


def test_fallback_mode_local_rate_limit():
    mock_redis.is_up = False

    # Global is 5, cluster is 2, local limit should be max(1, 5//2) = 2
    for _ in range(2):
        res = client.get(
            "/test", headers={"X-Tenant-ID": "tenant_loc", "Authorization": "token123"}
        )
        assert res.status_code == 200
        assert res.json()["tenant_context"]["fallback_mode"] is True

    response = client.get(
        "/test", headers={"X-Tenant-ID": "tenant_loc", "Authorization": "token123"}
    )
    assert response.status_code == 429
    assert "Local Rate Limit Exceeded" in response.json()["detail"]


if __name__ == "__main__":
    test_missing_headers()
    test_valid_request()
    test_revoked_token()
    test_global_rate_limit()
    test_fallback_mode_local_rate_limit()
    print("All tests passed!")
