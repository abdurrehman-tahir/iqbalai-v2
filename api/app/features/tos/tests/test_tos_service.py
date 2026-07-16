"""Unit tests for TosService — T-016 + T-019 acceptance criteria."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.features.independent_users.service import IndependentUserService
from app.features.tos.models import TosVersion
from app.features.tos.service import TosService
from app.features.users.service import UserService


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


def _tos_version(version: int = 1) -> TosVersion:
    return TosVersion(
        id=f"tos-v{version}",
        version_number=version,
        content_md="# ToS",
        language="en",
        effective_at=datetime.now(timezone.utc),
    )


class TestTosService:
    def _svc(self, session: AsyncMock) -> TosService:
        return TosService(session)

    def _make_tos(self, version: int = 1) -> TosVersion:
        from datetime import datetime, timezone

        return TosVersion(
            id=f"tos-v{version}",
            version_number=version,
            content_md="# ToS",
            language="en",
            effective_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_publish_first_tos_sets_version_1(self, mock_session: AsyncMock) -> None:
        svc = self._svc(mock_session)
        repo_mock = AsyncMock()
        repo_mock.get_current_tos.return_value = None
        repo_mock.create_tos_version.side_effect = lambda t: t
        svc._repo = repo_mock

        result = await svc.publish_new_tos("# ToS v1", "en", "user-001")
        assert result.version_number == 1

    @pytest.mark.asyncio
    async def test_publish_second_tos_increments_version(self, mock_session: AsyncMock) -> None:
        svc = self._svc(mock_session)
        repo_mock = AsyncMock()
        repo_mock.get_current_tos.return_value = self._make_tos(version=1)
        repo_mock.create_tos_version.side_effect = lambda t: t
        svc._repo = repo_mock

        result = await svc.publish_new_tos("# ToS v2", "en", "user-001")
        assert result.version_number == 2

    @pytest.mark.asyncio
    async def test_disclaimer_too_long_raises_validation_error(
        self, mock_session: AsyncMock
    ) -> None:
        from app.core.exceptions import ValidationError

        svc = self._svc(mock_session)
        long_content = "x" * 501
        with pytest.raises(ValidationError):
            await svc.publish_new_disclaimer(long_content, "en", "user-001")

    @pytest.mark.asyncio
    async def test_check_user_accepted_current_no_tos_returns_true(
        self, mock_session: AsyncMock
    ) -> None:
        svc = self._svc(mock_session)
        repo_mock = AsyncMock()
        repo_mock.get_current_tos.return_value = None
        svc._repo = repo_mock

        result = await svc.check_user_has_accepted_current("user-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_require_tos_accepted_raises_when_not_accepted(
        self, mock_session: AsyncMock
    ) -> None:
        from app.core.exceptions import TosAcceptanceRequiredError

        svc = self._svc(mock_session)
        repo_mock = AsyncMock()
        repo_mock.get_current_tos.return_value = self._make_tos(1)
        repo_mock.has_accepted_tos.return_value = False
        svc._repo = repo_mock

        with pytest.raises(TosAcceptanceRequiredError):
            await svc.require_tos_accepted("user-001")


class TestTosTenantRouting:
    """QA E10/E11 — ToS acceptance must act on the tenant that owns the caller.

    Independent users are created into independent.users by /auth/post-login and have no
    row in school.users. The accept/decline paths sent the status change to the school
    UserService regardless, which raised NotFound — 404'ing every independent teacher and
    student at the ToS gate, the final step of their first login.
    """

    @pytest.fixture
    def routed(self, monkeypatch: pytest.MonkeyPatch) -> tuple[TosService, AsyncMock, AsyncMock]:
        async def _noop_audit(**_kwargs: object) -> None:
            return None

        monkeypatch.setattr("app.features.tos.service.audit", _noop_audit)

        school_svc = AsyncMock()
        independent_svc = AsyncMock()
        monkeypatch.setattr("app.features.tos.service.UserService", lambda _s: school_svc)
        monkeypatch.setattr(
            "app.features.tos.service.IndependentUserService", lambda _s: independent_svc
        )

        svc = TosService(AsyncMock())
        repo = AsyncMock()
        repo.get_tos_by_id.return_value = _tos_version(1)
        repo.get_current_tos.return_value = _tos_version(1)
        repo.has_accepted_tos.return_value = False
        svc._repo = repo
        return svc, school_svc, independent_svc

    def test_account_service_selects_by_tenant(self, mock_session: AsyncMock) -> None:
        svc = TosService(mock_session)
        assert isinstance(svc._account_service("independent"), IndependentUserService)
        assert isinstance(svc._account_service("school"), UserService)

    @pytest.mark.asyncio
    async def test_accept_routes_independent_user_to_independent_table(
        self, routed: tuple[TosService, AsyncMock, AsyncMock]
    ) -> None:
        svc, school_svc, independent_svc = routed

        await svc.accept_tos("indep-1", "tos-v1", None, tenant_type="independent")

        independent_svc.reactivate_on_tos_accept.assert_awaited_once_with("indep-1")
        school_svc.reactivate_on_tos_accept.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_decline_routes_independent_user_to_independent_table(
        self, routed: tuple[TosService, AsyncMock, AsyncMock]
    ) -> None:
        svc, school_svc, independent_svc = routed

        await svc.decline_tos("indep-1", None, tenant_type="independent")

        independent_svc.suspend_for_tos_decline.assert_awaited_once_with("indep-1")
        school_svc.suspend_for_tos_decline.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_school_user_still_routes_to_school_table(
        self, routed: tuple[TosService, AsyncMock, AsyncMock]
    ) -> None:
        """The default must stay school so the hierarchy flow is untouched."""
        svc, school_svc, independent_svc = routed

        await svc.accept_tos("school-1", "tos-v1", None)

        school_svc.reactivate_on_tos_accept.assert_awaited_once_with("school-1")
        independent_svc.reactivate_on_tos_accept.assert_not_awaited()
