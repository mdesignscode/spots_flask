from __future__ import annotations
from logging import info

from engine.retry import retry
from tenacity import stop_after_delay
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bootstrap.container import Clients


class SpotifyUserPlaylistModify:
    """A class to retrieve metadata for a spotify track, album or playlist

    Attributes:
        track_url (str): The spotify url to be processed
    """

    def __init__(self, *, clients: Clients) -> None:
        self.clients = clients

    @retry(stop=stop_after_delay(30))
    def modify_saved_tracks_playlist(self, action: str, tracks: str):
        # update scope for write
        self.clients.secrets.write(
            key="scope", value="user-library-modify"
        )
        self.clients.spotify.signin()

        info(f"Removing {tracks} from playlist...")
        if action == "add":
            self.clients.spotify.spotify.current_user_saved_tracks_add(
                tracks
            )
        elif action == "delete":
            self.clients.spotify.spotify.current_user_saved_tracks_delete(
                [tracks]
            )
        else:
            raise TypeError("`delete` or `add` actions only")

