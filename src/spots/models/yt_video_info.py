from dataclasses import dataclass
from models.helper_models import ArtistAndTitle


@dataclass
class YTVideoInfo:
    id: str
    title: str
    uploader: str
    audio_ext: str
    filesize: int

    @property
    def video_link(self):
        return f"https://youtube.com.watch?v={self.id}"

    @property
    def full_title(self):
        return f"{self.uploader} - {self.title}"

    @full_title.setter
    def full_title(self, artist_and_title: ArtistAndTitle):
        self.uploader = artist_and_title.artist
        self.title = artist_and_title.title

