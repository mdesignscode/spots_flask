from dataclasses import dataclass, field
from requests import get
from requests.exceptions import Timeout, ConnectionError, RequestException, HTTPError
from typing import Any, Literal


@dataclass
class FetchResponseFailure:
    error: str
    status_code: int = field(default=500)
    success: Literal[False] = False
    data: None = None
    fallback: Any = None

@dataclass
class FetchResponseSuccess:
    data: dict[str, Any] | str
    status_code: int = field(default=200)
    success: Literal[True] = True
    error: None = None
    fallback: Any = None


def fetch_data(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
    timeout: int = 5,
) -> FetchResponseFailure | FetchResponseSuccess:
    try:
        response = get(url, params=params, headers=headers, timeout=timeout)

        # Check for HTTP errors (4xx, 5xx)
        response.raise_for_status()

        # Try to parse JSON (optional, adjust if expecting text)
        try:
            res_data = response.json()

            if res_data.get("error"):
                error_data = res_data["error"]
                return FetchResponseFailure(
                    status_code=error_data.get("code"), error=error_data["message"]
                )

            return FetchResponseSuccess(
                status_code=response.status_code, data=res_data
            )
        except ValueError:
            return FetchResponseSuccess(
                status_code=response.status_code,
                data=response.text,  # fallback if not JSON
            )

    except Timeout:
        return FetchResponseFailure(
            error="Request timed out",
            fallback=None,  # you can plug in cached data here
        )

    except ConnectionError:
        return FetchResponseFailure(error="Connection error", fallback=None)

    except HTTPError as e:
        return FetchResponseFailure(
            error=f"HTTP error: {e}",
            status_code=getattr(e.response, "status_code", 500),
            fallback=None,
        )

    except RequestException as e:
        # Catch-all for other request issues
        return FetchResponseFailure(
            error=f"Unexpected error: {e}", fallback=None
        )

