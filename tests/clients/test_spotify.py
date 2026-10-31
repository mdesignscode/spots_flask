import pytest
from unittest.mock import Mock, patch, MagicMock
from spots_cli.clients.spotify import SpotifyClient, DEFAULT_USER_SCOPE
from spotipy.exceptions import SpotifyException


class TestSpotifyClient:

    @pytest.fixture
    def client(self):
        with patch("spots_cli.clients.spotify.SpotifyClientCredentials"):
            return SpotifyClient()

    @pytest.fixture
    def mock_spotify(self):
        return Mock()

    def test_init(self):
        with patch("spots_cli.clients.spotify.SpotifyClientCredentials") as mock_auth:
            with patch("spots_cli.clients.spotify.Spotify") as mock_spotify:
                client = SpotifyClient()
                mock_auth.assert_called_once()
                mock_spotify.assert_called_once()

    def test_get_user_no_username_env(self, client):
        with patch.dict("os.environ", {}, clear=True):
            result = client.get_user()
            assert result is None

    def test_get_user_success(self, client):
        mock_user_data = {
            "display_name": "Test User",
            "external_urls": {"spotify": "https://open.spotify.com/user/test"},
            "id": "test123",
        }

        with patch.dict("os.environ", {"username": "testuser"}):
            with patch.object(client, "signin"):
                with patch.object(
                    client.client, "current_user", return_value=mock_user_data
                ):
                    result = client.get_user()
                    assert result == "Test User"

    def test_get_user_spotify_exception(self, client):
        mock_exception = SpotifyException(500, -1, "Authentication failed")

        with patch.dict("os.environ", {"username": "testuser"}):
            with patch.object(client, "signin", side_effect=mock_exception):
                result = client.get_user()
                assert result is None

    def test_signin_no_username(self, client):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(Exception, match="No `username` declared"):
                client.signin()

    def test_signin_already_signed_in(self, client):
        with patch.dict("os.environ", {"username": "testuser"}):
            with patch.object(
                client.client, "current_user", return_value={"display_name": "Test"}
            ):
                # Should not raise exception
                client.signin()

    def test_signin_with_token_prompt(self, client):
        mock_token = "test_token_12345"
        mock_exception = SpotifyException(-1, -1, "Need authentication")
        mock_exception.code = -1

        with patch.dict(
            "os.environ", {"username": "testuser", "scope": "user-library-read"}
        ):
            with patch.object(
                client.client, "current_user", side_effect=mock_exception
            ):
                with patch(
                    "spots_cli.clients.spotify.prompt_for_user_token",
                    return_value=mock_token,
                ):
                    with patch("spots_cli.clients.spotify.Spotify") as mock_spotify:
                        client.signin()
                        # Verify token-based client was created
                        mock_spotify.assert_called_with(auth=mock_token)

    def test_signin_with_default_scope(self, client):
        mock_token = "test_token_12345"
        mock_exception = SpotifyException(-1, -1, "Need authentication")
        mock_exception.code = -1

        with patch.dict("os.environ", {"username": "testuser"}, clear=True):
            with patch.object(
                client.client, "current_user", side_effect=mock_exception
            ):
                with patch(
                    "spots_cli.clients.spotify.prompt_for_user_token",
                    return_value=mock_token,
                ) as mock_prompt:
                    with patch("spots_cli.clients.spotify.Spotify"):
                        client.signin()
                        # Verify default scope was used
                        mock_prompt.assert_called_with("testuser", DEFAULT_USER_SCOPE)

    def test_signin_custom_scope(self, client):
        mock_token = "test_token_12345"
        mock_exception = SpotifyException(-1, -1, "Need authentication")
        mock_exception.code = -1
        custom_scope = "user-library-read user-read-private"

        with patch.dict("os.environ", {"username": "testuser", "scope": custom_scope}):
            with patch.object(
                client.client, "current_user", side_effect=mock_exception
            ):
                with patch(
                    "spots_cli.clients.spotify.prompt_for_user_token",
                    return_value=mock_token,
                ) as mock_prompt:
                    with patch("spots_cli.clients.spotify.Spotify"):
                        client.signin()
                        mock_prompt.assert_called_with("testuser", custom_scope)

    def test_signin_no_token_returned(self, client):
        mock_exception = SpotifyException(-1, -1, "Need authentication")
        mock_exception.code = -1

        with patch.dict("os.environ", {"username": "testuser"}):
            with patch.object(
                client.client, "current_user", side_effect=mock_exception
            ):
                with patch(
                    "spots_cli.clients.spotify.prompt_for_user_token", return_value=None
                ):
                    with pytest.raises(Exception, match="Can't get token for"):
                        client.signin()

    def test_signin_other_spotify_exception(self, client):
        mock_exception = SpotifyException(401, 401, "Invalid credentials")
        mock_exception.code = 401

        with patch.dict("os.environ", {"username": "testuser"}):
            with patch.object(
                client.client, "current_user", side_effect=mock_exception
            ):
                with pytest.raises(SpotifyException):
                    client.signin()
