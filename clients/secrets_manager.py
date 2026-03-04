from os import getenv, environ
from typing import Literal, overload
from dotenv import load_dotenv

load_dotenv()

class SecretsManager():
    @overload
    @staticmethod
    def read(*, key: str, alt: str) -> str: ...

    @overload
    @staticmethod
    def read(*, key: str, alt: Literal[None] = None) -> str | None: ...

    @staticmethod
    def read(*, key, alt = None):
        return getenv(key) or alt

    @staticmethod
    def write(*, key: str, value: str):
        environ[key] = value

