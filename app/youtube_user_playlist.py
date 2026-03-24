from __future__ import annotations

from googleapiclient.errors import HttpError
from logging import error, info
from socket import timeout as SocketTimeout
from tenacity import stop_after_attempt, wait_exponential
from typing import TYPE_CHECKING

from engine.persistence_model import storage
from engine.retry import retry
from models import SongNotFound, YouTubeQuotaExceeded, Sentinel, YTVideoInfo, Metadata

if TYPE_CHECKING:
    from bootstrap.container import Core, Clients
    from app.spotify_playlist_compilation import SpotifyPlaylistCompilation
    from services.youtube_search_service import YoutubeSearchService


class YouTubeUserPlaylist:
    def __init__(
        self,
        *,
        clients: Clients,
        core: Core,
        spotify_playlist_compiler: SpotifyPlaylistCompilation,
        search: YoutubeSearchService,
    ):
        self.search = search
        self.core = core
        self.clients = clients
        self.spotify_playlist_compiler = spotify_playlist_compiler

    def get_liked_videos(self, *, max_results=50) -> list[str]:
        """
        Fetch videos from the user's YouTube liked videos playlist.

        Args:
            max_results (int, Optional): The max items per pagination. Defaults to 50.
        """
        liked_videos = []
        next_page_token = None

        while True:
            request = self.clients.youtube.service.playlistItems().list(
                part="snippet,contentDetails",
                playlistId="LL",
                maxResults=max_results,
                pageToken=next_page_token,
            )

            response = request.execute()

            for item in response.get("items", []):
                video_id = item["contentDetails"]["videoId"]
                watch_url = f"https://www.youtube.com/watch?v={video_id}"
                liked_videos.append(watch_url)

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        return liked_videos

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=10))
    def _like_video(self, video_id: str):
        """
        Like a video with retry on transient failures.

        Args:
            video_id (str): the id of the video to be added.
        """
        try:
            self.clients.youtube.service.videos().rate(
                id=video_id, rating="like"
            ).execute()
        except (SocketTimeout, TimeoutError) as e:
            # Retryable network error
            info(f"[Network Timeout] Retrying like for {video_id}: {e}")
            raise  # Tenacity will retry
        except HttpError as e:
            # API-level error (bad ID, auth, quota, etc.)
            raise

    def like_video(self, *, video: YTVideoInfo, metadata: Metadata) -> bool:
        """
        Adds a video to YouTube likes.

        Args:
            video (YTVideoInfo): the video to be added.
            metadata (Metadata): the metadata for the video.

        Returns:
            bool: True if added to likes
        """
        video_id = video.id
        title = f"{video.uploader} - {video.title}"
        titles_match = self.core.matcher.match_tracks(
            video_info=video, metadata=metadata
        )
        if titles_match:
            try:
                info(f"Trying to add {title} to likes")
                self._like_video(video_id)
                return True
            except HttpError as e:
                status = getattr(e.resp, "status", None)
                details = getattr(e, "error_details", None)
                if status == 403 and isinstance(details, list) and details:
                    reason = details[0].get("reason")

                    if reason == "videoRatingDisabled":
                        return False
                    elif reason == "quotaExceeded":
                        raise YouTubeQuotaExceeded()
                    else:
                        error("Unexpected reason:")
                        error(reason)
                        raise
                raise
            except Exception as e:
                raise

        info(f"No match found for {title}")
        return False

    def transfer_spotify_likes_to_yt(self):
        """
        Adds each track in a users Spotify liked library, to the users YouTube likes
        """
        # get user liked tracks from spotify
        tracks = self.spotify_playlist_compiler.user_saved_tracks()

        # save newly added liked tracks
        storage.save()

        unexpected_errors = []
        playlist_len = len(tracks.provider_metadata)

        # try to find the youtube video for each track
        for index, track in enumerate(tracks.provider_metadata):
            spotify_title = f"{track.artist} - {track.title}"

            if storage.get(query=spotify_title, query_type="yt_likes"):
                info(f"🗄 Already Liked: {spotify_title}")
                continue

            video_added_to_likes = False

            try:
                search_results = self.search.video_search(
                    query=spotify_title, is_general_search=True
                )
            except SongNotFound:
                continue
            except Exception as e:
                unexpected_errors.append(str(e))
                continue

            try:
                best_match = self.core.matcher.find_best_match(
                    search_results=search_results.result, metadata=track
                )
                video_added_to_likes = self.like_video(video=best_match, metadata=track)
                if video_added_to_likes:
                    storage.new(
                        query=spotify_title,
                        result=best_match,
                        query_type="yt_likes",
                    )
                else:
                    info(f"Failed to add {spotify_title} to likes")
                    storage.new(
                        query=spotify_title, result=Sentinel(), query_type="yt_likes"
                    )
                    continue
            except SongNotFound:
                continue
            except YouTubeQuotaExceeded:
                storage.save()
                error("Quota exceeded")
                raise
            except Exception as e:
                unexpected_errors.append(str(e))
                continue

            if (index % 10 == 0) or (index == (playlist_len - 1)):
                storage.save()

            info(f"✅ Liked: {spotify_title}")

        storage.save()

        if len(unexpected_errors):
            error("Unexpected errors occurred")
            for unexpected in unexpected_errors:
                error(unexpected)
