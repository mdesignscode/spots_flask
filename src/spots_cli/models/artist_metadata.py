from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spots_cli.models import PlaylistInfo


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
