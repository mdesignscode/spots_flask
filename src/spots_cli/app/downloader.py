from __future__ import annotations

from hashlib import md5
from os.path import join, exists
from pathlib import Path
from typing import TYPE_CHECKING

from spots_cli.models import TitleExistsError, Metadata, VideoResolution, YTVideoInfo

if TYPE_CHECKING:
    from spots_cli.bootstrap.container import Core, Clients


class Downloader:
    """A service for interacting with YouTube."""

    def __init__(self, *, core: Core, clients: Clients):
        self.core = core
        self.clients = clients

    def download(
        self, *, video_info: YTVideoInfo, metadata: Metadata, directory_path: str = ""
    ) -> bool:
        """Downloads a YouTube video as mp3

        Args:
            video_info (YTVideoInfo): the extracted info.
            directory_path (str, Optional): the folder to be downloaded to. Defaults to the root of the Music folder.

        Returns:
            bool: True if downloaded successfully.
        """
        url = "https://youtube.com/watch?v=" + video_info.id
        title = f"{video_info.uploader} - {video_info.title}"

        # normalize title
        # '/' will read file name as folder in *nix systems
        filename = title.replace("/", "|")
        # Check if the file name length is too long, truncate if necessary
        max_filename_length = 255  # Maximum allowed file name length on most systems
        if len(filename) > max_filename_length:
            file_hash = md5(filename.encode()).hexdigest()
            filename = file_hash[:25]

        # check if downloaded already
        if self.core.history.read(filename):
            raise TitleExistsError(filename)

        download_folder = Path.home() / "Downloads"
        download_folder = download_folder if exists(
            download_folder) else Path.home()

        download_path = join(
            download_folder, directory_path, f"{
                filename}.{video_info.audio_ext}"
        )
        converted_path = join(
            download_folder, directory_path, f"{filename}.mp3")

        # set template for download titles
        self.clients.ytdlp.options = {"outtmpl": download_path}

        # download video
        self.clients.ytdlp.client.download([url])

        self.clients.ytdlp.reset_options()

        # post download processing
        converted = self.core.converter.convert_to_mp3(
            old_file=download_path, new_file=converted_path
        )
        if converted:
            metadata_updated = self.core.converter.update_metadata(
                audio_path=converted_path, metadata=metadata
            )
            if metadata_updated:
                self.core.history.write(filename)
        else:
            return False

        return True

    def get_available_resolutions(
        self, *, video_info: YTVideoInfo
    ) -> dict[str, VideoResolution]:
        """
        Detects all available video resolutions for a YouTube video.

        Args:
            video_info (YTVideoInfo): the extracted video info (only .id is used
                to look up the video).

        Returns:
            dict[str, VideoResolution]: maps a resolution label (e.g. "1080p")
                to a VideoResolution describing the best available format at
                that resolution. filesize_mb is reported in megabytes (MB).
                Most high-resolution formats are video-only (acodec == "none");
                download_video automatically merges in the best available audio
                track for those.
        """
        url = f"https://youtube.com/watch?v={video_info.id}"

        self.clients.ytdlp.options = {"quiet": True, "noplaylist": True}
        try:
            info = self.clients.ytdlp.client.extract_info(url, download=False)
        finally:
            self.clients.ytdlp.reset_options()

        all_formats = info.get("formats", [])

        # Estimate the size of the audio track yt-dlp will pick for "bestaudio",
        # so video-only formats can report a total (video + audio) download size
        # instead of just the video stream's size.
        best_audio_bytes = 0
        best_audio_abr = -1.0
        for fmt in all_formats:
            is_audio_only = fmt.get("vcodec") in (None, "none") and fmt.get(
                "acodec"
            ) not in (None, "none")
            if not is_audio_only:
                continue
            abr = fmt.get("abr") or 0
            if abr > best_audio_abr:
                best_audio_abr = abr
                best_audio_bytes = (
                    fmt.get("filesize") or fmt.get("filesize_approx") or 0
                )

        resolutions: dict[str, VideoResolution] = {}
        for fmt in all_formats:
            height = fmt.get("height")
            # skip audio-only formats and formats with no video track
            if not height or fmt.get("vcodec") in (None, "none"):
                continue

            label = f"{height}p"
            is_video_only = fmt.get("acodec") in (None, "none")
            video_bytes = fmt.get("filesize") or fmt.get(
                "filesize_approx") or 0
            # video-only formats get merged with bestaudio on download, so
            # reflect that in the reported size; progressive formats already
            # include audio in their own filesize.
            total_bytes = video_bytes + best_audio_bytes if is_video_only else video_bytes

            existing = resolutions.get(label)
            existing_bytes = (existing.filesize_mb or 0) * \
                1024 * 1024 if existing else -1

            # keep the best-quality format available for each resolution
            if not existing or total_bytes > existing_bytes:
                resolutions[label] = VideoResolution(
                    format_id=fmt.get("format_id"),
                    height=height,
                    ext=fmt.get("ext"),
                    vcodec=fmt.get("vcodec"),
                    acodec=fmt.get("acodec"),
                    fps=fmt.get("fps"),
                    filesize_mb=(
                        round(total_bytes / (1024 * 1024),
                              2) if total_bytes else None
                    ),
                )

        return resolutions

    def download_video(
        self,
        *,
        video_info: YTVideoInfo,
        resolution: VideoResolution,
        directory_path: str = "",
    ) -> bool:
        """
        Downloads a specific resolution of a YouTube video.

        Args:
            video_info (YTVideoInfo): the extracted info.
            resolution (VideoResolution): one of the *values* returned by
                get_available_resolutions(), e.g. resolutions["1080p"].
            directory_path (str, Optional): the folder to be downloaded to.
        """
        format_id = resolution.format_id
        if not format_id:
            raise ValueError(
                "resolution must be a VideoResolution returned from "
                "get_available_resolutions() (missing 'format_id')"
            )

        url = f"https://youtube.com/watch?v={video_info.id}"
        title = f"{video_info.uploader} - {video_info.title}"
        filename = title.replace("/", "|")

        download_folder = Path.home() / "Downloads"
        download_folder = download_folder if exists(
            download_folder) else Path.home()
        download_path = join(download_folder, directory_path, f"{
                             filename}.%(ext)s")

        # video-only formats (common at higher resolutions) need audio merged in
        format_selector = (
            f"{format_id}+bestaudio/best" if resolution.is_video_only else format_id
        )

        self.clients.ytdlp.options = {
            "outtmpl": download_path,
            "format": format_selector,
            "merge_output_format": "mp4",
            "postprocessors": [
                {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
            ],
        }

        try:
            self.clients.ytdlp.client.download([url])
        finally:
            self.clients.ytdlp.reset_options()

        return True
