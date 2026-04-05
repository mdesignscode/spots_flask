from __future__ import annotations

from logging import getLogger
from tenacity import stop_after_delay
from typing import TYPE_CHECKING

from spots_cli.engine import retry
from spots_cli.models import SpotifyUnavailableError

if TYPE_CHECKING:
    from spots_cli.clients import SpotifyClient
    from spots_cli.bootstrap.container import Clients


logger = getLogger(__name__)


class SpotifyUserPlaylistModify:
    """A class to retrieve metadata for a spotify track, album or playlist

    Attributes:
        track_url (str): The spotify url to be processed
    """

    def __init__(self, *, clients: Clients) -> None:
        self.clients = clients

    def _client(self) -> SpotifyClient:
        if not self.clients.spotify:
            raise SpotifyUnavailableError(
                "Spotify client is not configured. Enable Spotify features in your environment."
            )
        return self.clients.spotify

    @retry(stop=stop_after_delay(30))
    def modify_saved_tracks_playlist(self, action: str, tracks: str):
        # update scope for write
        self.clients.secrets.write(key="scope", value="user-library-modify")
        self._client().signin()

        logger.info(f"Removing {tracks} from playlist...")
        if action == "add":
            self._client().client.current_user_saved_tracks_add(tracks)
        elif action == "delete":
            self._client().client.current_user_saved_tracks_delete([tracks])
        else:
            raise TypeError("`delete` or `add` actions only")
