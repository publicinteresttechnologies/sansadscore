import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import REQUEST_TIMEOUT_SECONDS, RETRY_BACKOFF_FACTOR, RETRY_TOTAL, USER_AGENT


def build_session():
    retry = Retry(
        total=RETRY_TOTAL,
        connect=RETRY_TOTAL,
        read=RETRY_TOTAL,
        status=RETRY_TOTAL,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


SESSION = build_session()


def get_json(url, params=None):
    response = SESSION.get(url, params=params or {}, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def get_text(url, params=None):
    response = SESSION.get(url, params=params or {}, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text
