from orbit_core import MemoryEngine


def test_memory_store_and_recall() -> None:
    memory = MemoryEngine()
    memory.store("hello", "world")

    assert memory.recall("hello") == "world"
    assert memory.count() == 1
