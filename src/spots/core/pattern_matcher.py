from __future__ import unicode_literals, annotations

from logging import getLogger
from re import compile, sub, IGNORECASE, VERBOSE
from typing import TYPE_CHECKING

from spots.engine import storage
from spots.models import SongNotFound, Sentinel, YTVideoInfo, Metadata

if TYPE_CHECKING:
    from spots.core import YouTubeExtractor

# -----------------------------
# logging setup
# -----------------------------

logger = getLogger(__name__)

# -----------------------------
# regex
# -----------------------------

FEAT_PATTERN = compile(
    r"""
    (\(|\[)?
    \b(feat|ft|featuring)\b
    [\s\.:,-]*.*
    (\)|\])?
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
    cleaned = sub(FEAT_PATTERN, "", text)
    logger.debug("strip_features: '%s' -> '%s'", text, cleaned)
    return cleaned


def tokenize(text: str) -> set[str]:
    original = text
    text = text.lower()
    text = strip_features(text)
    tokens = NON_WORD_PATTERN.sub(" ", text).split()
    filtered = {t for t in tokens if t not in STOPWORDS}

    logger.debug(
        "tokenize: original='%s', tokens=%s, filtered=%s",
        original,
        tokens,
        filtered,
    )

    return filtered


def token_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        logger.debug("token_similarity: empty tokens -> 0.0")
        return 0.0

    score = len(a & b) / max(len(a), len(b))
    logger.debug("token_similarity: %s vs %s -> %.3f", a, b, score)
    return score


def uploader_penalty(uploader: str) -> float:
    uploader_lower = uploader.lower()
    penalty = 0.35 if any(k in uploader_lower for k in BAD_UPLOADER_KEYWORDS) else 0.0

    logger.debug("uploader_penalty: '%s' -> %.2f", uploader, penalty)
    return penalty


def artist_in_title_or_uploader(
    sp_artist: str, yt_title: str, yt_uploader: str
) -> bool:
    sp_tokens = tokenize(sp_artist)
    yt_tokens = tokenize(yt_title) | tokenize(yt_uploader)
    result = bool(sp_tokens & yt_tokens)

    logger.debug(
        "artist_in_title_or_uploader: sp=%s, yt=%s -> %s",
        sp_tokens,
        yt_tokens,
        result,
    )

    return result


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

        logger.debug(
            "Matching track: YT(title='%s', uploader='%s') vs SP(title='%s', artist='%s')",
            yt_title,
            yt_artist,
            sp_title,
            sp_artist,
        )

        yt_title_tokens = tokenize(yt_title)
        sp_title_tokens = tokenize(sp_title)

        yt_artist_tokens = tokenize(yt_artist)
        sp_artist_tokens = tokenize(sp_artist)

        title_score = token_similarity(yt_title_tokens, sp_title_tokens)
        artist_score = token_similarity(yt_artist_tokens, sp_artist_tokens)

        penalty = uploader_penalty(yt_artist)

        final_score = 0.6 * title_score + 0.3 * artist_score - penalty

        logger.debug(
            "Scores -> title: %.3f, artist: %.3f, penalty: %.2f, final: %.3f",
            title_score,
            artist_score,
            penalty,
            final_score,
        )

        title_dominant_match = title_score >= 0.60 and artist_in_title_or_uploader(
            sp_artist, yt_title, yt_artist
        )

        score_based_match = final_score >= self.FINAL_THRESHOLD and (
            title_score >= self.TITLE_THRESHOLD or artist_score >= self.ARTIST_THRESHOLD
        )

        is_match = title_dominant_match or score_based_match

        logger.debug(
            "Decision -> title_dominant: %s, score_based: %s, final_match: %s",
            title_dominant_match,
            score_based_match,
            is_match,
        )

        return is_match

    def find_best_match(
        self, *, search_results: list[YTVideoInfo], metadata: Metadata
    ) -> YTVideoInfo:
        query = f"{metadata.artist} - {metadata.title}"
        logger.debug("Searching best match for query: '%s'", query)

        cache = storage.get(query=query, query_type="youtube")
        if cache:
            logger.debug("Cache hit for query: '%s'", query)
            return cache

        for idx, result in enumerate(search_results):
            logger.debug("#" * 50)
            logger.debug("Evaluating result #%d: %s", idx + 1, result.title)

            title_and_artist = self.extractor.extract_artist_and_title(
                video_info=result, metadata=metadata
            )
            result.full_title = title_and_artist

            if self.match_tracks(video_info=result, metadata=metadata):
                logger.debug("Match found: '%s'", result.title)
                storage.new(query=query, result=result, query_type="youtube")
                logger.debug("#" * 50)
                return result

        logger.warning("No match found for query: '%s'", query)
        storage.new(query=query, result=Sentinel(), query_type="youtube")
        raise SongNotFound(query)
