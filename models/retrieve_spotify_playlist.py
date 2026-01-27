from bs4 import BeautifulSoup
from logging import info
from requests import get
from re import search


def retrieve_spotify_playlist(url: str):
    """
    Retrieves Spotify track IDs from a given playlist URL.

    Args:
        url (str): The URL of the Spotify playlist.

    Returns:
        list: A list of track IDs extracted from the playlist page.
        str: playlist cover url
        str: playlist title
    """
    if not url:
        return

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

    return playlist_ids, cover_image, playlist_title
