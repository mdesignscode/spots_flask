"""Factor an object to Retrieve and Download a Youtube Video as MP3"""

from __future__ import unicode_literals
from dotenv import load_dotenv
from services.ytdlp_client import YtDlpClient
from services.youtube_search_service import YoutubeSearchService

load_dotenv()

DELIMITERS_PATTERN = r"( x | & |\s(ft|feat|featuring)\W?)"


class ProcessSpotifyLink:
    """A client that Retrieves and Download a Youtube Video as MP3

    Attributes:
        @ytdlp (YtDlpClient): YouTube DL client.
        @youtube_search (YoutubeSearchService): Service for searching videos on YouTube.
    """

    def __init__(
        self,
        ytdlp: YtDlpClient = YtDlpClient(),
        youtube_search: YoutubeSearchService = YoutubeSearchService(),
    ):
        self.ytdlp = ytdlp
        self.youtube_search = youtube_search
