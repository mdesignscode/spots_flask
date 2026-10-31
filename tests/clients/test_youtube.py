import pickle
from unittest.mock import Mock, mock_open, patch

import pytest

from spots_cli.clients import youtube
from spots_cli.clients.youtube import PICKLE_TOKEN, SCOPES, YouTubeApiClient

MODULE = "spots_cli.clients.youtube"


def bare_client(secrets_file="client_secrets.json") -> YouTubeApiClient:
    client = YouTubeApiClient.__new__(YouTubeApiClient)
    client.secrets_file = secrets_file
    return client


def creds(*, valid=True, expired=False, refresh_token=None) -> Mock:
    return Mock(valid=valid, expired=expired, refresh_token=refresh_token)


def test_constants():
    assert SCOPES == ["https://www.googleapis.com/auth/youtube.force-ssl"]
    assert PICKLE_TOKEN.endswith("spots_cli/token.pickle")


def test_init_without_client_secrets_fails():
    with patch(f"{MODULE}.exists", return_value=False):
        with pytest.raises(RuntimeError):
            YouTubeApiClient()


def test_init_builds_service():
    with (
        patch(f"{MODULE}.exists", return_value=True),
        patch.object(YouTubeApiClient, "_build_service", return_value="svc") as build,
    ):
        client = YouTubeApiClient()

    build.assert_called_once()
    assert client.service == "svc"
    assert client.secrets_file.endswith("client_secrets.json")


def test_valid_saved_token_is_reused():
    saved = creds()
    with (
        patch(f"{MODULE}.os.path.exists", return_value=True),
        patch("builtins.open", mock_open()),
        patch(f"{MODULE}.pickle.load", return_value=saved),
        patch(f"{MODULE}.InstalledAppFlow") as flow,
        patch(f"{MODULE}.build") as build,
    ):
        bare_client()._build_service()

    flow.from_client_secrets_file.assert_not_called()
    build.assert_called_once_with("youtube", "v3", credentials=saved)


def test_expired_token_is_refreshed_and_saved():
    saved = creds(valid=False, expired=True, refresh_token="r")
    with (
        patch(f"{MODULE}.os.path.exists", return_value=True),
        patch("builtins.open", mock_open()),
        patch(f"{MODULE}.pickle.load", return_value=saved),
        patch(f"{MODULE}.pickle.dump") as dump,
        patch(f"{MODULE}.Request"),
        patch(f"{MODULE}.build") as build,
    ):
        bare_client()._build_service()

    saved.refresh.assert_called_once()
    dump.assert_called_once()
    build.assert_called_once_with("youtube", "v3", credentials=saved)


@pytest.mark.parametrize("token_exists", [False, True])
def test_signs_in_when_no_usable_token(token_exists):
    fresh = creds()
    unusable = creds(valid=False, expired=True, refresh_token=None)
    file = mock_open()
    with (
        patch(f"{MODULE}.os.path.exists", return_value=token_exists),
        patch("builtins.open", file),
        patch(f"{MODULE}.pickle.load", return_value=unusable),
        patch(f"{MODULE}.pickle.dump") as dump,
        patch(f"{MODULE}.InstalledAppFlow") as flow,
        patch(f"{MODULE}.build") as build,
    ):
        flow.from_client_secrets_file.return_value.run_local_server.return_value = fresh
        bare_client("secrets.json")._build_service()

    flow.from_client_secrets_file.assert_called_once_with("secrets.json", SCOPES)
    file.assert_called_with(PICKLE_TOKEN, "wb")
    dump.assert_called_once()
    build.assert_called_once_with("youtube", "v3", credentials=fresh)
