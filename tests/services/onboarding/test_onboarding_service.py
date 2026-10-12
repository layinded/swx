# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for the Onboarding Service."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swx_core.models.onboarding import OnboardingStepStatus
from swx_core.services.onboarding.onboarding_service import (
    OnboardingService,
    OnboardingProgress,
    onboarding,
)


class TestRegisterOnboardingSteps:
    """Tests for step registration."""

    def test_register_steps_adds_new_steps(self):
        """register_steps() adds new step keys."""
        svc = OnboardingService()
        svc.register_steps("profile", "email_verify")

        assert "profile" in svc.registered_steps
        assert "email_verify" in svc.registered_steps

    def test_register_steps_is_idempotent(self):
        """Registering the same step twice does not duplicate it."""
        svc = OnboardingService()
        svc.register_steps("profile")
        svc.register_steps("profile")

        assert svc.registered_steps.count("profile") == 1

    def test_default_steps_are_registered(self):
        """Default steps (profile, email_verify, first_project) are pre-registered."""
        svc = OnboardingService()
        steps = svc.registered_steps
        assert "profile" in steps
        assert "email_verify" in steps
        assert "first_project" in steps

    def test_get_registered_steps_returns_copy(self):
        """registered_steps returns a copy, not the internal list."""
        svc = OnboardingService()
        steps = svc.registered_steps
        steps.append("extra")
        # Internal list should not be affected
        assert "extra" not in svc.registered_steps


class TestInitializeSteps:
    """Tests for initialize_steps (called for new users)."""

    @pytest.mark.asyncio
    async def test_initialize_steps_creates_pending_steps(self):
        """initialize_user() creates pending steps for a new user."""
        svc = OnboardingService()
        # Override to only have 2 steps for this test
        svc._registered_steps = ["profile", "email_verify"]
        session = AsyncMock()
        user_id = uuid.uuid4()

        with patch.object(svc, "_get_existing_keys", new_callable=AsyncMock) as mock_existing:
            mock_existing.return_value = set()

            result = await svc.initialize_user(session, user_id)

        assert len(result) == 2
        for step in result:
            assert step.status == OnboardingStepStatus.PENDING.value
            assert step.user_id == user_id
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_steps_skips_existing(self):
        """initialize_user() skips steps that already exist."""
        svc = OnboardingService()
        svc.register_steps("profile", "email_verify", "first_project")
        session = AsyncMock()
        user_id = uuid.uuid4()

        with patch.object(svc, "_get_existing_keys", new_callable=AsyncMock) as mock_existing:
            mock_existing.return_value = {"profile"}  # profile already exists

            result = await svc.initialize_user(session, user_id)

        # Only email_verify and first_project should be created
        assert len(result) == 2
        step_keys = [s.step_key for s in result]
        assert "profile" not in step_keys
        assert "email_verify" in step_keys
        assert "first_project" in step_keys

    @pytest.mark.asyncio
    async def test_initialize_steps_all_existing_no_commit(self):
        """When all steps exist, no commit is made."""
        svc = OnboardingService()
        svc._registered_steps = ["profile", "email_verify"]
        session = AsyncMock()
        user_id = uuid.uuid4()

        with patch.object(svc, "_get_existing_keys", new_callable=AsyncMock) as mock_existing:
            mock_existing.return_value = {"profile", "email_verify"}

            result = await svc.initialize_user(session, user_id)

        assert len(result) == 0
        session.commit.assert_not_called()


class TestCompleteStep:
    """Tests for complete_step."""

    @pytest.mark.asyncio
    async def test_complete_step_marks_as_completed(self):
        """complete_step() marks a step as completed."""
        svc = OnboardingService()
        session = AsyncMock()
        user_id = uuid.uuid4()

        # Mock the update to return a row
        mock_row = MagicMock()
        mock_row.status = OnboardingStepStatus.COMPLETED.value
        mock_row.step_key = "profile"
        mock_row.user_id = user_id
        mock_row.completed_at = MagicMock()
        mock_row.id = uuid.uuid4()
        mock_row.created_at = MagicMock()
        mock_row.updated_at = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_row
        session.execute = AsyncMock(return_value=mock_result)

        result = await svc.complete_step(session, user_id, "profile")

        assert result is not None
        assert result.status == OnboardingStepStatus.COMPLETED.value
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_step_nonexistent_returns_none(self):
        """complete_step() returns None for nonexistent step."""
        svc = OnboardingService()
        session = AsyncMock()
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await svc.complete_step(session, user_id, "nonexistent")

        assert result is None


class TestSkipStep:
    """Tests for skip_step."""

    @pytest.mark.asyncio
    async def test_skip_step_marks_as_skipped(self):
        """skip_step() marks a step as skipped."""
        svc = OnboardingService()
        session = AsyncMock()
        user_id = uuid.uuid4()

        mock_row = MagicMock()
        mock_row.status = OnboardingStepStatus.SKIPPED.value
        mock_row.step_key = "email_verify"
        mock_row.user_id = user_id
        mock_row.completed_at = None
        mock_row.id = uuid.uuid4()
        mock_row.created_at = MagicMock()
        mock_row.updated_at = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_row
        session.execute = AsyncMock(return_value=mock_result)

        result = await svc.skip_step(session, user_id, "email_verify")

        assert result is not None
        assert result.status == OnboardingStepStatus.SKIPPED.value
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_skip_step_nonexistent_returns_none(self):
        """skip_step() returns None for nonexistent step."""
        svc = OnboardingService()
        session = AsyncMock()
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await svc.skip_step(session, user_id, "nonexistent")

        assert result is None


class TestGetProgress:
    """Tests for get_progress."""

    @pytest.mark.asyncio
    async def test_get_progress_computes_percentage_correctly(self):
        """get_progress() computes percentage from completed + skipped / total."""
        svc = OnboardingService()
        svc.register_steps("profile", "email_verify", "first_project")
        session = AsyncMock()
        user_id = uuid.uuid4()

        # Create mock steps: 1 completed, 1 skipped, 1 pending
        def make_step(key, status):
            s = MagicMock()
            s.step_key = key
            s.status = status
            s.user_id = user_id
            s.completed_at = MagicMock()
            s.id = uuid.uuid4()
            s.created_at = MagicMock()
            s.updated_at = MagicMock()
            return s

        steps = [
            make_step("profile", OnboardingStepStatus.COMPLETED.value),
            make_step("email_verify", OnboardingStepStatus.SKIPPED.value),
            make_step("first_project", OnboardingStepStatus.PENDING.value),
        ]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = steps
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        progress = await svc.get_progress(session, user_id)

        assert progress.total_steps == 3
        assert progress.completed_steps == 1
        assert progress.skipped_steps == 1
        # (1 completed + 1 skipped) / 3 total = 66.7%
        assert progress.percentage == pytest.approx(66.7, abs=0.1)

    @pytest.mark.asyncio
    async def test_get_progress_all_completed(self):
        """When all steps are completed, percentage is 100%."""
        svc = OnboardingService()
        svc._registered_steps = ["profile", "email_verify"]
        session = AsyncMock()
        user_id = uuid.uuid4()

        def make_step(key, status):
            s = MagicMock()
            s.step_key = key
            s.status = status
            s.user_id = user_id
            s.completed_at = MagicMock()
            s.id = uuid.uuid4()
            s.created_at = MagicMock()
            s.updated_at = MagicMock()
            return s

        steps = [
            make_step("profile", OnboardingStepStatus.COMPLETED.value),
            make_step("email_verify", OnboardingStepStatus.COMPLETED.value),
        ]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = steps
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        progress = await svc.get_progress(session, user_id)

        assert progress.percentage == 100.0

    @pytest.mark.asyncio
    async def test_get_progress_none_completed(self):
        """When no steps are completed or skipped, percentage is 0%."""
        svc = OnboardingService()
        svc.register_steps("profile", "email_verify")
        session = AsyncMock()
        user_id = uuid.uuid4()

        def make_step(key, status):
            s = MagicMock()
            s.step_key = key
            s.status = status
            s.user_id = user_id
            s.completed_at = None
            s.id = uuid.uuid4()
            s.created_at = MagicMock()
            s.updated_at = MagicMock()
            return s

        steps = [
            make_step("profile", OnboardingStepStatus.PENDING.value),
            make_step("email_verify", OnboardingStepStatus.PENDING.value),
        ]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = steps
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        progress = await svc.get_progress(session, user_id)

        assert progress.percentage == 0.0

    @pytest.mark.asyncio
    async def test_get_progress_no_registered_steps(self):
        """When no steps are registered, percentage is 0.0."""
        svc = OnboardingService()
        # Override registered steps to empty
        svc._registered_steps = []
        session = AsyncMock()
        user_id = uuid.uuid4()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        progress = await svc.get_progress(session, user_id)

        assert progress.total_steps == 0
        assert progress.percentage == 0.0


class TestModuleLevelSingleton:
    """Tests for the module-level onboarding singleton."""

    def test_onboarding_is_onboarding_service_instance(self):
        """The module-level onboarding is an OnboardingService instance."""
        assert isinstance(onboarding, OnboardingService)

    def test_singleton_has_default_steps(self):
        """The singleton has the default steps registered."""
        steps = onboarding.registered_steps
        assert "profile" in steps
        assert "email_verify" in steps
        assert "first_project" in steps
