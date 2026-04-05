from html import unescape
from unicodedata import normalize
from re import compile, escape, IGNORECASE, search, sub, split

from spots_cli.models.yt_video_info import YTVideoInfo
from spots_cli.models.metadata import Metadata
from spots_cli.models.helper_models import ArtistAndTitle


class YouTubeExtractor:
    """A service for extracting data from a YouTubeVideoInfo"""

    @staticmethod
    def remove_odd_keywords(title: str, keywords_list: list[str] = []) -> str:
        defined_keywords = [
            " (Live Session) | Vevo Ctrl",
            " [Official Audio]",
            " (Audio Visual)",
            " | Official Audio",
            " | Official",
            " (Official Audio)",
            " (Official Video)",
            " (Audio)",
            " Uncut [HD]",
            " [Video]",
            " (HD)",
            " (Official Music Video)",
            " [Official Music Video]",
            " - Topic",
            " (Official Visualizer)",
            " (Complete)",
            " (Visualizer)",
            " [Official Lyrics Video]",
            " (Lyric Video)",
            " (Lyrics)",
            " (Official HD Video)",
            " (Audio Oficial)",
            " Official Music Video",
            " [Official Video]",
            " - Official Video",
            " (Original Video)",
            "(LYRICS+PICTURES)",
            " [Lyrics]",
            " HQ",
            " - Audio",
            " (Album Version)",
            " (Clean Version)",
        ]

        title = title.replace("(with", "(feat.")

        odd_keywords = (
            defined_keywords + keywords_list
            if all(isinstance(k, str) for k in keywords_list)
            else defined_keywords
        )

        pattern = compile("|".join(escape(k) for k in odd_keywords), flags=IGNORECASE)
        return pattern.sub("", title).strip()

    @staticmethod
    def normalize_special_chars(text: str) -> str:
        return (
            normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
            .replace("–", "-")
            .strip()
        )

    def extract_artist_and_title(
        self, *, video_info: YTVideoInfo, metadata: Metadata
    ) -> ArtistAndTitle:
        """Extracts the title and artist from a YouTube search result.

        Args:
            video_info (YTVideoInfo): The search result object to be processed.

        Returns:
            ArtistAndTitle: The extracted title and artist.
        """
        # Decode the string
        try:
            video_title = unescape(video_info.title)
        except TypeError:
            video_title = video_info.title

        # normalize tokens
        normalized_yt_artist = self.normalize_special_chars(video_info.uploader)
        normalized_yt_title = self.normalize_special_chars(video_title)
        normalized_sp_artist = self.normalize_special_chars(metadata.artist)

        title_parts = split(r"\s*[-|:•]\s*|\s{2,}", normalized_yt_title, maxsplit=1)

        ARTIST_CANDIDATES = [normalized_yt_artist.strip()] + title_parts

        def recursive_artist_search(pattern: str, index: int):
            if search(escape(pattern), normalized_sp_artist, flags=IGNORECASE):
                return pattern, index
            if index == (len(ARTIST_CANDIDATES) - 1):
                return video_info.uploader, 0
            next_index = index + 1
            return recursive_artist_search(ARTIST_CANDIDATES[next_index], next_index)

        _, uploader_index = recursive_artist_search(ARTIST_CANDIDATES[0], 0)

        match uploader_index:
            case 0:
                # artist is uploader
                youtube_artist, youtube_title = video_info.uploader, video_title

                # check for artist repeat in title
                if normalized_yt_artist in normalized_yt_title:
                    artist_pattern = compile(rf"{youtube_artist}\W?", flags=IGNORECASE)
                    youtube_title = sub(artist_pattern, "", video_title)

                    # strip title
                    youtube_title = sub(r"\W", "", youtube_title, count=1)
                    youtube_title = youtube_title
            case 1:
                # different uploader, artist in title
                pattern = rf"{escape(metadata.artist)}\W"
                pattern_match = search(pattern, video_title)

                if pattern_match:
                    # strip artist
                    youtube_artist = pattern_match.group(0)
                    rev_artist = youtube_artist[::-1]
                    youtube_artist = sub(r"\W", "", rev_artist, count=1)
                    youtube_artist = youtube_artist[::-1]

                    # strip title
                    youtube_title = video_title[pattern_match.end() :]
                    youtube_title = sub(r"\W", "", youtube_title, count=1)
                else:
                    youtube_artist, youtube_title = video_info.uploader, video_title
            case _:
                # different uploader, artist and title reversed
                pattern = rf"\W{escape(self.normalize_special_chars(metadata.artist))}"
                pattern_match = search(pattern, video_title, flags=IGNORECASE)

                if pattern_match:
                    # strip artist
                    youtube_artist = pattern_match.group(0)
                    youtube_artist = sub(r"\W", "", youtube_artist, count=1)

                    # strip title
                    youtube_title = video_title[: pattern_match.start()]
                    rev_title = youtube_title[::-1]
                    youtube_title = sub(r"\W", "", rev_title, count=1)
                    youtube_title = youtube_title[::-1]
                else:
                    youtube_artist, youtube_title = video_info.uploader, video_title

        youtube_title = youtube_title.rstrip(" |–-")
        youtube_title = self.remove_odd_keywords(youtube_title)
        youtube_artist = self.remove_odd_keywords(youtube_artist)

        return ArtistAndTitle(
            artist=youtube_artist.strip(), title=youtube_title.strip()
        )
