from orbit_core import AIRouter, BootManager, IdentityEngine, MemoryEngine


def test_boot_manager_returns_ready_summary() -> None:
    manager = BootManager(
        identity=IdentityEngine.default_identity(),
        memory=MemoryEngine(),
        router=AIRouter(default_provider="local-dev"),
    )

    summary = manager.boot()

    assert summary.status == "ready"
    assert summary.identity_name == "Orbit"
    assert summary.memory_records == 1
    assert summary.router_provider == "local-dev"
