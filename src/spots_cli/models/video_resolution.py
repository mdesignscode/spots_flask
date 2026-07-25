from dataclasses import dataclass


@dataclass
class VideoResolution:
    format_id: str
    height: int
    ext: str
    vcodec: str
    acodec: str
    fps: float | None = None
    filesize_mb: float | None = None

    @property
    def label(self) -> str:
        return f"{self.height}p"

    @property
    def is_video_only(self) -> bool:
        return self.acodec in (None, "none")
