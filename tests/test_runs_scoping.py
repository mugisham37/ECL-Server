"""Tests for 3-tier run visibility scoping."""

import pytest
from sqlalchemy import and_

from app.core.enums import UserRole
from app.modules.runs.models import Run
from app.modules.runs.service import get_run_scope_filter


class _FakeUser:
    def __init__(self, user_id: str, is_platform_admin: bool = False):
        self.id = user_id
        self.is_platform_admin = is_platform_admin


class _FakeMembership:
    def __init__(self, role: str):
        self.role = role


def test_platform_admin_scopes_to_tenant():
    user = _FakeUser("u1", is_platform_admin=True)
    scope = get_run_scope_filter(user, "tenant-a", None)
    assert str(scope) == str(Run.tenant_id == "tenant-a")


def test_tenant_admin_sees_all_tenant_runs():
    user = _FakeUser("u1")
    membership = _FakeMembership(UserRole.ADMINISTRATOR.value)
    scope = get_run_scope_filter(user, "tenant-a", membership)
    assert str(scope) == str(Run.tenant_id == "tenant-a")


def test_analyst_sees_own_runs_only():
    user = _FakeUser("u1")
    membership = _FakeMembership(UserRole.ANALYST.value)
    scope = get_run_scope_filter(user, "tenant-a", membership)
    expected = and_(Run.tenant_id == "tenant-a", Run.created_by_user_id == "u1")
    assert str(scope) == str(expected)


def test_reviewer_sees_own_runs_only():
    user = _FakeUser("u1")
    membership = _FakeMembership(UserRole.REVIEWER.value)
    scope = get_run_scope_filter(user, "tenant-a", membership)
    expected = and_(Run.tenant_id == "tenant-a", Run.created_by_user_id == "u1")
    assert str(scope) == str(expected)
