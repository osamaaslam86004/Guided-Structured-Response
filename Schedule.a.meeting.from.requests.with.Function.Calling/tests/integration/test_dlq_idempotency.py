"""
Integrations tests for DLQ replay fingerprinting, locks, and quarantine
"""

import json
import pytest
from fastapi.testclient import TestClient
from main import app
import redis


@pytest.mark.integration
class TestDLQAdminIntegration:
    @pytest.fixture
    def client_and_redis(self):
        r = redis.Redis(host="localhost", port=6379, db=14)
        r.flushdb()
        test_client = TestClient(app)

        # Seed a dummy DLQ message
        msg_id = "dlq_msg_404"
        payload = {"meeting_id": "m_990", "action": "CREATE_INVITE", "user_id": "u_12"}
        r.set(
            f"dlq:msg:{msg_id}",
            json.dumps({"message_id": msg_id, "replay_count": 0, "payload": payload}),
        )

        yield test_client, r, msg_id, payload
        r.flushdb()

    def test_successful_idempotent_replay(self, client_and_redis):
        """Verify DLQ replay execution using a valid X-Idempotency-Key."""
        client, r, msg_id, payload = client_and_redis
        headers = {
            "X-Idempotency-Key": "idem_key_unique_001",
            "X-Tenant-ID": "tenant_prod",
        }

        response = client.post(
            "/admin/dlq/replay",
            json={"message_id": msg_id, "override_payload": payload},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "SUCCESS"
        # Message should be removed from DLQ upon successful replay
        assert r.get(f"dlq:msg:{msg_id}") is None

    def test_payload_tampering_rejected_on_key_reuse(self, client_and_redis):
        """Verify that reusing an idempotency key with a MODIFIED payload returns HTTP 422 Unprocessable Entity."""
        client, r, msg_id, payload = client_and_redis
        headers = {
            "X-Idempotency-Key": "idem_key_unique_002",
            "X-Tenant-ID": "tenant_prod",
        }

        # First Call -> Set initial fingerprint
        client.post(
            "/admin/dlq/replay",
            json={"message_id": msg_id, "override_payload": payload},
            headers=headers,
        )

        # Re-seed message to simulate concurrent retry attempt
        r.set(
            f"dlq:msg:{msg_id}",
            json.dumps({"message_id": msg_id, "replay_count": 0, "payload": payload}),
        )

        # Second Call with SAME Key but ALTERED Payload
        tampered_payload = {
            "meeting_id": "m_990",
            "action": "DELETE_ALL",
            "user_id": "u_12",
        }
        response = client.post(
            "/admin/dlq/replay",
            json={"message_id": msg_id, "override_payload": tampered_payload},
            headers=headers,
        )

        assert response.status_code == 422
        assert (
            "payload" in response.json()["detail"].lower()
            or "idempotency" in response.json()["detail"].lower()
        )
