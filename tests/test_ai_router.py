import pytest

from orbit_core import AIRouter


def test_router_builds_route_key() -> None:
    router = AIRouter(default_provider="local-dev")

    assert router.route("chat") == "local-dev:chat"


def test_router_rejects_blank_provider() -> None:
    router = AIRouter(default_provider="")

    with pytest.raises(ValueError):
        router.validate()
