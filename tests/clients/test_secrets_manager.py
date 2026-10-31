from spots_cli.clients import SecretsManager


def test_read_returns_env_value(monkeypatch):
    monkeypatch.setenv("SPOTS_TEST_KEY", "value")
    assert SecretsManager.read(key="SPOTS_TEST_KEY") == "value"


def test_read_falls_back_to_alt(monkeypatch):
    monkeypatch.delenv("SPOTS_TEST_KEY", raising=False)
    assert SecretsManager.read(key="SPOTS_TEST_KEY") is None
    assert SecretsManager.read(key="SPOTS_TEST_KEY", alt="fallback") == "fallback"


def test_write_sets_env(monkeypatch):
    monkeypatch.delenv("SPOTS_TEST_KEY", raising=False)
    SecretsManager.write(key="SPOTS_TEST_KEY", value="written")
    assert SecretsManager.read(key="SPOTS_TEST_KEY") == "written"
    monkeypatch.delenv("SPOTS_TEST_KEY")
