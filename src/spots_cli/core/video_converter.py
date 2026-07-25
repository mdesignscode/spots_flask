from logging import getLogger
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC, TIT2, TPE1, TRCK, TALB, USLT, TDRL
from mutagen.mp3 import MP3
from os import remove
from os.path import abspath
from requests import get

from spots_cli.models.metadata import Metadata

logger = getLogger(__name__)


class VideoConverter:
    """
    Service responsible for converting audio/video files to MP3/MP4 format
    and updating their metadata.

    Attributes:
        @add_to_history (AddToHistoryService): Service for adding downloaded songs to history.

    Methods:
        @update_metadata

        @convert_to_mp3

        @convert_to_mp4

    This service handles:
    - Converting audio files to MP3
    - Converting video files to MP4
    - Updating ID3 metadata (title, artist, album, cover art, lyrics, etc.)
    - Removing the original file after conversion
    - Adding successful downloads to the download history
    """

    def update_metadata(self, *, audio_path: str, metadata: Metadata) -> bool:
        """
        Update the ID3 metadata of an MP3 file.

        Existing ID3 tags are removed and replaced with new ones
        based on the provided metadata.

        Args:
            audio_path (str): Path to the MP3 file whose metadata will be updated.
            metadata (Metadata): Metadata object containing song information.

        Raises:
            FileNotFoundError: If the audio file does not exist.
        """
        logger.debug("Updating metadata")

        try:
            audio = MP3(audio_path, ID3=ID3)

            # Remove existing ID3 tags
            audio.tags = None

            # Create new ID3 tags
            audio.tags = ID3()

            # Set basic metadata
            audio.tags.add(TIT2(encoding=3, text=metadata.title))
            audio.tags.add(TPE1(encoding=3, text=metadata.artist))
            audio.tags.add(TRCK(encoding=3, text=metadata.tracknumber))
            audio.tags.add(TALB(encoding=3, text=metadata.album))

            # Handle cover art
            cover = metadata.cover
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
            if metadata.lyrics:
                audio.tags.add(
                    USLT(
                        encoding=3,
                        lang="eng",
                        desc="",
                        text=metadata.lyrics,
                    )
                )

            # Add release date if provided
            if metadata.release_date:
                audio.tags.add(
                    TDRL(
                        encoding=3,
                        text=metadata.release_date,
                    )
                )

            # Save changes
            audio.save(audio_path)

            return True

        except FileNotFoundError as exc:
            logger.error(f"{audio_path} not found...")
            raise exc

    def convert_to_mp3(
        self,
        *,
        old_file: str,
        new_file: str,
    ) -> bool:
        """
        Convert an audio file to MP3 format and update its metadata.

        This method:
        - Converts the input audio file to MP3
        - Deletes the original file
        - Updates the MP3 metadata
        - Adds the song to the download history on success

        Args:
            old_file (str): Path to the source audio file.
            new_file (str): Path where the converted MP3 file will be saved.
            song_title (str): Song title to be added to the download history.
            metadata (Metadata): Metadata to apply to the converted MP3 file.

        Returns:
            bool: True indicates a successful download
        """
        try:
            # Load the audio clip
            clip = AudioFileClip(old_file)

            # Convert and save as MP3
            clip.write_audiofile(new_file, codec="mp3")

            # Clean up resources
            clip.close()
            remove(old_file)

            return True

        except FileNotFoundError:
            logger.error(f"{old_file} not found...")
            return False

    def convert_to_mp4(
        self,
        *,
        old_file: str,
        new_file: str,
    ) -> bool:
        """
        Convert a video file to MP4 format.

        This method:
        - Converts the input video file to MP4 (H.264 video / AAC audio)
        - Deletes the original file once conversion succeeds, unless the
          source and destination paths are the same

        Args:
            old_file (str): Path to the source video file.
            new_file (str): Path where the converted MP4 file will be saved.

        Returns:
            bool: True indicates a successful conversion.
        """
        try:
            # Load the video clip
            clip = VideoFileClip(old_file)

            # Convert and save as MP4
            clip.write_videofile(new_file, codec="libx264", audio_codec="aac")

            # Clean up resources
            clip.close()
            if abspath(old_file) != abspath(new_file):
                remove(old_file)

            return True

        except FileNotFoundError:
            logger.error(f"{old_file} not found...")
            return False
