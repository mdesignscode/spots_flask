#!/usr/bin/python3
"""Metadata for a Spotify Track"""


class Metadata:
    """Metadata for a spotify track"""

    def __init__(
        self,
        title: str,
        artist: str,
        link: str,
        cover: str = "",
        tracknumber: str = "",
        album: str = "",
        lyrics: str = "",
        release_date: str | None = None,
        preview_url: str = "",
        spotify_id: str = ""
    ) -> None:
        """Creates a metadata object

        Args:
            title (str): the songs title
            artist (str): the artist(s)
            link (str): the link of the song
            cover (str, optional): the url for the cover image. Defaults to ""
            tracknumber (str, optional): the song's position in an album. `position/album_length`. Defaults to ""
            album (str, optional): the album name. Defaults to ""
            lyrics (str, optional): the lyrics of the song. Defaults to ""
            release_date (str | None, optional): the release date of the song. Defaults to None
            preview_url (str, optional): A link to a 30 second preview (MP3 format) of the track.
            spotify_id (str, optional): The spotify track id
        """
        self.title: str = title
        self.artist: str = artist
        self.cover: str = cover
        self.tracknumber: str = tracknumber
        self.album: str = album
        self.lyrics: str = lyrics
        self.release_date: str | None = release_date
        self.link: str = link
        self.preview_url = preview_url
        self.spotify_id = spotify_id
