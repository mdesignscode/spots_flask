#!/usr/bin/python3
"""Contains functions that processes a Spotify or YouTube url"""

from logging import ERROR, basicConfig, error
from dotenv import load_dotenv
from tenacity import retry, stop_after_delay
from models.get_spotify_track import GetSpotifyTrack, Metadata
from models.errors import InvalidURL, SongNotFound
from models.spotify_to_youtube import ProcessSpotifyLink
from models.youtube_to_spotify import ProcessYoutubeLink
from os import getenv
from pytube import Playlist, YouTube
from typing import Any, Dict, List, Tuple, cast

load_dotenv()


@retry(stop=stop_after_delay(60))
async def convert_url(url: str):
    """Converts a youtube or spotify url to mp3, or a youtube video to mp3

    Args:
        url (str): url to be converted

    Raises:
        InvalidURL: if provided url not available
    """
    # process spotify link
    if "spotify" in url:
        spotify = GetSpotifyTrack(url)
        # single
        if "track" in url:
            result = cast(Tuple[Metadata, List[Metadata]], spotify.process_url())
            metadata = result[0]
            youtube = ProcessYoutubeLink(metadata=cast(Metadata, metadata))
            youtube_result = youtube.get_title()
            return "single", f"{youtube_result[0]} - {youtube_result[1]}", (metadata, result[1], youtube_result[2])
        # playlist
        else:
            spotify_playlist, album_data = cast(
                tuple[list[Metadata], dict[str, str]], spotify.process_url()
            )
            playlist = search_on_youtube(spotify_playlist)

            return "playlist", playlist, album_data

    # process youtube link
    elif "youtu" in url:
        # download a youtube playlist
        if "playlist" in url:
            playlist_name, metadata_list = process_youtube_playlist(url)

            cover = "/static/youtube-playlist.jpg"

            album_data = {
                "cover": cover,
                "name": playlist_name,
                "artist": "",
            }

            playlist = search_on_youtube(metadata_list)

            return "playlist", playlist, album_data
        else:
            # check url availability
            try:
                youtube = YouTube(url, use_oauth=bool(getenv("use_oauth")))
                youtube.check_availability()
            except:
                basicConfig(level=ERROR)
                error(f"{url} is not available")
                raise InvalidURL(url)

            yt_to_spotify = ProcessYoutubeLink(youtube_url=url)
            metadata = await yt_to_spotify.process_youtube_url()
            artist, title, _ = yt_to_spotify.get_title()
            return "single", f"{artist} - {title}", metadata


def playlist_downloader(playlist: list[Metadata], album_folder: str) -> list[str]:
    """downloads a playlist

    Args:
        playlist (list[Metadata]): list of metadata objects
        album_folder (str): The folder to download an album or playlist to.

    Returns:
        list[str]: A list of errors that may have occurred during the download process
    """
    print(f"Downloading {album_folder}...")

    exceptions = []

    for track in playlist:
        try:
            spotify = ProcessSpotifyLink(track)
            spotify.download_youtube_video(album_folder)
        except Exception as e:
            exceptions.append(str(e))

    return exceptions


def process_youtube_playlist(url: str) -> tuple[str, list[Metadata]]:
    """processes all songs in a youtube playlist

    Args:
        url (str): the url of the playlist

    Returns:
        tuple[str, list[Metadata]]: the playlist name and playlist items
    """
    playlist = Playlist(url)
    playlist_urls = playlist.video_urls

    playlist_name = playlist.title

    playlist = []

    # get metadata for each song in playlist
    for video_url in playlist_urls:
        youtube = ProcessYoutubeLink(video_url)
        metadata = youtube.process_youtube_url()
        playlist.append(metadata)

    return playlist_name, playlist


def search_on_youtube(
    spotify_playlist: List[Metadata],
) -> List[Tuple[str, Dict[str, Any], int]]:
    """Searches for a list of titles on youtube

    Returns:
        List[Tuple[str, Dict[str, Any], int]]: A list of tuples containing the youtube title, a metadata dict, and the file size for each metadata in `spotify_playlist`
    """
    playlist = []

    # search for each song on YouTube
    for metadata in spotify_playlist:
        try:
            youtube = ProcessYoutubeLink(metadata=metadata)
            youtube_result = youtube.get_title()
            yt_title = f"{youtube_result[0]} - {youtube_result[1]}"
            playlist.append((yt_title, metadata.__dict__, youtube_result[2]))
        except SongNotFound:
            pass

    return playlist
