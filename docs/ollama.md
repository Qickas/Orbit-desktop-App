# Ollama och terminalchat

Orbit använder Ollamas lokala HTTP-API. Providern skickar hela den begränsade
konversationshistoriken till `POST /api/chat` med `stream: false` och sparar
sedan både användarens fråga och modellens svar i Memory v2.

## Starta lokalt

1. Installera och starta Ollama.
2. Hämta en modell, till exempel `ollama pull llama3.2`.
3. Starta Orbit med `python scripts/terminal_chat.py`.

Standardadressen är `http://localhost:11434`. Den kan ändras med
`OLLAMA_BASE_URL` eller `--base-url`. Standardmodellen är `llama3.2` och kan
ändras med `OLLAMA_MODEL` eller `--model`.

## Minnet

Standardfilen är `data/memory.json`. Den skapas först när Orbit sparar sin
första minnespost. Använd `--no-persist` när du vill prova utan att spara
något på disk.

## Begränsning i denna sprint

Första versionen använder synkrona, icke-strömmande svar. Det gör pipeline och
tester enkla att lita på. Streaming och verktygsanrop kan läggas ovanpå samma
providergränssnitt i nästa sprint.
