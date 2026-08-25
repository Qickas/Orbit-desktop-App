import json

import pytest

from orbit_core import ChatMessage, OllamaError, OllamaProvider


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_provider_posts_non_streaming_chat_payload() -> None:
    requests: list[object] = []

    def opener(request: object, *, timeout: float) -> FakeResponse:
        requests.append((request, timeout))
        return FakeResponse(
            {"model": "llama3.2", "message": {"role": "assistant", "content": "Hej!"}}
        )

    provider = OllamaProvider(model="llama3.2", opener=opener)

    response = provider.chat([ChatMessage("user", "Hej Orbit")], system="Var kort.")

    request, timeout = requests[0]
    payload = json.loads(request.data.decode("utf-8"))
    assert response.content == "Hej!"
    assert request.full_url == "http://localhost:11434/api/chat"
    assert timeout == 180.0
    assert payload == {
    "model": "llama3.2",
    "messages": [
        {"role": "system", "content": "Var kort."},
        {"role": "user", "content": "Hej Orbit"},
    ],
    "stream": False,
    "think": False,
    "options": {
        "num_ctx": 4096,
    },
}


def test_provider_rejects_missing_assistant_content() -> None:
    provider = OllamaProvider(opener=lambda *_args, **_kwargs: FakeResponse({}))

    with pytest.raises(OllamaError, match="no assistant message"):
        provider.chat([ChatMessage("user", "Hej")])
