from fastapi.testclient import TestClient

from backend.app.config import Settings, load_settings
from backend.app import main


def test_parent_dotenv_fallback(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (tmp_path / ".env").write_text("OPENAI_API_KEY=parent-dummy-value\n", encoding="utf-8")
    before = (tmp_path / ".env").read_bytes()
    settings = load_settings(root)
    assert settings.env_file == tmp_path / ".env"
    assert settings.openai_api_key == "parent-dummy-value"
    assert settings.api_key_configured
    assert (tmp_path / ".env").read_bytes() == before


def test_local_dotenv_preferred(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (tmp_path / ".env").write_text("OPENAI_API_KEY=parent-dummy-value\n", encoding="utf-8")
    (root / ".env").write_text("OPENAI_API_KEY=local-dummy-value\n", encoding="utf-8")
    settings = load_settings(root)
    assert settings.env_file == root / ".env"
    assert settings.openai_api_key == "local-dummy-value"


def test_incomplete_local_does_not_merge_parent(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (tmp_path / ".env").write_text("OPENAI_API_KEY=parent-dummy-value\n", encoding="utf-8")
    (root / ".env").write_text("UNRELATED_SETTING=1\n", encoding="utf-8")
    assert not load_settings(root).api_key_configured


def test_process_environment_takes_precedence(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=file-dummy-value\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "process-dummy-value")
    settings = load_settings(tmp_path)
    assert settings.openai_api_key == "process-dummy-value"


def test_missing_key_allowed_in_phase_one(tmp_path):
    root = tmp_path / "isolated" / "project"
    root.mkdir(parents=True)
    settings = load_settings(root)
    assert settings.env_file is None
    assert not settings.api_key_configured


def test_secret_not_logged_or_in_repr(tmp_path, capsys):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=secret-test-marker\n", encoding="utf-8")
    settings = load_settings(tmp_path)
    assert "secret-test-marker" not in repr(settings)
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""


def test_config_independent_of_cwd(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (root / ".env").write_text("OPENAI_API_KEY=local-dummy-value\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert load_settings(root).openai_api_key == "local-dummy-value"


def test_health_without_network_or_secret_exposure(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "load_settings", lambda: Settings(tmp_path, None, "secret-test-marker"))
    with TestClient(main.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["api_key_configured"] is True
    assert response.json()["ai_enabled"] is True
    assert response.json()["regulatory_checks"] == "not_implemented"
    assert "secret-test-marker" not in response.text
    assert "openai_api_key" not in response.text


def test_health_without_key(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "load_settings", lambda: Settings(tmp_path, None, None))
    with TestClient(main.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["api_key_configured"] is False
