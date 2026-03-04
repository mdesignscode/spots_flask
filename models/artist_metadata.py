from models.playlist_info import PlaylistInfo
from dataclasses import dataclass


@dataclass
class ArtistMetadata:
    """
    Metadata for an artist.

    Args:
        albums list[PlaylistInfo]: a list of metadata for each of the artist's albums/
        cover (str): The artist's cover url.
        name (str): The artist's name.
    """

    albums: list[PlaylistInfo]
    cover: str
    name: str
