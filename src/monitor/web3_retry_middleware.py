from time import sleep

import structlog
from requests.exceptions import ConnectionError, HTTPError, Timeout, TooManyRedirects

logger = structlog.get_logger("monitor.http_retry_request_middleware_endlessly")

_RETRY_SLEEP_DURATION = 5  # seconds


def exception_retry_middleware_endlessly(make_request, web3, errors):
    def middleware(method, params):
        while True:
            try:
                return make_request(method, params)

            except errors as err:
                logger.warn(
                    f"The RPC request to the HTTPProvider failed with the following error:\n\t{str(err)}"
                )
                logger.warn(
                    f"Wait for {_RETRY_SLEEP_DURATION}s before trying it again..."
                )
                sleep(_RETRY_SLEEP_DURATION)
                continue

    return middleware


def http_retry_request_middleware_endlessly(make_request, web3):
    """An adopted version of the default http_retry_request middleware.

    In contrast to the origin middleware this retries to connect
    forever. Furthermore does it introduce a short delay between the
    retries.
    """

    return exception_retry_middleware_endlessly(
        make_request, web3, (ConnectionError, HTTPError, Timeout, TooManyRedirects)
    )
