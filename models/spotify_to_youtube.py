#!/usr/bin/python3
"""Factor an object to Retrieve and Download a Youtube Video as MP3"""

from __future__ import unicode_literals
from math import ceil
from dotenv import load_dotenv
from logging import basicConfig, error, ERROR, info, INFO
from hashlib import md5
from models.errors import TitleExistsError, SongNotFound, InvalidURL
from models.metadata import Metadata
from moviepy.editor import AudioFileClip
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC, TIT2, TPE1, TRCK, TALB, USLT, TDRL
from mutagen.mp3 import MP3
from os import path, remove, getenv
from requests import get
from pytube import YouTube
from typing import Any, Dict, List, cast
from youtube_search import YoutubeSearch

load_dotenv()


class ProcessSpotifyLink:
    """A client that Retrieves and Download a Youtube Video as MP3

    Attributes:
        spotify_track (Metadata): an object with metadata
        youtube_url (str, optional): youtube url to be downloaded. Defaults to ''.
    """

    def __init__(self, spotify_track: Metadata, youtube_url=""):
        self.spotify_track = spotify_track
        self.youtube_url = youtube_url or self.get_youtube_video()

        # check url availability
        try:
            self.youtube = YouTube(
                self.youtube_url, use_oauth=bool(getenv("use_oauth"))
            )
            self.youtube.check_availability()
        except:
            basicConfig(level=ERROR)
            error(f"{self.youtube_url} is not available")
            raise InvalidURL(self.youtube_url)

    def download_youtube_video(self, directory_path="", get_size=False):
        """Downloads a youtube video as audio, or returns the file size of the video.

        Args:
            directory_path (str, optional): The directory to save a playlist to. Defaults to ''.

        Returns:
            float | None: The size of the video in MB
        """
        # no search result found
        if not self.youtube_url:
            return

        # add title to downloads history
        track_title = f"{self.spotify_track.artist} - {self.spotify_track.title}"
        # '/' will read file name as folder in *nix systems
        track_title = track_title.replace("/", "|")

        if not get_size:
            self.add_to_download_history(track_title)

        # get highest quality audio file
        try:
            audio = self.youtube.streams.get_audio_only()

            if not audio:
                basicConfig(level=INFO)
                info(f"{self.youtube_url} not available")
                raise SongNotFound(self.youtube_url)

            if get_size:
                return ceil(audio.filesize_mb)
        except:
            basicConfig(level=ERROR)
            error(f"Couldn't download {track_title}")
            return

        # get audio file name
        filename = audio.default_filename
        ext = filename.split(".")[1]

        # file name to download to
        output = path.join(directory_path, filename)

        # Check if the file name length is too long, and truncate if necessary
        max_filename_length = 255  # Maximum allowed file name length on most systems
        if len(filename) > max_filename_length:
            # Generate a unique file name using a hash function (MD5 in this case)
            file_hash = md5(track_title.encode()).hexdigest()
            output = path.join(directory_path, f"{file_hash[:25]}.{ext}")
            filename = f"{file_hash[:25]}.{ext}"

        # download the audio file
        print(f"Downloading {track_title}...")
        audio.download(output_path=directory_path, filename=filename)

        # convert to mp3 and update metadata
        self.convert_to_mp3(
            output,
            path.join(directory_path, filename.replace(".mp4", ".mp3")),
            track_title,
        )

    def update_metadata(self, audio_path: str):
        """Updates the metadata of song to be downloaded

        Args:
            audio_path (str): the path of the audio file to be updated
        """
        print("Updating metadata")
        try:
            audio = MP3(audio_path, ID3=ID3)

            metadata = self.spotify_track

            # Remove existing ID3 tags
            audio.tags = None

            # Create new ID3 tags
            audio.tags = ID3()

            # Set the metadata attributes
            audio.tags.add(TIT2(encoding=3, text=metadata.title))
            audio.tags.add(TPE1(encoding=3, text=metadata.artist))
            audio.tags.add(TRCK(encoding=3, text=metadata.tracknumber))
            audio.tags.add(TALB(encoding=3, text=metadata.album))

            cover = metadata.cover
            if "/static/" in cover:
                cover = "http://127.0.01:5000" + cover

            if cover:
                audio.tags.add(
                    APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=get(cover).content,
                    )
                )

            # Add lyrics if provided
            lyrics = metadata.lyrics
            if lyrics:
                audio.tags.add(USLT(encoding=3, lang="eng", desc="", text=lyrics))

            # Set the release date
            release_date = metadata.release_date
            if release_date:
                audio.tags.add(TDRL(encoding=3, text=release_date))

            # Save the changes
            audio.save(audio_path)

        except FileNotFoundError:
            basicConfig(level=ERROR)
            error(f"{audio_path} not found...")
            return

    @staticmethod
    def add_to_download_history(title="", add_title=False):
        """Adds a downloaded song's title to history

        Args:
            title (str, optional): The title to be added. Defaults to ''.
            add_title (bool, optional): If False, only checks if title already exists. Defaults to false.

        Raises:
            TitleExistsError: if title already in downloads history
        """
        history_file = ".spots_download_history.txt"

        # Check if the file exists, otherwise create it
        if not path.isfile(history_file):
            with open(history_file, "w", newline=""):
                pass

        # Check if the title already exists in the file
        with open(history_file, "r") as file:
            history = file.read().split("\n")
            for song in history:
                if title == song:
                    raise TitleExistsError(title)

        # Add the title to the file
        if add_title:
            with open(history_file, "a", newline="") as file:
                file.write(f"{title}\n")

    def get_youtube_video(self, search_title="") -> str:
        """Searches for a given title on youtube

        Args:
            search_title (str, optional): the search title. Defaults to ''.

        Raises:
            SongNotFound: if `search_title` not found

        Returns:
            str: the watch url
        """
        title = (
            f"{search_title} Audio"
            if search_title
            else f"{self.spotify_track.title} - {self.spotify_track.artist} Audio"
        )

        print(f"Searching for {title} on YouTube...")

        results = YoutubeSearch(title, max_results=1)
        first_result = cast(List[Dict[str, Any]], results.to_dict())[0]

        print(f'Found: {first_result["title"]}, by channel: {first_result["channel"]}')

        return "https://www.youtube.com/watch?v=" + first_result["id"]

    def convert_to_mp3(self, old_file: str, new_file: str, song_title: str):
        """converts an audio file to mp3, updates the metadata and removes the original file

        Args:
            old_file (str): the file to be converted
            new_file (str): the name of the new file
            song_title (str): the title to be added to downloads history
        """
        try:
            # Load the audio clip
            clip = AudioFileClip(old_file)
            # Convert and save as MP3 format
            clip.write_audiofile(new_file, codec="mp3")

            # Close the clip
            clip.close()
            remove(old_file)

            if self.spotify_track:
                self.update_metadata(new_file)

        except FileNotFoundError:
            basicConfig(level=ERROR)
            error(f"{old_file} not found...")
            return

        self.add_to_download_history(song_title, True)
