from orbit_core.continuity_runtime import ContinuityRuntime


def test_continuity_runtime_survives_restart(tmp_path):
    memory_path = tmp_path / "continuity-memory.json"

    first = ContinuityRuntime.create(memory_path=memory_path)

    first.learn(
        "Orbit owns the identity. Models provide intelligence.",
        source="constitution",
        confidence=1.0,
        importance=1.0,
    )

    assert first.identity.name == "Orbit"
    assert first.memory.count(kind="learning") == 1

    del first

    second = ContinuityRuntime.create(memory_path=memory_path)

    results = second.recall_learning("owns the identity")

    assert len(results) == 1
    assert results[0].content == (
        "Orbit owns the identity. Models provide intelligence."
    )
    assert results[0].source == "constitution"
    assert second.memory.count(kind="learning") == 1


def test_continuity_summary_reports_identity_and_learning(tmp_path):
    memory_path = tmp_path / "continuity-memory.json"

    runtime = ContinuityRuntime.create(memory_path=memory_path)

    runtime.learn(
        "Explore freely. Believe carefully.",
        source="constitution",
        confidence=1.0,
        importance=1.0,
    )

    summary = runtime.continuity_summary()

    assert "Orbit" in summary
    assert "0.1.0" in summary
    assert "learned=1" in summary