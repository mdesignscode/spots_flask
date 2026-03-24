from __future__ import unicode_literals, annotations

from re import compile, sub, IGNORECASE, VERBOSE

from engine.persistence_model import storage
from models.errors import SongNotFound
from models.sentinel import Sentinel
from models.yt_video_info import YTVideoInfo
from models.metadata import Metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.youtube_extractor import YouTubeExtractor

# -----------------------------
# regex
# -----------------------------

FEAT_PATTERN = compile(
    r"""
    (\(|\[)?                  # optional opening bracket
    \b(feat|ft|featuring)\b
    [\s\.:,-]*.*               # everything after feat
    (\)|\])?                  # optional closing bracket
    """,
    flags=IGNORECASE | VERBOSE,
)

NON_WORD_PATTERN = compile(r"\W+")

# -----------------------------
# constants
# -----------------------------

STOPWORDS = {
    "official",
    "audio",
    "video",
    "lyrics",
    "lyric",
    "visualizer",
    "remix",
    "version",
    "edit",
    "hd",
    "explicit",
    "clean",
    "topic",
}

BAD_UPLOADER_KEYWORDS = {
    "karaoke",
    "lyrics",
    "remastered",
    "mashup",
    "nightcore",
    "slowed",
    "reverb",
    "8d",
    "cover",
}

# -----------------------------
# helpers
# -----------------------------


def strip_features(text: str) -> str:
    return sub(FEAT_PATTERN, "", text)


def tokenize(text: str) -> set[str]:
    text = text.lower()
    text = strip_features(text)
    tokens = NON_WORD_PATTERN.sub(" ", text).split()
    return {t for t in tokens if t not in STOPWORDS}


def token_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a), len(b))


def uploader_penalty(uploader: str) -> float:
    uploader = uploader.lower()
    return 0.35 if any(k in uploader for k in BAD_UPLOADER_KEYWORDS) else 0.0


def artist_in_title_or_uploader(
    sp_artist: str, yt_title: str, yt_uploader: str
) -> bool:
    sp_tokens = tokenize(sp_artist)
    yt_tokens = tokenize(yt_title) | tokenize(yt_uploader)
    return bool(sp_tokens & yt_tokens)


# -----------------------------
# matcher
# -----------------------------


class PatternMatcher:
    TITLE_THRESHOLD = 0.50
    ARTIST_THRESHOLD = 0.40
    FINAL_THRESHOLD = 0.60

    def __init__(self, *, extractor: YouTubeExtractor):
        self.extractor = extractor

    def match_tracks(self, *, video_info: YTVideoInfo, metadata: Metadata) -> bool:
        yt_artist = video_info.uploader or ""
        yt_title = video_info.title or ""

        sp_artist = metadata.artist or ""
        sp_title = metadata.title or ""
        # Artist - Title ft Artsit two
        # [artist, title, artist two]

        yt_title_tokens = tokenize(yt_title)
        sp_title_tokens = tokenize(sp_title)

        yt_artist_tokens = tokenize(yt_artist)
        sp_artist_tokens = tokenize(sp_artist)

        title_score = token_similarity(yt_title_tokens, sp_title_tokens)
        artist_score = token_similarity(yt_artist_tokens, sp_artist_tokens)

        penalty = uploader_penalty(yt_artist)

        final_score = 0.6 * title_score + 0.3 * artist_score - penalty

        title_dominant_match = title_score >= 0.60 and artist_in_title_or_uploader(
            sp_artist, yt_title, yt_artist
        )

        score_based_match = final_score >= self.FINAL_THRESHOLD and (
            title_score >= self.TITLE_THRESHOLD or artist_score >= self.ARTIST_THRESHOLD
        )

        is_match = title_dominant_match or score_based_match

        return is_match

    def find_best_match(
        self, *, search_results: list[YTVideoInfo], metadata: Metadata
    ) -> YTVideoInfo:
        query = f"{metadata.artist} - {metadata.title}"
        cache = storage.get(query=query, query_type="youtube")
        if cache:
            return cache

        for result in search_results:
            title_and_artist = self.extractor.extract_artist_and_title(
                video_info=result, metadata=metadata
            )
            result.full_title = title_and_artist
            if self.match_tracks(video_info=result, metadata=metadata):
                storage.new(query=query, result=result, query_type="youtube")
                return result

        storage.new(query=query, result=Sentinel(), query_type="youtube")
        raise SongNotFound(query)

