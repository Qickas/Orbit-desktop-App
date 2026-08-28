from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_has_no_direct_core_http_or_bearer_handling() -> None:
    source = (ROOT / "src" / "main.ts").read_text(encoding="utf-8")

    assert "fetch(" not in source
    assert "Authorization" not in source
    assert "Bearer" not in source
    assert "token" not in source.lower()
    assert "@tauri-apps/api/core" in source


def test_tauri_csp_does_not_grant_webview_loopback_access() -> None:
    config = (ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")

    assert "connect-src 'self';" in config
    assert "connect-src 'self' http://127.0.0.1:8765" not in config
