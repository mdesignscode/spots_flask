from __future__ import annotations

from logging import getLogger
from os.path import exists

from .bootstrap.container import Container
from .models import (
    MediaResourceSingle,
    SongNotFound,
    TitleExistsError,
    InvalidSearchFormat,
    InvalidURL,
    ResolutionUnavailable,
)

logger = getLogger(__name__)


class Spots:
    def __init__(self):
        from spots_cli.setup_env import main as setup, FILENAME as setup_file

        if not exists(setup_file):
            setup()

        self.container = Container()
        self.downloader = self.container.app.downloader

    def download(self, query: str):
        """Downloads a song

        Args:
            query (str): The query to be downloaded. Can be either a query to be searched for, or a direct Spotify or YouTube download url.
        """
        # handle direct link
        if "https://" in query:
            logger.info(f"Processing url: {query}")
            try:
                resolved_url = self.container.app.resolver.resolve(url=query)
            except InvalidURL as e:
                logger.info(e)
                return

            # handle single
            if isinstance(resolved_url, MediaResourceSingle):
                try:
                    logger.info(f"{query} found, downloading now...")
                    self.downloader.download(
                        video_info=resolved_url.video_info,
                        metadata=resolved_url.metadata,
                    )
                    self.container.core.storage.save()
                except (TitleExistsError, SongNotFound) as e:
                    logger.info(e)
                    return
            else:
                playlist_info = resolved_url.playlist_info
                playlist_songs = zip(
                    playlist_info.provider_metadata, playlist_info.youtube_metadata
                )

                for index, [provider, youtube] in enumerate(playlist_songs):
                    logger.info(
                        f"Processing song: {index + 1}/{len(playlist_info.provider_metadata)}"
                    )
                    try:
                        self.downloader.download(video_info=youtube, metadata=provider)
                    except (SongNotFound, TitleExistsError) as e:
                        logger.info(e)
                        continue
                self.container.core.storage.save()
        # search query
        else:
            try:
                logger.info(f"Searching for {query}...")
                provider_result = self.container.domain.provider_search.search_track(
                    query
                )
            except SongNotFound:
                logger.debug(
                    "Query not found by provider, falling back to YouTube video details."
                )
                provider_result = None
            except InvalidSearchFormat as e:
                logger.error(e)
                return

            search_result = self.container.domain.youtube_search.video_search(
                query=query, is_general_search=True
            )

            if search_result.is_cached:
                best_match = search_result.result[0]
            else:
                best_match = (
                    self.container.core.matcher.find_best_match(
                        search_results=search_result.result, metadata=provider_result
                    )
                    if provider_result
                    else search_result.result[0]
                )

            metadata = (
                provider_result
                if provider_result
                else self.container.domain.youtube_metadata.get(best_match)
            )

            try:
                logger.info(f"{query} found, downloading now...")
                self.downloader.download(video_info=best_match, metadata=metadata)
            except (SongNotFound, TitleExistsError) as e:
                logger.info(e)

            self.container.core.storage.new(
                query=query, result=best_match, query_type="youtube"
            )
            self.container.core.storage.save()

    def download_video(
        self, query: str, resolution: str | None = None, directory_path: str = ""
    ) -> str | None:
        """Downloads a YouTube video as mp4

        Args:
            query (str): A YouTube video url, or search terms (the top result is used).
            resolution (str, Optional): e.g. "720p". Defaults to the highest available.
            directory_path (str, Optional): sub-folder of the downloads folder.

        Returns:
            str | None: the downloaded file's path, or None if nothing was downloaded.
        """
        is_url = query.startswith(("http://", "https://"))

        try:
            logger.info(f"Searching for {query}...")
            search = self.container.domain.youtube_search.video_search(
                query=query, is_general_search=not is_url
            )
            video = search.result if is_url else search.result[0]

            logger.info(f"Downloading {video.full_title}...")
            path = self.downloader.download_video(
                video_info=video, resolution=resolution, directory_path=directory_path
            )
        except (SongNotFound, ResolutionUnavailable) as e:
            logger.error(e)
            return None
        finally:
            self.container.core.storage.save()

        logger.info(f"Saved to {path}")
        return path

    def transfer_spotify_likes(self):
        """Transfers all spotify likes to YouTube library"""
        try:
            self.container.app.youtube_user_playlist.transfer_spotify_likes_to_yt()
        except SongNotFound:
            logger.info("No liked songs found.")

    def download_spotify_likes(self):
        """Downloads all Spotify likes"""
        try:
            self.container.app.youtube_user_playlist.transfer_spotify_likes_to_yt()
        except SongNotFound:
            logger.info("No liked songs found.")


__all__ = ["Spots"]
