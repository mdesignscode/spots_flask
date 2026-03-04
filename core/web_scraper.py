from dataclasses import dataclass
from bs4 import BeautifulSoup, Comment
from logging import info
from re import search
from requests import get

@dataclass
class ScrapedResult:
    cover: str
    name: str
    ids: list[str]

def get_element_by_comment(soup: BeautifulSoup, comment_text: str):
    """Find the first element that follows a comment with exact `comment_text`."""
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))

    for comment in comments:
        if comment.strip() == comment_text.strip():
            parent_el = comment.parent
            if parent_el:
                return parent_el

    return None

class WebScraper:
    def scrape_azlyrics(self, *, artist: str, title: str):

        info("Searching for lyrics on AZLyrics")
        artist = artist.lower().replace(" ", "")
        title = title.lower().replace(" ", "")

        url = f"https://azlyrics.com/lyrics/{artist}/{title}.html"

        response = get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        lyrics_comment = "Usage of azlyrics.com content by any third-party lyrics provider is prohibited by our licensing agreement. Sorry about that."
        lyrics_el = get_element_by_comment(soup, lyrics_comment)
        return lyrics_el.text if lyrics_el else ""

    def scrape_spotify_playlist(self, url: str) -> ScrapedResult:
        """
        Retrieves Spotify track IDs from a given playlist URL.

        Args:
            url (str): The URL of the Spotify playlist.

        Returns:
            list: A list of track IDs extracted from the playlist page.
            str: playlist cover url
            str: playlist title
        """
        if not search("spotify", url) and search("playlist", url):
            raise TypeError("Please provide a valid Spotify playlist url")

        info("Scraping spotify playlist")

        # Fetch the webpage content
        response = get(url)

        # Parse the HTML content
        soup = BeautifulSoup(response.text, "html.parser")
        # print(soup, end="\n\n")

        # Find all elements with data-encore-id="listRowTitle"
        tracklist_rows = soup.find_all(attrs={"data-encore-id": "listRowTitle"})

        # find cover image and title
        cover_container = soup.find(attrs={"data-testid": "entity-image"})
        title_container = soup.find(attrs={"data-encore-id": "text"})

        cover_image = cover_container.find("img")["src"] if title_container else None
        playlist_title = title_container.text if title_container else None

        # Extract the id attributes from the tracklist rows
        id_values = [p_tag["id"] for p_tag in tracklist_rows]

        # Extract the Spotify track IDs using regex
        playlist_ids = []
        for id_value in id_values:
            match = search(r"spotify:track:([a-zA-Z0-9]+)", id_value)
            if match:
                track_id = match.group(1)
                playlist_ids.append(track_id)

        return ScrapedResult(ids=playlist_ids, cover=cover_image, name=playlist_title)

