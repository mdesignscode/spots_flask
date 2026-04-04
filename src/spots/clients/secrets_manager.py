from os import getenv, environ
from typing import Literal, overload
from dotenv import load_dotenv

from spots.utils import get_config_path


load_dotenv(dotenv_path=f"{get_config_path()}/.env")

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

