from bs4 import BeautifulSoup, Comment
from logging import info
from requests import get


def get_element_by_comment(soup: BeautifulSoup, comment_text: str):
    """Find the first element that follows a comment with exact `comment_text`."""
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))

    for comment in comments:
        if comment.strip() == comment_text.strip():
            parent_el = comment.parent
            if parent_el:
                return parent_el

    return None


def scrape_azlyrics(artist: str, title: str):
    info("Searching for lyrics on AZLyrics")
    artist = artist.lower().replace(" ", "")
    title = title.lower().replace(" ", "")

    url = f"https://azlyrics.com/lyrics/{artist}/{title}.html"

    response = get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    lyrics_comment = "Usage of azlyrics.com content by any third-party lyrics provider is prohibited by our licensing agreement. Sorry about that."
    lyrics_el = get_element_by_comment(soup, lyrics_comment)
    return lyrics_el.text if lyrics_el else ""
