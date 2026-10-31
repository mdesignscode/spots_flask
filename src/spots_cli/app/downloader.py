from __future__ import annotations

from hashlib import md5
from os.path import join, exists
from pathlib import Path
from typing import TYPE_CHECKING

from spots_cli.models import (
    ResolutionUnavailable,
    TitleExistsError,
    Metadata,
    VideoResolution,
    YTVideoInfo,
)

if TYPE_CHECKING:
    from spots_cli.bootstrap.container import Core, Clients


class Downloader:
    """A service for interacting with YouTube."""

    def __init__(self, *, core: Core, clients: Clients):
        self.core = core
        self.clients = clients

    @staticmethod
    def _filename(video_info: YTVideoInfo) -> str:
        """A file-system safe name for a video: "Uploader - Title"."""
        # '/' will read file name as folder in *nix systems
        filename = video_info.full_title.replace("/", "|")
        # Check if the file name length is too long, truncate if necessary
        max_filename_length = 255  # Maximum allowed file name length on most systems
        if len(filename) > max_filename_length:
            filename = md5(filename.encode()).hexdigest()[:25]
        return filename

    @staticmethod
    def _download_folder(directory_path: str) -> str:
        """The folder downloads are saved to: ~/Downloads (or ~), plus directory_path."""
        download_folder = Path.home() / "Downloads"
        if not exists(download_folder):
            download_folder = Path.home()
        return join(download_folder, directory_path)

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
        url = video_info.video_link
        filename = self._filename(video_info)

        # check if downloaded already
        if self.core.history.read(filename):
            raise TitleExistsError(filename)

        folder = self._download_folder(directory_path)
        download_path = join(folder, f"{filename}.{video_info.audio_ext}")
        converted_path = join(folder, f"{filename}.mp3")

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
        url = video_info.video_link

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

    @staticmethod
    def pick_resolution(
        resolutions: dict[str, VideoResolution], label: str | None = None
    ) -> VideoResolution:
        """
        Chooses one resolution from get_available_resolutions().

        Args:
            resolutions: the available resolutions, keyed by label.
            label (str, Optional): e.g. "720p" (a bare "720" is accepted too).
                Defaults to the highest resolution available.

        Raises:
            ResolutionUnavailable: no resolutions, or `label` is not among them.
        """
        by_height = sorted(resolutions.values(), key=lambda r: r.height)
        available = [r.label for r in by_height]

        if label is None:
            if not by_height:
                raise ResolutionUnavailable("best", available)
            return by_height[-1]

        wanted = label.strip().lower()
        if not wanted.endswith("p"):
            wanted += "p"
        if wanted not in resolutions:
            raise ResolutionUnavailable(wanted, available)
        return resolutions[wanted]

    def download_video(
        self,
        *,
        video_info: YTVideoInfo,
        resolution: VideoResolution | str | None = None,
        directory_path: str = "",
    ) -> str:
        """
        Downloads a YouTube video as mp4 at a chosen resolution.

        Args:
            video_info (YTVideoInfo): the extracted info.
            resolution (VideoResolution | str, Optional): one of the values
                returned by get_available_resolutions(), a label such as
                "1080p", or None for the highest resolution available.
            directory_path (str, Optional): the folder to be downloaded to.

        Returns:
            str: the path of the downloaded file.

        Raises:
            ResolutionUnavailable: the requested label is not offered.
        """
        if not isinstance(resolution, VideoResolution):
            resolution = self.pick_resolution(
                self.get_available_resolutions(video_info=video_info), resolution
            )

        url = video_info.video_link
        download_path = join(
            self._download_folder(directory_path),
            f"{self._filename(video_info)}.%(ext)s",
        )

        # video-only formats (common at higher resolutions) need audio merged in
        format_selector = (
            f"{resolution.format_id}+bestaudio/best"
            if resolution.is_video_only
            else resolution.format_id
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
            info = self.clients.ytdlp.client.extract_info(url, download=True)
        finally:
            self.clients.ytdlp.reset_options()

        return info["requested_downloads"][-1]["filepath"]
