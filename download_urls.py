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
def convert_url(url: str, single: bool = False) -> dict[str, Any]:
    """Converts a youtube or spotify url to mp3, or a youtube video to mp3

    Args:
        url (str): url to be converted
        single: (bool, optional): don't search for recommended tracks if false. Defaults to False

    Raises:
        InvalidURL: if provided url not available
    """
    # process spotify link
    info("Process:: Converting url")

    if "spotify" in url:
        info("URL type: Spotify")
        spotify = SpotifyWorker(url)
        # single
        if "track" in url:
            # retrieve Spotify data
            info("Resource type: single")
            result = cast(
                Tuple[
                    Metadata,
                    List[Metadata],  # optional list of recommended tracks metadata
                ],
                spotify.process_url(single),
            )
            metadata = result[0]

            # search on YouTube
            youtube = YoutubeSearchService()
            youtube_result = youtube.process_spotify_title(metadata)

            return {
                "resource_type": "single",
                "youtube_title": f"{youtube_result[0]} - {youtube_result[1]}",
                "metadata": {"single": metadata, "recommended": result[1]},
                "filesize": youtube_result[2],
                "playlist_info": None,
            }
        # playlist
        else:
            info("Resource type: playlist")
            spotify_playlist, album_data = cast(
                tuple[list[Metadata], dict[str, str]], spotify.process_url()
            )
            playlist = search_on_youtube(spotify_playlist)

            return {
                "resource_type": "playlist",
                "youtube_title": None,
                "metadata": None,
                "filesize": None,
                "playlist_info": {"album_data": album_data, "playlist": playlist},
            }

    # process youtube link
    elif "youtu" in url:
        info("URL type: YouTube")
        # download a youtube playlist
        if "playlist" in url:
            info("Resource type: playlist")
            playlist_name, metadata_list = process_youtube_playlist(url)

            cover = "http://localhost:5000/static/youtube-playlist.jpg"

            album_data = {
                "cover": cover,
                "name": playlist_name,
                "artist": "",
            }

            playlist = search_on_youtube(metadata_list)

            return {
                "resource_type": "playlist",
                "youtube_title": None,
                "metadata": None,
                "filesize": None,
                "playlist_info": {"album_data": album_data, "playlist": playlist},
            }
        else:
            info("Resource type: single")
            # check url availability
            try:
                yt_to_spotify = ProcessYoutubeLink()
                metadata = yt_to_spotify.youtube_search.process_youtube_url(url, single)
                artist, yt_title, file_size = yt_to_spotify.youtube_search.get_title(
                    url
                )

                result = (yt_title, metadata.__dict__, file_size)

                return {
                    "resource_type": "single",
                    "youtube_title": f"{artist} - {yt_title}",
                    "metadata": {"single": metadata, "recommended": []},
                    "filesize": file_size,
                }
            except DownloadError:
                error(f"{url} is not available")
                raise InvalidURL(url)
    else:
        raise InvalidURL(url)


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


@retry(stop=stop_after_delay(60))
def process_youtube_playlist(url: str) -> tuple[str, list[Metadata]]:
    """processes all songs in a youtube playlist

    Args:
        url (str): the url of the playlist

    Returns:
        tuple[str, list[Metadata]]: the playlist name and playlist items
    """
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "playlistend": None,  # Extract full playlist,
        "cookiefile": "cookies.txt",
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    playlist_name = info.get("title", "Unknown Playlist")
    playlist_urls = [
        entry["url"] for entry in info.get("entries", []) if entry.get("url")
    ]

    playlist = []

    # get metadata for each song in playlist
    for video_url in playlist_urls:
        youtube = ProcessYoutubeLink()
        metadata = youtube.youtube_search.process_youtube_url(video_url)
        playlist.append(metadata)

    return playlist_name, playlist


@retry(stop=stop_after_delay(60))
def search_on_youtube(
    spotify_playlist: List[Metadata],
):
    """Searches for a list of titles on youtube

    Args:
        spotify_playlist (List[Metadata]) : The list of spotify tracks to be searched for.

    Returns:
        List[Tuple[str, Dict[str, Any], int]]: A list of tuples containing the youtube title, a metadata dict, and the file size for each metadata in `spotify_playlist`
    """
    from engine import storage

    playlist = []

    # search for each song on YouTube
    for index, metadata in enumerate(spotify_playlist):
        playlist_len = len(spotify_playlist)
        youtube = ProcessYoutubeLink()
        info(
            f"[Search On YouTube] Searching for track {index + 1}/{playlist_len} on YouTube..."
        )

        try:
            try:
                artist, title, filesize = youtube.youtube_search.process_spotify_title(
                    metadata
                )
                yt_title = f"{artist} - {title}"

                result = (yt_title, metadata.__dict__, filesize)

                playlist.append(result)

                if (index % 10 == 0) or (index == (playlist_len - 1)):
                    storage.save()

            except SongNotFound:
                info(f"{metadata.artist} - {metadata.title} not found")
                continue
        except Exception as e:
            error(f"Error occurred during YouTube search: {e}")
            raise Exception(e)

    return playlist


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

