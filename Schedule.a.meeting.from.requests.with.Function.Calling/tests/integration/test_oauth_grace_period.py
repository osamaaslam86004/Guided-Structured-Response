"""
Integration tests Concurrent worker token rotation race conditions
"""

import asyncio
import pytest
import redis.asyncio as aioredis
from tasks.refresh_oauth_tokens import OAuthTokenManager


@pytest.mark.integration
@pytest.mark.asyncio
class TestOAuthGracePeriodIntegration:
    @pytest.fixture
    async def redis_client(self):
        client = aioredis.from_url("redis://localhost:6379/15", decode_responses=True)
        await client.flushdb()
        yield client
        await client.flushdb()
        await client.close()

    async def test_concurrent_token_refresh_grace_window(self, redis_client):
        """Simulate 5 parallel workers presenting the same legacy refresh token simultaneously."""
        token_manager = OAuthTokenManager(
            redis_client=redis_client, grace_period_seconds=10
        )
        tenant_id = "tenant_test_101"
        user_id = "user_test_888"
        old_refresh_token = "refresh_token_legacy_v1"

        # Mock downstream OAuth provider call
        call_count = 0

        def mock_provider_call(token):
            nonlocal call_count
            call_count += 1
            return {
                "access_token": f"access_token_v2_call_{call_count}",
                "refresh_token": f"refresh_token_v2_call_{call_count}",
            }

        token_manager._call_oauth_provider_refresh = mock_provider_call

        # Execute 5 parallel refresh tasks
        tasks = [
            asyncio.create_task(
                asyncio.to_thread(
                    token_manager.refresh_tokens_atomic,
                    tenant_id,
                    user_id,
                    old_refresh_token,
                )
            )
            for _ in range(5)
        ]
        results = await asyncio.gather(*tasks)

        # Assertions
        assert len(results) == 5
        # The downstream IdP must be called exactly ONCE despite 5 parallel worker calls
        assert call_count == 1

        # All 5 workers must receive valid token pairs (either fresh or served from grace cache)
        for res in results:
            assert res["access_token"] == "access_token_v2_call_1"
            assert res["refresh_token"] == "refresh_token_v2_call_1"

    async def test_out_of_bounds_token_reuse_triggers_family_revocation(
        self, redis_client
    ):
        """Verify that presenting a revoked token OUTSIDE the grace period revokes the entire token family."""
        token_manager = OAuthTokenManager(
            redis_client=redis_client, grace_period_seconds=1
        )
        tenant_id = "tenant_test_101"
        user_id = "user_test_999"
        old_token = "refresh_token_legacy_v1"

        # First refresh -> Success
        token_manager.refresh_tokens_atomic(tenant_id, user_id, old_token)

        # Wait for grace period to expire
        await asyncio.sleep(1.2)

        # Attempt reuse after grace period expiry -> Must raise SecurityException
        with pytest.raises(Exception) as exc_info:
            token_manager.refresh_tokens_atomic(tenant_id, user_id, old_token)

        assert (
            "reuse detected" in str(exc_info.value).lower()
            or "family revoked" in str(exc_info.value).lower()
        )
