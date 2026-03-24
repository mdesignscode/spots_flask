from dataclasses import dataclass
from bs4 import BeautifulSoup, Comment, Tag
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
        if not (search("spotify", url) and search("playlist", url)):
            raise TypeError("Please provide a valid Spotify playlist url")

        info("Scraping spotify playlist")

        response = get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        tracklist_rows = soup.find_all(attrs={"data-encore-id": "listRowTitle"})

        cover_container = soup.find(attrs={"data-testid": "entity-image"})
        title_container = soup.find(attrs={"data-encore-id": "text"})

        # Cover
        cover_image: str = ""
        if cover_container:
            img_tag = cover_container.find("img")
            if isinstance(img_tag, Tag):
                cover_image = img_tag.get("src", "")

        # Title
        playlist_title: str = ""
        if isinstance(title_container, Tag):
            playlist_title = title_container.get_text(strip=True)

        # Track IDs
        playlist_ids: list[str] = []

        for tag in tracklist_rows:
            if isinstance(tag, Tag):
                id_value = tag.get("id")
                if isinstance(id_value, str):
                    match = search(r"spotify:track:([a-zA-Z0-9]+)", id_value)
                    if match:
                        playlist_ids.append(match.group(1))

        return ScrapedResult(
            ids=playlist_ids,
            cover=cover_image,
            name=playlist_title
        )

