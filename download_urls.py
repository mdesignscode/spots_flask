"""Contains functions that processes a Spotify or YouTube url"""

from engine import storage
from logging import ERROR, basicConfig, error, info, INFO
from dotenv import load_dotenv
from tenacity import retry, stop_after_delay
from models.spotify_worker import SpotifyWorker, Metadata
from models.errors import InvalidURL, SongNotFound
from models.spotify_to_youtube import ProcessSpotifyLink
from models.youtube_to_spotify import ProcessYoutubeLink
from re import search
from typing import List, Tuple, cast
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


load_dotenv()


@retry(stop=stop_after_delay(60))
def convert_url(url: str, single: bool = False):
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
            info("Resource type: single")
            result = cast(Tuple[Metadata, List[Metadata]], spotify.process_url(single))
            metadata = result[0]
            youtube = ProcessYoutubeLink(metadata=metadata)
            youtube_result = youtube.get_title()
            return (
                "single",
                f"{youtube_result[0]} - {youtube_result[1]}",
                (metadata, result[1], youtube_result[2]),
            )
        # playlist
        else:
            info("Resource type: playlist")
            spotify_playlist, album_data = cast(
                tuple[list[Metadata], dict[str, str]], spotify.process_url()
            )
            playlist = search_on_youtube(spotify_playlist)

            storage.save()

            return "playlist", playlist, album_data

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

            return "playlist", playlist, album_data
        else:
            info("Resource type: single")
            # check url availability
            try:
                yt_to_spotify = ProcessYoutubeLink(youtube_url=url)
                metadata = yt_to_spotify.process_youtube_url(single)
                artist, yt_title, file_size = yt_to_spotify.get_title()

                query = f"{metadata.artist} - {metadata.title}"
                result = (yt_title, metadata.__dict__, file_size)
                storage.new(query, result, "youtube")
                storage.save()

                return "single", f"{artist} - {yt_title}", metadata, file_size
            except DownloadError:
                basicConfig(level=ERROR)
                error(f"{url} is not available")
                raise InvalidURL(url)

@retry(stop=stop_after_delay(60))
def playlist_downloader(
    playlist: list[Metadata], album_folder: str, unique_path: bool = False
) -> list[str]:
    """downloads a playlist

    Args:
        playlist (list[Metadata]): list of metadata objects
        album_folder (str): The folder to download an album or playlist to.

    Returns:
        list[str]: A list of errors that may have occurred during the download process
    """
    basicConfig(level=INFO)
    info(f"Downloading {album_folder}...")

    exceptions = []

    for index, track in enumerate(playlist):
        info(f"Downloading track {index + 1}/{len(playlist)}")

        try:
            spotify = ProcessSpotifyLink(track)
            folder = (
                album_folder if not unique_path else f"{album_folder}/{track.album}"
            )
            spotify.download_youtube_video(folder)

        except Exception as e:
            basicConfig(level=ERROR)
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
        'quiet': True,
        'extract_flat': True,
        'playlistend': None,  # Extract full playlist,
        'cookiefile': 'cookies.txt'
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    playlist_name = info.get('title', 'Unknown Playlist')
    playlist_urls = [entry['url'] for entry in info.get('entries', []) if entry.get('url')]

    playlist = []

    # get metadata for each song in playlist
    for video_url in playlist_urls:
        youtube = ProcessYoutubeLink(video_url)
        metadata = youtube.process_youtube_url()
        playlist.append(metadata)

    return playlist_name, playlist

@retry(stop=stop_after_delay(60))
def search_on_youtube(
    spotify_playlist: List[Metadata],
):
    """Searches for a list of titles on youtube

    Returns:
        List[Tuple[str, Dict[str, Any], int]]: A list of tuples containing the youtube title, a metadata dict, and the file size for each metadata in `spotify_playlist`
    """
    playlist = []

    # search for each song on YouTube
    for index, metadata in enumerate(spotify_playlist):
        basicConfig(level=INFO)
        info(f"Searching for track {index + 1}/{len(spotify_playlist)} on YouTube...")

        try:
            # get cached result
            query = f"{metadata.artist} - {metadata.title}"
            cache = storage.get(query, "youtube")
            if cache:
                info(f"Cached result: {cache[0]}")
                playlist.append(cache)
            else:
                try:
                    youtube = ProcessYoutubeLink(metadata=metadata)
                    youtube_result = youtube.get_title()
                    file_size = youtube_result[2]
                    yt_title = f"{youtube_result[0]} - {youtube_result[1]}"

                    result = (yt_title, metadata.__dict__, file_size)

                    storage.new(query, result, "youtube")
                    playlist.append(result)

                    if index % 10 or len(spotify_playlist) == 1:
                        storage.save()
                except SongNotFound:
                    info(f"{metadata.artist} - {metadata.title} not found")
                    continue
        except Exception as e:
            error(f"Error occurred during YouTube search: {e}")
            raise Exception(e)

    storage.save()

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
    # check cache first
    cached_artist = storage.get(artist, "artist")
    if cached_artist:
        return cached_artist

    info(f"Searching for {artist}'s songs on YT")
    options = {
        'format': 'bestaudio/best',
        'cookiefile': 'cookies.txt',  # Path to your cookies file
        'outtmpl': '%(title)s.%(ext)s',
        'noplaylist': True,
        'cachedir': './yt_cache',
    }

    with YoutubeDL(options) as ydl:
        video_record = {}
        vid_info = ydl.extract_info(f"ytsearch50:{artist}", download=False)

        if not vid_info:
            raise SongNotFound(artist)

        for index, entry in enumerate(vid_info['entries']):
            title = entry.get('title')

            if search(artist, title) and not video_record.get(title):
                try:
                    id = entry.get("id")
                    watch_url = f"https://www.youtube.com/watch?v={id}"
                    yt_to_spotify = ProcessYoutubeLink(youtube_url=watch_url)
                    metadata = yt_to_spotify.process_youtube_url(True, default_cover)
                    video_record[title] = metadata

                    storage.new(artist, metadata, "artist")

                    if index % 10:
                        storage.save()
                except SongNotFound:
                    pass

        artist_playlist = list(video_record.values())

        storage.save()

        return artist_playlist

