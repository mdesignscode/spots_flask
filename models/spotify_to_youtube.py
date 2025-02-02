#!/usr/bin/python3
"""Factor an object to Retrieve and Download a Youtube Video as MP3"""

from __future__ import unicode_literals
from engine import storage
from math import ceil
from dotenv import load_dotenv
from logging import basicConfig, error, ERROR, info, INFO
from hashlib import md5
from models.errors import TitleExistsError, SongNotFound
from models.metadata import Metadata
from moviepy.editor import AudioFileClip
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC, TIT2, TPE1, TRCK, TALB, USLT, TDRL
from mutagen.mp3 import MP3
from os import path, remove
from requests import get
from re import compile, sub, search, escape
from typing import Any, cast
from yt_dlp import YoutubeDL
from tenacity import retry, stop_after_delay

load_dotenv()

DELIMITERS_PATTERN = r"( x | & |\s(ft|feat|featuring)\W?)"

class ProcessSpotifyLink:
    """A client that Retrieves and Download a Youtube Video as MP3

    Attributes:
        spotify_track (Metadata): an object with metadata
        youtube_url (str, optional): youtube url to be downloaded. Defaults to ''.
    """

    def __init__(self, spotify_track: Metadata, youtube_url=""):
        options = {
            "format": "bestaudio/best",
            "quiet": True,
            "cookiefile": "cookies.txt",  # Path to your cookies file
            "outtmpl": "%(title)s.%(ext)s",
        }
        with YoutubeDL(options) as ydl:
            self.youtube = ydl

        self.spotify_track = spotify_track
        self.youtube_url = youtube_url or self.get_youtube_video()

    # @retry(stop=stop_after_delay(max_delay=120))
    def download_youtube_video(self, directory_path="", get_size=False):
        """Downloads a YouTube video as audio, or returns the file size of the video.

        Args:
            directory_path (str, optional): The directory to save the audio. Defaults to ''.
            get_size (bool, optional): If True, only calculate the size of the audio. Defaults to False.

        Returns:
            float | None: The size of the video in MB, if get_size is True.
        """
        # No search result found
        if not self.youtube_url:
            return

        # Add title to downloads history
        track_title = f"{self.spotify_track.artist} - {self.spotify_track.title}"
        # '/' will read file name as folder in *nix systems
        track_title = track_title.replace("/", "|")

        # return if song already downloaded
        if not get_size:
            self.add_to_download_history(track_title)

        # check cache
        cache = storage.get(self.youtube_url, "ytdl")
        if cache:
            info(f"Cached result: {cache['title']}")
            video_info = cache

        else:
            # get data online and store in cache
            video_info = self.youtube.extract_info(
                self.youtube_url, download=False
            )
            storage.new(self.youtube_url, video_info, "ytdl")

        if not video_info:
            raise SongNotFound(self.youtube_url)

        filename = video_info["title"]
        ext = video_info.get("audio_ext")

        # Check if the file name length is too long, truncate if necessary
        max_filename_length = 255  # Maximum allowed file name length on most systems
        if len(filename) > max_filename_length:
            file_hash = md5(track_title.encode()).hexdigest()
            filename = f"{file_hash[:25]}.{ext}"

        return self.download_with_ytdlp(track_title, directory_path, get_size)

    def download_with_ytdlp(self, track_title, directory_path, get_size=False):
        """download audio using yt-dlp.

        Args:
            track_title (str): The title of the track.
            directory_path (str): The directory to save the audio.
            get_size (bool, optional): If True, only calculate the size of the audio. Defaults to False.

        Returns:
            float | None: The size of the video in MB, if get_size is True.
        """
        # check cached response for getting size only
        if get_size:
            cache = storage.get(self.youtube_url, "ytdl")

            if cache:
                file_size_bytes = cache.get("filesize") or cache.get(
                    "filesize_approx"
                )
                return (
                    ceil(file_size_bytes / (1024 * 1024)) if file_size_bytes else 0
                )

        options = {
            "format": "bestaudio/best",
            "outtmpl": path.join(directory_path, "%(title)s.%(ext)s"),
            # "quiet": True,
            "cookiefile": "cookies.txt",  # Path to your cookies file,
            "noplaylist": True,
            "cachedir": "./yt_cache",
        }

        if get_size:
            options["simulate"] = True
            options["noplaylist"] = True
            options["skip_download"] = True
            options["forcejson"] = True

        try:
            with YoutubeDL(options) as ydl:
                info(f"Processing {track_title} using yt-dlp...")
                info_dict = ydl.extract_info(self.youtube_url, download=not get_size)

                if get_size:
                    file_size_bytes = info_dict.get("filesize") or info_dict.get(
                        "filesize_approx"
                    )
                    return (
                        ceil(file_size_bytes / (1024 * 1024)) if file_size_bytes else 0
                    )

                if not get_size:
                    # Dynamically infer the downloaded file extension
                    downloaded_path = ydl.prepare_filename(info_dict)
                    ext = downloaded_path.rsplit(".", 1)[-1]
                    final_path = downloaded_path.rsplit(".", 1)[0] + ".mp3"

                    # Convert file to MP3 if necessary
                    if ext != "mp3":
                        self.convert_to_mp3(downloaded_path, final_path, track_title)
                    else:
                        error(f"Audio already in MP3 format: {downloaded_path}")

                    # Update metadata if Spotify track information is available
                    if self.spotify_track:
                        self.update_metadata(final_path)

                    info(f"Audio downloaded successfully with yt-dlp: {final_path}")
        except Exception as e:
            raise Exception(f"yt-dlp failed for {self.youtube_url}: {e}")

    def update_metadata(self, audio_path: str):
        """Updates the metadata of the song to be downloaded

        Args:
            audio_path (str): the path of the audio file to be updated
        """
        info("Updating metadata")
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

        except FileNotFoundError as e:
            basicConfig(level=ERROR)
            error(f"{audio_path} not found...")
            raise e

    @staticmethod
    def add_to_download_history(title="", add_title=False):
        """Adds a downloaded song's title to history

        Args:
            title (str, optional): The title to be added. Defaults to ''.
            add_title (bool, optional): If False, only checks if title already exists. Defaults to False.

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

    # @retry(stop=stop_after_delay(max_delay=120))
    def get_youtube_video(self, search_title="") -> str:
        """Searches for a given title on YouTube

        Args:
            search_title (str, optional): the search title. Defaults to ''.

        Raises:
            SongNotFound: if `search_title` not found

        Returns:
            str: the watch URL
        """
        def match_titles(results, pattern):
            # remove keywords
            result_title = results["entries"][0]["title"]
            processed_title = self.remove_odd_keywords(result_title)

            normalize_string = lambda s: sub(r"\W", "", s).lower()

            # ensure consistent delimiters
            consistent_delimiters = compile(DELIMITERS_PATTERN)
            consistent_title = consistent_delimiters.sub(", ", processed_title.lower())

            # Normalize whitespace and ignore case
            normalized_pattern = normalize_string(pattern)
            normalized_title = normalize_string(consistent_title)

            # grab result title and pattern title
            try:
                _, split_consistent_title = consistent_title.split(" - ", maxsplit=1)
                yt_title = normalize_string(split_consistent_title)
                _, split_pattern = pattern.split(" - ", maxsplit=1)
                spotify_title = normalize_string(split_pattern)
            except ValueError:
                yt_title = normalized_title
                spotify_title = normalized_pattern

            # match titles only
            spotify_match = spotify_title in normalized_title
            yt_match = yt_title in normalized_pattern

            # match pattern to full title
            pattern_match = normalized_pattern in normalized_title
            title_match = normalized_title in normalized_pattern

            # try to extract title from pattern
            title_extract_pattern = r"\s\([\w\W]*"
            pattern_title_match = search(title_extract_pattern, pattern)
            pattern_title = ""

            if pattern_title_match:
                pattern_title = pattern_title_match.group(0)

            pattern_title_matches_yt = pattern_title in normalized_title

            # prepare search conditions
            conditions = [
                    spotify_match, yt_match, pattern_match,
                    title_match, pattern_title_matches_yt
            ]

            if any(conditions):
                closest_match = results["entries"][0]
                closest_match.update({ "title": processed_title })
                return closest_match

        # search for audio version
        title = (
            f"{search_title} Audio"
            if search_title
            else f"{self.spotify_track.artist} - {self.spotify_track.title} Audio"
        )
        title = self.remove_odd_keywords(title)

        # create search pattern
        pattern = title.replace(" Audio", "").lower()

        info(f"Searching for {title} on YouTube...")

        closest_match = None
        results = None

        cached_result = storage.get(title, "ytdl")
        if cached_result == "Not found":
            info(f"[Cache] {title} not found")
            raise SongNotFound(title)
        if cached_result:
            if not cached_result["playlist_count"]:
                info(f"[Cache] {title} not found")
                raise SongNotFound(title)

            info(f"[Cache] {title} found")

            id = cached_result.get("id")
            return f"https://www.youtube.com/watch?v={id}"
        else:
            results = self.youtube.extract_info(f"ytsearch:{title}", download=False)

        if not results:
            raise SongNotFound(title)

        try:
            # empty response
            if not results.get("playlist_count"):
                raise SongNotFound("")

            closest_match = match_titles(results, pattern)
            # no matching results found
            if not closest_match:
                info("No match found")
                raise SongNotFound("")

        except SongNotFound:
            info("Searching for music video version")
            # search for music video version
            title = title.replace(" Audio", "")

            cached_result = storage.get(title, "ytdl")
            if cached_result:
                info(f"[Cache] {title} found")

                closest_match = cached_result
            else:
                results = self.youtube.extract_info(f"ytsearch:{title}", download=False)

            if not closest_match:
                if not results:
                    raise SongNotFound(title)

                all_results = results["entries"]

                # empty response
                if not len(all_results):
                    info(f"No search results for {title}")
                    raise SongNotFound(title)

                closest_match = match_titles(results, title)
                if not closest_match:
                    info("No match found for music video version either")

                    # cache "Not found" indicating title not found
                    original_title = title + " Audio"
                    storage.new(original_title, "Not found", "ytdl")

                    raise SongNotFound(title)

        info(
            f'Found: {closest_match.get("title")}, by channel: {closest_match.get("channel")}'
        )

        storage.new(title, closest_match, "ytdl")

        id = closest_match.get("id")
        return f"https://www.youtube.com/watch?v={id}"

    def remove_odd_keywords(self, string):
        """
        Removes all occurrences of substrings from the string.

        :param string: The original string.
        :return: A new string with all specified substrings removed.
        """
        odd_keywords = [
            " [Official Audio]",
            " (Audio Visual)",
            " | Official Audio",
            " | Official",
            " (Official Audio)",
            " (Official Video)",
            " (Audio)",
            " Uncut [HD]",
            " [Video]",
            " (HD)",
            " (Official Music Video)",
            " [Official Music Video]",
            " - Topic",
            " (Official Visualizer)",
            " (Complete)",
            " (Visualizer)",
            " [Official Lyrics Video]",
        ]

        # Create a regex pattern for all substrings to remove
        pattern = compile("|".join(escape(sub) for sub in odd_keywords))

        # Replace all matches with an empty string
        return pattern.sub("", string)

    def convert_to_mp3(self, old_file: str, new_file: str, song_title: str):
        """Converts an audio file to MP3, updates the metadata, and removes the original file

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





