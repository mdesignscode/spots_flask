from __future__ import annotations

from logging import error
from lyricsgenius import Genius
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clients.secrets_manager import SecretsManager
    from core.web_scraper import WebScraper


class LyricsFinder:
    """
    A service for retrieving lyrics for a song

    Args:
        scraper (WebScrapeService): The web scraper client.

    Attributes:
        genius: Genius api client.
    """

    def __init__(self, *, scraper: WebScraper, secrets_manager: SecretsManager):
        self.secrets_manager = secrets_manager
        self.scraper = scraper
        genius_key = self.secrets_manager.read(key="lyricsgenius_key")
        self.genius = Genius(genius_key)

    def get_lyrics(self, *, artist: str, title: str) -> str:
        """Retrieve lyrics using Genius. Falls back to using alternatives provided by the scraper.

        Args:
            artist (str): The artist.
            title (str): The title.

        Returns:
            str: The lyrics if found, else an empty string.
        """
        try:
            song = self.genius.search_song(title, artist)

            if not song or "Verse" not in song.lyrics or title not in song.title:
                lyrics = self.scraper.scrape_azlyrics(artist=artist, title=title)
            else:
                lyrics = song.lyrics
        except Exception as e:
            error(e)
            lyrics = ""
        return lyrics

