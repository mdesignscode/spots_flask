from googleapiclient.errors import HttpError
from logging import error, info
from models.spotify_worker import SpotifyWorker
from models.errors import SongNotFound
from models.yt_video_info import YTVideoInfo
from services.ytdlp_client import YtDlpClient
from services.youtube_api_client import YouTubeApiClient
from services.youtube_search_service import YoutubeSearchService
from socket import timeout as SocketTimeout
from ssl import SSLEOFError
from tenacity import stop_after_attempt, wait_exponential, stop_after_delay
from engine.retry import retry


class ProcessYoutubeLink:
    def __init__(self):
        self.spotify = SpotifyWorker()
        self.ytdlp = YtDlpClient()
        self.youtube_api = YouTubeApiClient()
        self.youtube_search = YoutubeSearchService(self.ytdlp)

    def get_liked_videos(self, max_results=50):
        """
        Fetch videos from the user's YouTube liked videos playlist.
        """
        liked_videos = []
        next_page_token = None

        while True:
            request = self.youtube_api.service.playlistItems().list(
                part="snippet,contentDetails",
                playlistId="LL",
                maxResults=max_results,
                pageToken=next_page_token,
            )

            response = request.execute()

            for item in response.get("items", []):
                id = item["contentDetails"]["videoId"]
                watch_url = f"https://www.youtube.com/watch?v={id}"
                liked_videos.append(watch_url)

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        return liked_videos

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=10))
    def _like_video(self, video_id: str):
        try:
            self.youtube_api.like_video(video_id)
        except (SocketTimeout, TimeoutError) as e:
            # Retryable network error
            info(f"[Network Timeout] Retrying like for {video_id}: {e}")
            raise  # Tenacity will retry
        except HttpError as e:
            # API-level error (bad ID, auth, quota, etc.)
            info(f"[HttpError] Could not like video {video_id}: {e}")
            raise

    def like_video(self, video: YTVideoInfo, spotify_title: str) -> bool:
        """
        Attemps to add a video to YouTube likes by catching the `Requested entity was not found` error.

        Args:
            video (YTVideoInfo): the video to be added.
            spotify_title (str): the title to find a matching video for.

        Returns:
            bool: True if added to likes
        """
        video_id = video.id
        title = f"{video.uploader} - {video.title}"
        matcher = self.youtube_search.matcher
        titles_match = matcher.match_titles(
            matcher.remove_odd_keywords(spotify_title),
            matcher.remove_odd_keywords(title),
        )
        if titles_match:
            info(f"[_Like Video] {title} matched")
            try:
                info(f"[_Like Video] Trying to add {title} to likes")
                self._like_video(video_id)
                return True
            except Exception as e:
                info(f"[_Like Video] Failed to add {title} to likes")
                error(e)
                print("\n\n")
                return False

        info(f"[_Like Video] No match found for {title}")
        return False

    @retry(stop=stop_after_delay(max_delay=120))
    def _search_spotify_title(self, spotify_title: str):
        return self.ytdlp.search(spotify_title, False)

    @retry(stop=stop_after_delay(max_delay=120))
    def transfer_spotify_likes_to_yt(self):
        """
        Adds each track in a users Spotify liked library, to the users YouTube likes
        """
        from engine import storage

        # get user liked tracks from spotify
        tracks = self.spotify.user_saved_tracks()
        if not tracks:
            info("No liked tracks found on Spotify")
            raise SongNotFound("Spotify likes")

        # save newly added liked tracks
        storage.save()

        errors = []
        playlist_len = len(tracks)

        # try to find the youtube video for each track
        for index, track in enumerate(tracks):
            spotify_title = f"{track.artist} - {track.title}"
            try:
                if storage.get(spotify_title, "yt_likes"):
                    info(f"🗄 Aready Liked: {spotify_title}")
                    continue

                # get list of search_results for Audio version
                info(
                    f"🔎 [Transfer Spotify Likes To YouTube] Searching for {spotify_title} on YouTube"
                )
                video_added_to_likes = False

                # find a matching video
                info("🏗 [Transfer Spotify Likes To YouTube] Processing list of results")
                search_results = self._search_spotify_title(spotify_title)
                for video in search_results:
                    video_added_to_likes = self.like_video(video, spotify_title)
                    if video_added_to_likes:
                        break

                storage.new(spotify_title, query_type="yt_likes")
                if (index % 10 == 0) or (index == (playlist_len - 1)):
                    storage.save()

                if not video_added_to_likes:
                    info(f"Failed to add {spotify_title} to likes")
                    continue

                info(f"✅ Liked: {spotify_title}")
            except (SSLEOFError, SongNotFound) as e:
                errors.append(str(e))
            except Exception as e:
                error("Unexpected error occurred")
                storage.save()
                raise e

        storage.save()

        print(f"\n{'#' * 10}\nThe following errors occured")
        [print(e) for e in errors]

