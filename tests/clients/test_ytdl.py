from unittest.mock import Mock, patch

import pytest

from spots_cli.clients.ytdl import YtDlpClient

MODULE = "spots_cli.clients.ytdl"


@pytest.fixture
def secrets():
    secrets = Mock()
    secrets.read.return_value = None
    return secrets


def make_client(secrets, *, browser=None, runtimes=None, extra_options=None):
    runtimes = {"bun": {"path": "/bin/bun"}} if runtimes is None else runtimes
    with (
        patch(f"{MODULE}.YoutubeDL") as ydl,
        patch(f"{MODULE}.detect_browser", return_value=browser),
        patch(f"{MODULE}.detect_js_runtimes", return_value=runtimes),
    ):
        kwargs = {"secrets": secrets}
        if extra_options is not None:
            kwargs["extra_options"] = extra_options
        client = YtDlpClient(**kwargs)
    return client, ydl


def test_uses_detected_js_runtimes(secrets):
    runtimes = {"deno": {"path": "/usr/bin/deno"}}
    client, ydl = make_client(secrets, runtimes=runtimes)

    assert client.options["js_runtimes"] == runtimes
    assert client.options["remote_components"] == {"ejs:github"}
    ydl.assert_called_once_with(client.options)


def test_warns_when_no_js_runtime(secrets, caplog):
    make_client(secrets, runtimes={})

    assert "No JavaScript runtime found" in caplog.text


def test_default_options(secrets):
    client, _ = make_client(secrets)

    assert client.options["format"] == "bestaudio/best"
    assert client.options["noplaylist"] is True
    assert client.options["quiet"] is True
    assert client.options["cachedir"].endswith("yt_cache")


def test_no_browser_means_no_cookies(secrets):
    client, _ = make_client(secrets, browser=None)

    assert "cookiesfrombrowser" not in client.options
    assert "cookiefile" not in client.options


def test_browser_cookies_and_cookie_file(secrets):
    secrets.read.return_value = "/tmp/cookies.txt"
    client, _ = make_client(secrets, browser=("firefox",))

    assert client.options["cookiesfrombrowser"] == ("firefox",)
    assert client.options["cookiefile"] == "/tmp/cookies.txt"
    secrets.read.assert_called_with(key="YOUTUBE_COOKIES_PATH")


def test_extra_options_override_defaults(secrets):
    client, _ = make_client(secrets, extra_options={"format": "worst", "quiet": False})

    assert client.options["format"] == "worst"
    assert client.options["quiet"] is False
    assert client.options["noplaylist"] is True


def test_options_setter_merges_and_rebuilds_client(secrets):
    client, _ = make_client(secrets)
    before = dict(client.options)

    with patch(f"{MODULE}.YoutubeDL") as ydl:
        client.options = {"outtmpl": "/tmp/x.%(ext)s"}

    assert client.options == before | {"outtmpl": "/tmp/x.%(ext)s"}
    ydl.assert_called_once_with(client.options)


def test_reset_drops_call_options_but_keeps_cookies_and_extras(secrets):
    """A reset after a download must not lose the session the formats came from."""
    client, _ = make_client(
        secrets, browser=("firefox",), extra_options={"custom": "kept"}
    )

    with patch(f"{MODULE}.YoutubeDL"):
        client.options = {"outtmpl": "/tmp/x.%(ext)s", "format": "137+bestaudio"}
        client.reset_options()

    assert client.options["outtmpl"] == "%(title)s.%(ext)s"
    assert client.options["format"] == "bestaudio/best"
    assert client.options["cookiesfrombrowser"] == ("firefox",)
    assert client.options["custom"] == "kept"
