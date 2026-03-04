"""Contains functions that processes a Spotify or YouTube url"""

from dotenv import load_dotenv
from logging import error, info
from models.sentinel import Sentinel
from models.spotify_worker import SpotifyWorker, Metadata
from models.errors import InvalidURL, SongNotFound
from models.process_spotify_link import ProcessSpotifyLink
from models.process_youtube_link import ProcessYoutubeLink
from re import search
from services.youtube_search_service import YoutubeSearchService
from services.ytdlp_client import YtDlpClient
from tenacity import stop_after_delay
from engine.retry import retry
from typing import List, Sequence, Tuple, cast, Any
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


load_dotenv()


@retry(stop=stop_after_delay(60))
def playlist_downloader(
    playlist: list[Metadata],
    album_data: dict[str, str],
    album_folder: str,
    unique_path: bool = False,
) -> list[str]:
    """downloads a playlist

    Args:
        playlist (list[Metadata]): list of metadata objects
        album_folder (str): The folder to download an album or playlist to.

    Returns:
        list[str]: A list of errors that may have occurred during the download process
    """
    info(f"Downloading {album_folder}...")

    exceptions = []
    folder = album_folder if not unique_path else f"{album_folder}/{album_data}"
    ytdlp = YtDlpClient(directory_path=folder)

    for index, track in enumerate(playlist):
        info(f"Downloading track {index + 1}/{len(playlist)}")

        try:
            spotify = ProcessSpotifyLink(ytdlp=ytdlp)
            youtube_url = spotify.youtube_search.search_best_match(track)
            spotify.ytdlp.download_youtube_video(youtube_url, track, folder)

        except Exception as e:
            error(f"Error occurred during download: {e}")
            exceptions.append(str(e))

    return exceptions

def search_artist_on_yt(artist: str, default_cover: str):
    """
    Search for for all videos by an artist name on youtube

    Args:
        artist (str): The name of the artist
        default_cover (str): Fallback cover url

    Returns:
        List[Metadata]: A list of songs by `artist` found on YT
    """
    from engine import storage

    info(f"[Search Artist on YouTube] Searching for {artist}'s songs on YT")

    def artist_search():
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
        }

        ytdl = YtDlpClient(options=ydl_opts)
        search_results = ytdl.search(artist, False)

        if not search_results:
            raise SongNotFound(artist)

        video_record: dict[str, Metadata] = {}

        playlist_len = len(search_results["entries"])
        for index, entry in enumerate(search_results["entries"]):
            info(
                f"[Search Artist on YouTube] Searching for track {index + 1}/{playlist_len} on YouTube..."
            )
            title = entry.get("title")

            if not video_record.get(title):
                try:
                    id = entry.get("id")
                    watch_url = f"https://www.youtube.com/watch?v={id}"
                    yt_to_spotify = ProcessYoutubeLink()
                    metadata = yt_to_spotify.youtube_search.process_youtube_url(
                        watch_url, True, default_cover
                    )
                    video_record[title] = metadata

                    if (index % 10 == 0) or (index == (playlist_len - 1)):
                        storage.save()

                except SongNotFound:
                    continue
            else:
                continue

            artist_playlist = list(video_record.values())
            storage.new(artist, artist_playlist, query_type="artist")

            storage.save()

            return artist_playlist

    return storage.get(artist, "artist", artist_search)

