from orbit_core import ChatResponse, ConversationPipeline, MemoryV2


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[list[dict[str, str]], str | None]] = []

    def chat(self, messages, *, system=None):
        self.calls.append(([message.to_dict() for message in messages], system))
        return ChatResponse(content="Svar från Orbit", model="test-model")


def test_pipeline_sends_history_and_records_both_sides() -> None:
    provider = FakeProvider()
    memory = MemoryV2()
    pipeline = ConversationPipeline(provider=provider, memory=memory)

    first = pipeline.respond("Första frågan")
    second = pipeline.respond("Minns du frågan?")

    assert first.content == "Svar från Orbit"
    assert second.content == "Svar från Orbit"
    messages, system = provider.calls[1]
    assert system is not None
    assert [message["role"] for message in messages] == [
        "user",
        "assistant",
        "user",
    ]
    assert memory.count(kind="conversation") == 4
