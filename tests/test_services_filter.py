from unittest.mock import patch

import pytest

from server import (
    app,
    cache,
    filter_services_for_user,
    get_authentik_base_url,
    is_service_accessible_via_authentik,
    user_has_service_access,
)


@pytest.fixture(autouse=True)
def clear_cache():
    with app.app_context():
        cache.clear()
    yield
    with app.app_context():
        cache.clear()


def test_get_authentik_base_url_from_metadata(monkeypatch):
    monkeypatch.delenv("AUTHENTIK_API_URL", raising=False)
    monkeypatch.delenv("AUTHENTIK_URL", raising=False)
    monkeypatch.setenv(
        "AUTHENTIK_METADATA_URL",
        "https://auth.woodburn.au/application/o/woodburn/.well-known/openid-configuration",
    )
    assert get_authentik_base_url() == "https://auth.woodburn.au"


def test_get_authentik_base_url_explicit(monkeypatch):
    monkeypatch.setenv("AUTHENTIK_API_URL", "https://custom-auth.example.com/")
    assert get_authentik_base_url() == "https://custom-auth.example.com"


def test_is_service_accessible_via_authentik():
    authentik_apps = [
        {
            "name": "Woodburn Cloud",
            "slug": "cloud",
            "launch_url": "https://cloud.woodburn.au",
        },
        {
            "name": "Vaultwarden",
            "slug": "vaultwarden",
            "meta_launch_url": "https://bw.woodburn.au",
        },
        {
            "name": "Kitchen Owl",
            "slug": "kitchen-owl",
            "launch_url": "https://shopping.woodburn.au",
        },
    ]

    # Matching by exact ID / slug
    assert is_service_accessible_via_authentik({"id": "cloud"}, authentik_apps) is True

    # Matching case-insensitive and underscore to hyphen
    assert (
        is_service_accessible_via_authentik({"id": "kitchen_owl"}, authentik_apps)
        is True
    )

    # Matching by launch URL host
    assert (
        is_service_accessible_via_authentik(
            {"id": "pw_manager", "url": "https://bw.woodburn.au/login"}, authentik_apps
        )
        is True
    )

    # Matching by name
    assert (
        is_service_accessible_via_authentik(
            {"id": "unknown_id", "name": "Woodburn Cloud"}, authentik_apps
        )
        is True
    )

    # Matching explicit authentik_slug
    assert (
        is_service_accessible_via_authentik(
            {"id": "custom", "authentik_slug": "vaultwarden"}, authentik_apps
        )
        is True
    )

    # Unrestricted bypass
    assert (
        is_service_accessible_via_authentik(
            {"id": "random_service", "unrestricted": True}, authentik_apps
        )
        is True
    )
    assert (
        is_service_accessible_via_authentik(
            {"id": "random_service", "authentik_slug": False}, authentik_apps
        )
        is True
    )

    # Not in authentik apps
    assert (
        is_service_accessible_via_authentik(
            {"id": "immich", "name": "Immich", "url": "https://immich.woodburn.au"},
            authentik_apps,
        )
        is False
    )


def test_filter_services_unauthenticated():
    services = {
        "external": [{"id": "web", "name": "Website"}],
        "internal": [{"id": "cloud", "name": "Cloud"}],
    }
    filtered = filter_services_for_user(services, user=None, access_token=None)
    assert filtered["external"] == [{"id": "web", "name": "Website"}]
    assert filtered["internal"] == []


def test_filter_services_authenticated_with_authentik_apps():
    services = {
        "external": [{"id": "web", "name": "Website"}],
        "internal": [
            {"id": "cloud", "name": "Cloud", "url": "https://cloud.woodburn.au"},
            {"id": "immich", "name": "Immich", "url": "https://immich.woodburn.au"},
        ],
    }
    user = {"sub": "user-123", "preferred_username": "nathan"}

    with patch("server.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "results": [
                {
                    "name": "Cloud",
                    "slug": "cloud",
                    "launch_url": "https://cloud.woodburn.au",
                }
            ],
            "pagination": {"next": None},
        }

        filtered = filter_services_for_user(
            services, user=user, access_token="mock_token"
        )
        assert len(filtered["internal"]) == 1
        assert filtered["internal"][0]["id"] == "cloud"


def test_filter_services_authentik_api_failure_fail_open(monkeypatch):
    monkeypatch.setenv("AUTHENTIK_FILTER_FAIL_CLOSED", "false")
    services = {
        "external": [{"id": "web"}],
        "internal": [{"id": "cloud"}, {"id": "immich"}],
    }
    user = {"sub": "user-123"}

    with patch("server.requests.get") as mock_get:
        mock_get.return_value.status_code = 403
        mock_get.return_value.text = "Forbidden"

        filtered = filter_services_for_user(
            services, user=user, access_token="mock_token"
        )
        # Fail-open should preserve all internal services
        assert len(filtered["internal"]) == 2


def test_filter_services_authentik_api_failure_fail_closed(monkeypatch):
    monkeypatch.setenv("AUTHENTIK_FILTER_FAIL_CLOSED", "true")
    services = {
        "external": [{"id": "web"}],
        "internal": [{"id": "cloud"}, {"id": "immich"}],
    }
    user = {"sub": "user-123"}

    with patch("server.requests.get") as mock_get:
        mock_get.return_value.status_code = 403
        mock_get.return_value.text = "Forbidden"

        filtered = filter_services_for_user(
            services, user=user, access_token="mock_token"
        )
        # Fail-closed should hide internal services
        assert len(filtered["internal"]) == 0


def test_user_has_service_access():
    user = {"sub": "user-123"}
    with patch("server.get_user_authentik_apps") as mock_apps:
        mock_apps.return_value = [{"slug": "cloud", "name": "Woodburn Cloud"}]
        assert user_has_service_access("cloud", user, "token") is True
        assert user_has_service_access("immich", user, "token") is False


def test_index_route_filtering():
    test_client = app.test_client()

    # Unauthenticated visitor (with auth_checked set):
    with test_client.session_transaction() as sess:
        sess["auth_checked"] = True

    res = test_client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Services" in html
    assert "Internal Services" not in html


def test_index_route_skeleton_loading_when_uncached():
    test_client = app.test_client()

    with test_client.session_transaction() as sess:
        sess["user"] = {"sub": "user-456", "preferred_username": "tester"}
        sess["access_token"] = "valid_token"
        sess["auth_checked"] = True

    # No cache present -> should render skeleton loading state immediately without making ANY external requests!
    with patch("server.requests.get") as mock_get:
        res = test_client.get("/")
        assert res.status_code == 200
        assert mock_get.call_count == 0  # Zero network calls on page load!
        html = res.get_data(as_text=True)
        assert "Internal Services" in html
        assert 'data-loading="true"' in html
        assert "skeleton-card" in html


def test_index_route_renders_cards_when_cached():
    test_client = app.test_client()

    with test_client.session_transaction() as sess:
        sess["user"] = {"sub": "user-456", "preferred_username": "tester"}
        sess["access_token"] = "valid_token"
        sess["auth_checked"] = True

    # Pre-populate cache
    cache.set("authentik_apps_user-456", [{"slug": "cloud", "name": "Woodburn Cloud"}])

    res = test_client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Internal Services" in html
    assert 'data-loading="false"' in html
    assert 'id="cloud"' in html
    assert "skeleton-card" not in html


def test_api_internal_services():
    test_client = app.test_client()

    # Unauthenticated
    res = test_client.get("/api/v1/internal_services")
    assert res.status_code == 401

    # Authenticated
    with test_client.session_transaction() as sess:
        sess["user"] = {"sub": "user-api", "preferred_username": "apiuser"}
        sess["access_token"] = "valid_token"

    with patch("server.get_user_authentik_apps") as mock_apps:
        mock_apps.return_value = [{"slug": "cloud", "name": "Woodburn Cloud"}]

        res = test_client.get("/api/v1/internal_services")
        assert res.status_code == 200
        data = res.get_json()
        assert "services" in data
        assert len(data["services"]) == 1
        assert data["services"][0]["id"] == "cloud"


def test_index_route_cli_filtering():
    test_client = app.test_client()

    with test_client.session_transaction() as sess:
        sess["user"] = {"sub": "user-cli", "preferred_username": "cliuser"}
        sess["access_token"] = "valid_token"

    with patch("server.get_user_authentik_apps") as mock_apps:
        mock_apps.return_value = [{"slug": "cloud", "name": "Woodburn Cloud"}]

        res = test_client.get("/?format=ascii")
        assert res.status_code == 200
        text = res.get_data(as_text=True)
        assert "INTERNAL SERVICES" in text
        assert "Woodburn Cloud" in text
        assert "Vaultwarden" not in text
        assert "Immich" not in text


def test_api_quota_endpoint_permissions():
    test_client = app.test_client()

    # 1. Unauthenticated -> 401
    res = test_client.get("/api/v1/cloud_quota")
    assert res.status_code == 401

    # 2. Authenticated but forbidden -> 403
    with test_client.session_transaction() as sess:
        sess["user"] = {"sub": "user-quota", "preferred_username": "quotauser"}
        sess["access_token"] = "valid_token"

    with patch("server.get_user_authentik_apps") as mock_apps:
        # Only has access to Vaultwarden, not cloud
        mock_apps.return_value = [{"slug": "vaultwarden", "name": "Vaultwarden"}]

        res = test_client.get("/api/v1/cloud_quota")
        assert res.status_code == 403

    # 3. Authenticated and allowed -> calls getUserQuota
    with (
        patch("server.get_user_authentik_apps") as mock_apps,
        patch("server.getUserQuota") as mock_quota,
    ):
        mock_apps.return_value = [{"slug": "cloud", "name": "Woodburn Cloud"}]
        mock_quota.return_value = {"used": 1, "total": 10, "percentage": "10"}

        res = test_client.get("/api/v1/cloud_quota")
        assert res.status_code == 200
        assert res.json["total"] == 10


def test_logout_clears_cache_and_session():
    test_client = app.test_client()

    with test_client.session_transaction() as sess:
        sess["user"] = {"sub": "user-logout", "preferred_username": "logoutuser"}
        sess["access_token"] = "token123"

    cache.set("authentik_apps_user-logout", [{"slug": "cloud"}])
    assert cache.get("authentik_apps_user-logout") is not None

    res = test_client.get("/logout")
    assert res.status_code == 302
    assert cache.get("authentik_apps_user-logout") is None

    with test_client.session_transaction() as sess:
        assert "user" not in sess
        assert "access_token" not in sess


def test_sanitize_userinfo():
    from server import sanitize_userinfo

    bloated = {
        "sub": "user_id",
        "preferred_username": "nathan",
        "name": "Nathan Woodburn",
        "email": "nathan@example.com",
        "groups": ["admin"],
        "avatar": "data:image/png;base64," + "A" * 3000,
        "raw_attributes": {"foo": "bar" * 100},
    }
    sanitized = sanitize_userinfo(bloated)
    assert sanitized["sub"] == "user_id"
    assert sanitized["preferred_username"] == "nathan"
    assert "avatar" not in sanitized
    assert "raw_attributes" not in sanitized


def test_session_token_storage_keeps_cookie_tiny():
    from server import get_session_access_token, store_session_access_token

    test_client = app.test_client()
    huge_token = "jwt_header." + "jwt_payload_" * 200 + ".signature"

    with test_client.session_transaction() as sess:
        sess["user"] = {"sub": "u1", "preferred_username": "tester"}

    with app.test_request_context():
        # Store large token in session
        from flask import session as flask_session

        flask_session["sid"] = "test_sid"
        store_session_access_token(huge_token)
        # Ensure it is in server-side cache and NOT in cookie dict
        assert "access_token" not in flask_session
        assert get_session_access_token() == huge_token


def test_authentik_api_timeout_cooldown(monkeypatch):
    from server import get_user_authentik_apps

    monkeypatch.setenv("AUTHENTIK_API_URL", "https://auth.woodburn.au")

    with patch("server.requests.get") as mock_get:
        import requests

        mock_get.side_effect = requests.ReadTimeout("Read timed out")

        # First attempt times out
        result1 = get_user_authentik_apps("test_token", user_sub="timeout_user")
        assert result1 is None
        assert mock_get.call_count == 1

        # Second attempt should hit the cooldown cache without re-invoking requests.get
        result2 = get_user_authentik_apps("test_token", user_sub="timeout_user")
        assert result2 is None
        assert mock_get.call_count == 1  # Not called again!


def test_get_authentik_internal_url(monkeypatch):
    monkeypatch.delenv("AUTHENTIK_API_URL", raising=False)
    monkeypatch.setenv("AUTHENTIK_INTERNAL_URL", "http://authentik-server:9000/")
    assert get_authentik_base_url() == "http://authentik-server:9000"


def test_load_services_in_memory_caching():
    from server import load_services

    data1 = load_services()
    data2 = load_services()
    assert data1 is data2  # Same memory reference


def test_service_images_cache_control_headers():
    test_client = app.test_client()

    res = test_client.get("/favicon.png")
    assert res.status_code == 200
    assert "public, max-age=" in res.headers.get("Cache-Control", "")

    res_svc = test_client.get("/services/external/git.png")
    assert res_svc.status_code == 200
    assert "public, max-age=" in res_svc.headers.get("Cache-Control", "")


def test_stats_api_server_side_caching():
    test_client = app.test_client()

    with test_client.session_transaction() as sess:
        sess["user"] = {
            "sub": "user-stats-cache",
            "preferred_username": "cacheuser",
            "email": "cache@example.com",
        }
        sess["access_token"] = "valid_token"

    with (
        patch("server.get_user_authentik_apps") as mock_apps,
        patch("server.getUserQuota") as mock_quota,
    ):
        mock_apps.return_value = [{"slug": "cloud", "name": "Woodburn Cloud"}]
        mock_quota.return_value = {"used": 2, "total": 20, "percentage": "10"}

        # First call hits getUserQuota
        res1 = test_client.get("/api/v1/cloud_quota")
        assert res1.status_code == 200
        assert mock_quota.call_count == 1

        # Second call returns from Flask-Caching without calling getUserQuota
        res2 = test_client.get("/api/v1/cloud_quota")
        assert res2.status_code == 200
        assert mock_quota.call_count == 1
        assert res2.json["total"] == 20
