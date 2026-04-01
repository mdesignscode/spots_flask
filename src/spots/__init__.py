from logging import getLogger
from .bootstrap.container import Container
from .models import MediaResourceSingle, SongNotFound, TitleExistsError


logger = getLogger(__name__)

class Spots:
    def __init__(self):
        self.container = Container()
        self.downloader = self.container.app.downloader

    def download(self, query: str):
        """Downloads a song

        Args:
            query (str): The query to be downloaded. Can be either a query to be searched for, or a direct Spotify or YouTube download url.
        """
        # handle direct link
        if "https://" in query:
            resolved_url = self.container.app.resolver.resolve(url=query)

            # handle single
            if isinstance(resolved_url, MediaResourceSingle):
                try:
                    self.downloader.download(video_info=resolved_url.video_info, metadata=resolved_url.metadata)
                    self.container.core.storage.save()
                except (TitleExistsError, SongNotFound) as e:
                    logger.info(e)
                    return
            else:
                playlist_info = resolved_url.playlist_info
                playlist_songs = zip(playlist_info.provider_metadata, playlist_info.youtube_metadata)

                for provider, youtube in playlist_songs:
                    try:
                        self.downloader.download(video_info=youtube, metadata=provider)
                    except (SongNotFound, TitleExistsError) as e:
                        logger.info(e)
                        continue
                self.container.core.storage.save()
        # search query
        else:
            try:
                provider_result = self.container.domain.provider_search.search_track(query)
            except SongNotFound:
                logger.info("Query not found by provider, falling back to YouTube video details.")
                provider_result = None


            search_result = self.container.domain.youtube_search.video_search(query=query, is_general_search=True)

            if search_result.is_cached:
                best_match = search_result.result[0]
            else:
                best_match = self.container.core.matcher.find_best_match(search_results=search_result.result, metadata=provider_result) if provider_result else search_result.result[0]

            metadata = provider_result if provider_result else self.container.domain.youtube_metadata.get(best_match)

            try:
                self.downloader.download(video_info=best_match, metadata=metadata)
            except (SongNotFound, TitleExistsError) as e:
                logger.info(e)
                return

            self.container.core.storage.new(query=query, result=best_match, query_type="youtube")
            self.container.core.storage.save()

    def transfer_spotify_likes(self):
        """Transfers all spotify likes to YouTube library"""
        self.container.app.youtube_user_playlist.transfer_spotify_likes_to_yt()


__all__ = ["Spots"]

