from __future__ import unicode_literals
from re import compile, sub, search, escape, VERBOSE, IGNORECASE

DELIMITERS_PATTERN = r"( x | & |\s(ft|feat|featuring)\W?)"

FEAT_PATTERN = compile(
    r"""
    (\(|\[)?              # optional opening bracket
    \b(feat|ft|featuring)\b
    [\s\.:,-]*.*           # everything after feat
    (\)|\])?               # optional closing bracket
    """,
    flags=IGNORECASE | VERBOSE,
)


class YoutubeMatcher:
    """
    A service for matching search queries to YouTube video titles

    Methods:
        @remove_odd_keywords

        @match_titles
    """

    @staticmethod
    def _extract_artist_title(value: str) -> tuple[str, str]:
        """
        Extract and normalize (artist, title) from:
        'Artist - Song ft. Someone'
        """

        normalize = lambda s: sub(r"\W+", "", s).lower()

        value = YoutubeMatcher.remove_odd_keywords(value).strip()

        if " - " not in value:
            return "", normalize(value)

        artist, title = value.split(" - ", 1)

        # remove feat / ft / featuring
        title = FEAT_PATTERN.sub("", title)

        # remove leftover parentheses
        title = sub(r"\s*\(.*?\)", "", title)
        # parenthesis equivalent of YouTube title in Spotify is `-`
        title = title.split(" - ")[0]

        return normalize(artist), normalize(title)

    @staticmethod
    def _contains_only_type(items: list, expected_type: type) -> bool:
        return all(isinstance(item, expected_type) for item in items)

    @staticmethod
    def remove_odd_keywords(title: str, keywords_list: list[str] = []) -> str:
        """
        Remove keywords that may lead to inconsistent matched results

        Args:
            title (str): The title to be processed.
            keywords_list (list[str]): An optional keywords list to filter. Defaults to an empty list.

        Returns
            str: A keyword stripped title.
        """
        defined_keywords = [
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
        ]

        title = title.replace("(with", "(feat.")

        odd_keywords = (
            defined_keywords + keywords_list
            if YoutubeMatcher._contains_only_type(keywords_list, str)
            else defined_keywords
        )

        pattern = compile("|".join(escape(k) for k in odd_keywords))
        return pattern.sub("", title)

    @staticmethod
    def _normalize_legacy(title: str, pattern: str) -> dict:
        """
        Normalize both Spotify pattern and YouTube title into comparable forms.

        Returns:
            dict: a dict containing normalized search patterns.
        """
        normalize_string = lambda s: sub(r"\W", "", s).lower()

        processed_title = YoutubeMatcher.remove_odd_keywords(title)

        # normalize delimiters
        delimiters = compile(DELIMITERS_PATTERN)
        consistent_title = delimiters.sub(", ", processed_title.lower())

        normalized_title = normalize_string(consistent_title)
        normalized_pattern = normalize_string(pattern)

        # try extracting title-only parts (after "Artist - ")
        try:
            _, yt_part = consistent_title.split(" - ", maxsplit=1)
            yt_title = normalize_string(yt_part)

            _, sp_part = pattern.split(" - ", maxsplit=1)
            spotify_title = normalize_string(sp_part)
        except ValueError:
            yt_title = normalized_title
            spotify_title = normalized_pattern

        return {
            "processed_title": processed_title,
            "spotify_title": spotify_title,
            "yt_title": yt_title,
            "normalized_pattern": normalized_pattern,
            "normalized_title": normalized_title,
        }

    @staticmethod
    def _normalize(title: str, pattern: str) -> dict:
        yt_artist, yt_title = YoutubeMatcher._extract_artist_title(title)
        sp_artist, sp_title = YoutubeMatcher._extract_artist_title(pattern)

        return {
            "yt_artist": yt_artist,
            "yt_title": yt_title,
            "sp_artist": sp_artist,
            "sp_title": sp_title,
        }

    @staticmethod
    def _match_titles(pattern: str, title: str) -> bool:
        """
        Match 2 titles

        Args:
            pattern (str): The pattern to be matched against.
            title (str): The string to match pattern with.

        Returns:
            bool: True if titles match.
        """
        norm = YoutubeMatcher._normalize(title, pattern)

        spotify_match = norm["spotify_title"] in norm["normalized_title"]
        yt_match = norm["yt_title"] in norm["normalized_pattern"]
        pattern_match = norm["normalized_pattern"] in norm["normalized_title"]
        title_match = norm["normalized_title"] in norm["normalized_pattern"]

        # extract parenthetical info (e.g. remix)
        extract_pattern = r"\s\([\w\W]*"
        pattern_title_match = search(extract_pattern, pattern)
        pattern_title = pattern_title_match.group(0) if pattern_title_match else ""
        pattern_title_matches_yt = (
            pattern_title in norm["normalized_title"] if pattern_title else False
        )

        if any(
            [
                spotify_match,
                yt_match,
                pattern_match,
                title_match,
                pattern_title_matches_yt,
            ]
        ):
            return True

        return False

    @staticmethod
    def match_titles(pattern: str, title: str) -> bool:
        norm = YoutubeMatcher._normalize(title, pattern)

        artist_match = (
            norm["yt_artist"]
            and norm["sp_artist"]
            and norm["yt_artist"] == norm["sp_artist"]
        )

        title_match = (
            norm["yt_title"]
            and norm["sp_title"]
            and norm["yt_title"] == norm["sp_title"]
        )

        partial_match = artist_match or title_match
        full_match = artist_match and title_match
        return partial_match if not all(norm.values()) else full_match

