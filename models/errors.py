#!/usr/bin/python3
"""Custom error classes"""


class TitleExistsError(Exception):
    """File already downloaded"""

    def __init__(self, title: str):
        self.message = f"{title} already downloaded"
        super().__init__(self.message)


class InvalidURL(Exception):
    """Url not valid"""

    def __init__(self, url: str):
        self.message = f"{url} is invalid"
        super().__init__(self.message)


class SongNotFound(Exception):
    """A search term is not found"""

    def __init__(self, query: str):
        self.message = f"{query} not found"
        super().__init__(self.message)


class VersionSkipped(Exception):
    """A search term contains blacklisted keywords"""

    def __init__(self, query: str):
        self.message = f"[Blacklisted] {query} skipped"
        super().__init__(self.message)
