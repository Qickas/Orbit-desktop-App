"""Simple bootstrap script for Orbit Core."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from orbit_core import AIRouter, BootManager, IdentityEngine, MemoryEngine


def main() -> None:
    identity = IdentityEngine.default_identity()
    memory = MemoryEngine()
    router = AIRouter(default_provider="local-dev")
    boot_manager = BootManager(identity=identity, memory=memory, router=router)

    summary = boot_manager.boot()
    print("Orbit boot complete")
    print(summary)


if __name__ == "__main__":
    main()
