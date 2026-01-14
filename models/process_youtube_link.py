from models.spotify_worker import SpotifyWorker
from services.ytdlp_client import YtDlpClient
from services.youtube_api_client import YouTubeApiClient
from services.youtube_search_service import YoutubeSearchService
from logging import basicConfig, info, INFO


basicConfig(level=INFO)


class ProcessYoutubeLink:
    def __init__(self):
        self.spotify = SpotifyWorker()
        self.ytdlp = YtDlpClient()
        self.youtube_api = YouTubeApiClient()
        self.youtube_search = YoutubeSearchService(self.ytdlp)

    def transfer_spotify_likes_to_yt(self):
        tracks = self.spotify.user_saved_tracks()
        if not tracks:
            return

        for track in tracks:
            query = f"{track.artist} - {track.title}"
            yt_url = self.youtube_search.search_best_match(track, query)
            if not yt_url:
                info(f"❌Query {query} not found")
                continue
            video_id = yt_url.split("v=")[1]

            self.youtube_api.like_video(video_id)
            info(f"✅ Liked: {query}")
