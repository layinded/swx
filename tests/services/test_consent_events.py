import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from swx_core.events import event_bus
from swx_core.models.consent import ConsentStatus


class TestConsentEvents:
    async def test_grant_and_withdraw_emit_events_and_clear_cache(self):
        from swx_core.services import consent_service

        session = AsyncMock()
        user_id = uuid.uuid4()
        consent_type = SimpleNamespace(id=uuid.uuid4(), is_active=True)
        granted = SimpleNamespace(id=uuid.uuid4())
        withdrawn_id = uuid.uuid4()
        withdrawn = SimpleNamespace(id=withdrawn_id, version="v1")

        with patch("swx_core.services.consent_service.consent_repository") as mock_repo:
            mock_repo.get_consent_type_by_key = AsyncMock(return_value=consent_type)
            mock_repo.create_user_consent = AsyncMock(return_value=granted)
            mock_repo.get_latest_user_consent = AsyncMock(return_value=granted)
            mock_repo.update_user_consent_status = AsyncMock(return_value=withdrawn)
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                with patch.object(consent_service, "clear_consent_cache") as mock_clear:
                    _ = await consent_service.grant_consent(session, user_id, "privacy", "v1", "127.0.0.1", "ua", "web")
                    grant_call = mock_dispatch.call_args_list[0]
                    assert grant_call.args[0] == "consent.granted"
                    assert grant_call.kwargs["payload"]["user_id"] == str(user_id)
                    assert grant_call.kwargs["payload"]["consent_type_key"] == "privacy"

                    _ = await consent_service.withdraw_consent(session, user_id, "privacy", "127.0.0.1", "ua")
                    withdraw_call = mock_dispatch.call_args_list[1]
                    assert withdraw_call.args[0] == "consent.withdrawn"
                    assert withdraw_call.kwargs["payload"]["consent_id"] == str(withdrawn_id)
                    assert mock_clear.call_count == 2

    async def test_check_expired_consents_emits_event(self):
        from swx_core.services import consent_service

        session = AsyncMock()
        consent_id = uuid.uuid4()
        consent_type_id = uuid.uuid4()
        consent = SimpleNamespace(
            id=consent_id,
            user_id=uuid.uuid4(),
            consent_type_id=consent_type_id,
            version="v2",
            expires_at=consent_service.utc_now_naive() - timedelta(minutes=1),
        )
        updated = SimpleNamespace(id=consent_id)

        with patch("swx_core.services.consent_service.consent_repository") as mock_repo:
            mock_repo.get_consents_by_status = AsyncMock(return_value=[consent])
            mock_repo.update_user_consent_status = AsyncMock(return_value=updated)
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                count = await consent_service.check_expired_consents(session)

        assert count == 1
        assert mock_dispatch.call_args.args[0] == "consent.expired"
        assert mock_dispatch.call_args.kwargs["payload"]["consent_type_id"] == str(consent_type_id)

    async def test_has_consent_cached_returns_cached_value_within_ttl(self):
        from swx_core.services import consent_service

        session = AsyncMock()
        user_id = uuid.uuid4()
        consent_service.clear_consent_cache()
        with patch.object(consent_service, "has_consent", new_callable=AsyncMock, return_value=True) as mock_has:
            first = await consent_service.has_consent_cached(session, user_id, "privacy")
            second = await consent_service.has_consent_cached(session, user_id, "privacy")

        assert first is True and second is True
        assert mock_has.await_count == 1

    async def test_has_consent_returns_false_for_expired_or_missing_records(self):
        from swx_core.services import consent_service

        session = AsyncMock()
        user_id = uuid.uuid4()
        consent_type = SimpleNamespace(id=uuid.uuid4())
        expired = SimpleNamespace(
            status=ConsentStatus.GRANTED.value,
            expires_at=consent_service.utc_now_naive() - timedelta(seconds=1),
        )

        with patch("swx_core.services.consent_service.consent_repository") as mock_repo:
            mock_repo.get_consent_type_by_key = AsyncMock(side_effect=[None, consent_type])
            mock_repo.get_latest_user_consent = AsyncMock(return_value=expired)
            assert await consent_service.has_consent(session, user_id, "privacy") is False
            assert await consent_service.has_consent(session, user_id, "privacy") is False
