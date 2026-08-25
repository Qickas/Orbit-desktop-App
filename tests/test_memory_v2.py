from orbit_core import MemoryV2


def test_memory_v2_searches_and_persists_records(tmp_path) -> None:
    path = tmp_path / "memory.json"
    memory = MemoryV2(path)
    memory.remember("Adrian bygger Orbit", kind="fact", metadata={"topic": "project"})
    memory.remember("Hej", kind="conversation", metadata={"role": "user"})

    restored = MemoryV2(path)

    assert restored.count() == 2
    assert restored.search("orbit")[0].kind == "fact"
    assert restored.recent(1, kind="conversation")[0].content == "Hej"
