from tenacity import retry as _retry
from tenacity import retry_if_exception
from models.errors import SongNotFound


def is_retryable_exception(exc: BaseException) -> bool:
    # Only retry transient failures
    return not isinstance(exc, SongNotFound)

def retry(*args, **kwargs):
    """
    Project-wide retry decorator.
    - Never retries SongNotFound
    - Always re-raises the final exception
    """

    user_retry = kwargs.pop("retry", None)

    base_retry = retry_if_exception(is_retryable_exception)

    if user_retry is not None:
        # Combine user retry conditions with ours
        retry_condition = base_retry & user_retry
    else:
        retry_condition = base_retry

    return _retry(
        *args,
        retry=retry_condition,
        reraise=True,
        **kwargs,
    )

