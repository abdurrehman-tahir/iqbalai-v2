"""Unit tests for TosService — T-016 + T-019 acceptance criteria."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.features.tos.models import TosVersion
from app.features.tos.service import TosService


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


class TestTosService:
    def _svc(self, session: AsyncMock) -> TosService:
        return TosService(session)

    def _make_tos(self, version: int = 1) -> TosVersion:
        from datetime import datetime, timezone

        t = TosVersion.__new__(TosVersion)
        t.id = f"tos-v{version}"
        t.version_number = version
        t.content_md = "# ToS"
        t.language = "en"

        t.effective_at = datetime.now(timezone.utc)
        return t

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
