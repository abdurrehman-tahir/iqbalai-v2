"""Framework notification tests — T-097 (Flow 4 §3.5, ARCH §9.21/§9).

Covers: 4-language templates with no ``__TODO__`` (Acceptance #5), the dispatcher deriving
the reused namespace from the template-key prefix (Acceptance #1/#3), Platform-Admin
fan-out for research-complete + SLA reminder/escalation (Acceptance #1/#2), student
version-available recipient resolution across tenants (Acceptance #3), and best-effort NATS
publishing (Acceptance #4).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.features.exam_frameworks import notifications as notif
from app.features.exam_frameworks.models import (
    ExamFramework,
    FrameworkStatus,
    SelectionStatus,
    SelectionTenantType,
    StudentFrameworkSelection,
)
from app.infrastructure.notifications.templates.framework import (
    FRAMEWORK_TEMPLATES,
    SUPPORTED_LOCALES,
    render_framework_template,
)


def _framework() -> ExamFramework:
    now = datetime.now(timezone.utc)
    fw = ExamFramework(
        id="fw-1",
        name="Matric Punjab — Physics",
        exam_target="Matric Punjab Board — Physics",
        subject_slug="physics",
        region="Punjab",
        target_grade_range=[9, 10],
        language="en",
        status=FrameworkStatus.PUBLISHED,
        created_by="admin-1",
    )
    fw.created_at = now
    fw.updated_at = now
    return fw


# --- templates (Acceptance #5) -------------------------------------------------


def test_every_template_has_all_four_locales_without_todo() -> None:
    assert SUPPORTED_LOCALES == frozenset({"en", "ur", "sd", "ps"})
    for template_key, variants in FRAMEWORK_TEMPLATES.items():
        for locale in SUPPORTED_LOCALES:
            fields = variants["default"][locale]
            assert fields["title"] and fields["body"], f"{template_key}/{locale} empty"
            assert "__TODO__" not in fields["title"]
            assert "__TODO__" not in fields["body"]


def test_render_fills_placeholders() -> None:
    rendered = render_framework_template(
        "self_study.framework_version_available",
        locale="en",
        params={"framework_name": "Matric Punjab", "version": "2"},
    )
    assert "Matric Punjab" in rendered["body"]
    assert "v2" in rendered["body"]


def test_render_falls_back_to_default_locale() -> None:
    rendered = render_framework_template(
        "system.framework_pending_approval",
        locale="fr",  # unsupported -> English fallback
        params={"framework_name": "X"},
    )
    assert (
        rendered["title"]
        == FRAMEWORK_TEMPLATES["system.framework_pending_approval"]["default"]["en"]["title"]
    )


# --- dispatcher namespace derivation -------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_derives_namespace_from_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.notifications import framework as dispatcher

    calls: list[dict[str, Any]] = []

    async def _fake_publish(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(dispatcher, "publish_notification", _fake_publish)

    await dispatcher.notify_framework_event(
        session=None,  # type: ignore[arg-type]
        template_key="system.framework_pending_approval",
        recipient_user_id="auth-admin",
        params={"framework_name": "X"},
    )
    await dispatcher.notify_framework_event(
        session=None,  # type: ignore[arg-type]
        template_key="self_study.framework_version_available",
        recipient_user_id="auth-stu",
        params={"framework_name": "X", "version": "2"},
    )

    assert calls[0]["feature_namespace"] == "system"
    assert calls[1]["feature_namespace"] == "self_study"


# --- Platform-Admin fan-out (Acceptance #1/#2) ---------------------------------


class _FakeUser:
    def __init__(self, authentik_id: str, language_preference: str = "en") -> None:
        self.authentik_id = authentik_id
        self.language_preference = language_preference


class _FakeUserRepo:
    admins: list[_FakeUser] = []
    by_id: dict[str, _FakeUser] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_platform_admins(self) -> list[_FakeUser]:
        return self.admins

    async def get_by_id(self, user_id: str) -> _FakeUser | None:
        return self.by_id.get(user_id)


@pytest.mark.asyncio
async def test_notify_platform_admins_fans_out(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.admins = [_FakeUser("auth-a"), _FakeUser("auth-b")]
    monkeypatch.setattr(notif, "UserRepository", _FakeUserRepo)

    fired: list[dict[str, Any]] = []

    async def _fake_notify(**kwargs: Any) -> None:
        fired.append(kwargs)

    monkeypatch.setattr(notif, "notify_framework_event", _fake_notify)

    await notif.notify_platform_admins(
        session=None,  # type: ignore[arg-type]
        template_key="system.framework_approval_reminder",
        framework=_framework(),
        extra_params={"days": "7"},
    )

    assert {c["recipient_user_id"] for c in fired} == {"auth-a", "auth-b"}
    assert all(c["template_key"] == "system.framework_approval_reminder" for c in fired)
    assert fired[0]["params"]["days"] == "7"


# --- student version-available recipients (Acceptance #3) ----------------------


class _FakeStudentRepo:
    selections: list[StudentFrameworkSelection] = []

    def __init__(self, session: Any) -> None:
        pass

    async def list_active_selections_pinned_below(
        self, framework_id: str, version: int
    ) -> list[StudentFrameworkSelection]:
        return [s for s in self.selections if s.pinned_version < version]


class _FakeIndependentRepo:
    by_id: dict[str, _FakeUser] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, user_id: str) -> _FakeUser | None:
        return self.by_id.get(user_id)


def _selection(**overrides: Any) -> StudentFrameworkSelection:
    now = datetime.now(timezone.utc)
    fields: dict[str, Any] = {
        "id": "sel-1",
        "tenant_type": SelectionTenantType.SCHOOL,
        "student_user_id": "stu-1",
        "framework_id": "fw-1",
        "pinned_version": 1,
        "status": SelectionStatus.ACTIVE,
        "selected_at": now,
    }
    fields.update(overrides)
    return StudentFrameworkSelection(**fields)


@pytest.mark.asyncio
async def test_notify_version_available_resolves_recipients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeStudentRepo.selections = [
        _selection(id="s1", tenant_type=SelectionTenantType.SCHOOL, student_user_id="stu-1"),
        _selection(id="s2", tenant_type=SelectionTenantType.INDEPENDENT, student_user_id="ind-1"),
    ]
    _FakeUserRepo.by_id = {"stu-1": _FakeUser("auth-school")}
    _FakeIndependentRepo.by_id = {"ind-1": _FakeUser("auth-indep", language_preference="ur")}

    monkeypatch.setattr(notif, "StudentFrameworkRepository", _FakeStudentRepo)
    monkeypatch.setattr(notif, "UserRepository", _FakeUserRepo)
    monkeypatch.setattr(notif, "IndependentUserRepository", _FakeIndependentRepo)

    fired: list[dict[str, Any]] = []

    async def _fake_notify(**kwargs: Any) -> None:
        fired.append(kwargs)

    monkeypatch.setattr(notif, "notify_framework_event", _fake_notify)

    await notif.notify_version_available(
        session=None,  # type: ignore[arg-type]
        framework=_framework(),
        new_version=2,
    )

    recipients = {c["recipient_user_id"]: c["locale"] for c in fired}
    assert recipients == {"auth-school": "en", "auth-indep": "ur"}
    assert all(c["template_key"] == "self_study.framework_version_available" for c in fired)


@pytest.mark.asyncio
async def test_notify_helpers_are_best_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    # A repo failure must be swallowed (post-commit side effect must not break lifecycle).
    class _Boom:
        def __init__(self, session: Any) -> None:
            pass

        async def list_platform_admins(self) -> list[_FakeUser]:
            raise RuntimeError("db down")

    monkeypatch.setattr(notif, "UserRepository", _Boom)
    # Should not raise.
    await notif.notify_platform_admins(
        session=None,  # type: ignore[arg-type]
        template_key="system.framework_pending_approval",
        framework=_framework(),
    )


# --- NATS best-effort (Acceptance #4) ------------------------------------------


@pytest.mark.asyncio
async def test_publish_framework_event_swallows_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.infrastructure.events.publisher as publisher
    from app.infrastructure.events import exam_frameworks as events

    async def _boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("nats down")

    monkeypatch.setattr(publisher, "publish", _boom)
    # Best-effort: must not raise even though publish blows up.
    await events.publish_framework_event(event_type="framework.published", payload={"a": 1})
