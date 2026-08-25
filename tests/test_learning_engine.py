from orbit_core.learning_engine import LearningEngine
from orbit_core.memory_v2 import MemoryV2


def test_learning_survives_restart(tmp_path):
    memory_path = tmp_path / "orbit-memory.json"

    memory_first_run = MemoryV2(memory_path)
    learning_first_run = LearningEngine(memory_first_run)

    learned = learning_first_run.learn(
        "Orbit should explore freely and believe carefully.",
        source="constitution",
        confidence=1.0,
        importance=1.0,
    )

    assert learned.content == "Orbit should explore freely and believe carefully."
    assert memory_first_run.count(kind="learning") == 1

    del learning_first_run
    del memory_first_run

    memory_second_run = MemoryV2(memory_path)
    learning_second_run = LearningEngine(memory_second_run)

    results = learning_second_run.search("explore freely")

    assert len(results) == 1
    assert results[0].content == "Orbit should explore freely and believe carefully."
    assert results[0].source == "constitution"
    assert results[0].confidence == 1.0
    assert results[0].importance == 1.0