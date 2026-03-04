from dataclasses import dataclass


@dataclass
class Metadata:
    """Creates a metadata object

    Args:
        title (str): the songs title
        artist (str): the artist(s)
        link (str): the link of the song
        cover (str, optional): the url for the cover image. Defaults to ""
        tracknumber (str, optional): the song's position in an album. `position/album_length`. Defaults to ""
        album (str, optional): the album name. Defaults to ""
        lyrics (str, optional): the lyrics of the song. Defaults to ""
        release_date (str | None, optional): the release date of the song. Defaults to None.
        preview_url (str | None, optional): A link to a 30 second preview (MP3 format) of the track. Defaults to None.
    """

    title: str
    artist: str
    link: str
    cover: str | None = ""
    tracknumber: str | None = ""
    album: str | None = ""
    lyrics: str | None = ""
    release_date: str | None = None
    preview_url: str | None = None

    @property
    def full_title(self):
        return f"{self.artist} - {self.title}"

