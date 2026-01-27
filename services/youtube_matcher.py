from __future__ import unicode_literals

from re import (
    compile,
    sub,
    escape,
    VERBOSE,
    IGNORECASE,
)
from typing import Set


DELIMITERS_PATTERN = compile(r"( x | & |\s(ft|feat|featuring)\W?)", IGNORECASE)

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
    A deterministic matcher for resolving Spotify patterns
    against YouTube video titles.
    """

    # -----------------------------
    # Normalization helpers
    # -----------------------------

    @staticmethod
    def _normalize_string(value: str) -> str:
        return sub(r"\W+", "", value).lower()

    @staticmethod
    def _normalize_artist_set(_value: str) -> Set[str]:
        """
        Convert an artist string into a normalized set of artist tokens.
        """
        value = _value.lower()
        value = DELIMITERS_PATTERN.sub(",", value)

        artists = []
        for part in value.split(","):
            cleaned = sub(r"\W+", "", part)
            if cleaned:
                artists.append(cleaned)

        return set(artists)

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
        ]

        title = title.replace("(with", "(feat.")

        odd_keywords = (
            defined_keywords + keywords_list
            if all(isinstance(k, str) for k in keywords_list)
            else defined_keywords
        )

        pattern = compile("|".join(escape(k) for k in odd_keywords), IGNORECASE)
        return pattern.sub("", title).strip()

    # -----------------------------
    # Extraction
    # -----------------------------

    @staticmethod
    def _extract_artist_title(value: str) -> tuple[str, str]:
        """
        Extract (artist, title) from:
        'Artist - Song ft. Someone'
        """
        value = YoutubeMatcher.remove_odd_keywords(value)

        if " - " not in value:
            return "", YoutubeMatcher._normalize_string(value)

        artist, title = value.split(" - ", 1)

        # strip feat info from title
        title = FEAT_PATTERN.sub("", title)
        title = sub(r"\s*\(.*?\)", "", title)
        title = title.split(" - ")[0]

        return artist.strip(), title.strip()

    # -----------------------------
    # Matching logic
    # -----------------------------

    @staticmethod
    def match_titles(pattern: str, title: str) -> bool:
        """
        Match a Spotify-style pattern against a YouTube title.
        """

        # extract raw components
        yt_artist_raw, yt_title_raw = YoutubeMatcher._extract_artist_title(title)
        sp_artist_raw, sp_title_raw = YoutubeMatcher._extract_artist_title(pattern)

        if not yt_title_raw or not sp_title_raw:
            return False

        # normalize titles
        yt_title = YoutubeMatcher._normalize_string(yt_title_raw)
        sp_title = YoutubeMatcher._normalize_string(sp_title_raw)

        print(f"\n\nYT: {yt_title}\nSP: {sp_title}\n{'#' * 30}")

        title_match_conditions = [
            yt_title == sp_title,
            yt_title in sp_title,
            sp_title in yt_title,
        ]
        title_match = any(title_match_conditions)
        print(f"title match: {title_match}")
        if not title_match:
            print(f"Lost title found!!\n{'@'*50}\n\n")

        # normalize artist sets
        yt_artists = YoutubeMatcher._normalize_artist_set(yt_artist_raw)
        sp_artists = YoutubeMatcher._normalize_artist_set(sp_artist_raw)

        print(yt_artists)
        print("*" * 10)
        print(sp_artists)

        sp_artist_in_yt = [artist in yt_artists for artist in sp_artists]
        yt_artist_in_sp = [artist in sp_artists for artist in yt_artists]
        artist_match_conditions = [
            not yt_artists,  # for yt videos without artist
            any(sp_artist_in_yt),
            any(yt_artist_in_sp),
            bool(yt_artists & sp_artists),
        ]
        artist_match = any(artist_match_conditions)
        print(f"artist match: {artist_match}")

        # -----------------------------
        # Matching rules
        # -----------------------------

        # strict match
        if title_match and artist_match:
            return True

        # controlled fallback:
        # allow title-only match ONLY if title is sufficiently unique
        if title_match and len(yt_title) > 10:
            return True

        return False

