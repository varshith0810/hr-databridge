"""
ingestion/api_poller.py
Polls Greenhouse (JSON) and Workday (XML) REST APIs.

Key features:
  - Delta sync: only fetches records modified since last successful cursor
  - Exponential backoff retry on transient failures (429, 5xx)
  - Batch pagination: fetches up to BATCH_SIZE records per page
  - Returns raw payloads + metadata for the parser to consume
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Generator, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

BATCH_SIZE = int(os.getenv("BATCH_SIZE", 500))
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds; doubles each retry


# --------------------------------------------------------------------------- #
#  Retry helper
# --------------------------------------------------------------------------- #

def _request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    """
    Makes an HTTP request with exponential backoff on retriable errors.
    Raises httpx.HTTPStatusError after MAX_RETRIES exhausted.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.request(method, url, timeout=30, **kwargs)

            if response.status_code in (429, 502, 503, 504):
                wait = RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    f"Retriable HTTP {response.status_code} on {url}. "
                    f"Attempt {attempt}/{MAX_RETRIES}. Retrying in {wait}s..."
                )
                time.sleep(wait)
                continue

            response.raise_for_status()
            return response

        except httpx.TimeoutException:
            wait = RETRY_BACKOFF_BASE ** attempt
            logger.warning(f"Timeout on {url}. Attempt {attempt}/{MAX_RETRIES}. Retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"All {MAX_RETRIES} retries exhausted for {url}")


# --------------------------------------------------------------------------- #
#  Greenhouse poller  (JSON REST API)
# --------------------------------------------------------------------------- #

class GreenhousePoller:
    """
    Polls Greenhouse ATS for candidate records.
    API contract:
      GET /v1/candidates?updated_after=<ISO8601>&page=<n>&per_page=<n>
    Returns JSON: { "meta": { "total": N }, "candidates": [...] }
    """

    BASE_URL = os.getenv("GREENHOUSE_API_BASE", "http://localhost:8001")
    API_KEY = os.getenv("GREENHOUSE_API_KEY", "mock-key")

    def __init__(self):
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.API_KEY}",
                "Accept": "application/json",
            },
        )

    def fetch_since(self, cursor: Optional[str] = None) -> Generator[dict, None, None]:
        """
        Yields raw candidate dicts page by page.

        Args:
            cursor: ISO8601 datetime string of last sync. If None, fetches all records.

        Yields:
            dict: raw candidate payload from Greenhouse API
        """
        page = 1
        total_yielded = 0

        params = {"per_page": BATCH_SIZE, "page": page}
        if cursor:
            params["updated_after"] = cursor

        while True:
            params["page"] = page
            logger.info(f"[Greenhouse] Fetching page {page} (cursor={cursor})")

            response = _request_with_retry(self.client, "GET", "/v1/candidates", params=params)
            data = response.json()

            candidates = data.get("candidates", [])
            if not candidates:
                logger.info(f"[Greenhouse] No more records. Total fetched: {total_yielded}")
                break

            for candidate in candidates:
                yield candidate
                total_yielded += 1

            # Check if there are more pages
            meta_total = data.get("meta", {}).get("total", 0)
            if total_yielded >= meta_total:
                break

            page += 1

    def get_next_cursor(self) -> str:
        """Returns current UTC timestamp as next cursor value."""
        return datetime.now(timezone.utc).isoformat()

    def close(self):
        self.client.close()


# --------------------------------------------------------------------------- #
#  Workday poller  (XML REST API)
# --------------------------------------------------------------------------- #

class WorkdayPoller:
    """
    Polls Workday HRIS for employee records.
    API contract:
      GET /workers?Last_Modified_After=<ISO8601>&startIndex=<n>&count=<n>
    Returns XML:
      <Workers total="N">
        <Worker>...</Worker>
      </Workers>
    """

    BASE_URL = os.getenv("WORKDAY_API_BASE", "http://localhost:8002")
    API_KEY = os.getenv("WORKDAY_API_KEY", "mock-key")

    def __init__(self):
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.API_KEY}",
                "Accept": "application/xml",
            },
        )

    def fetch_since(self, cursor: Optional[str] = None) -> Generator[bytes, None, None]:
        """
        Yields raw XML bytes for each worker element, page by page.

        Args:
            cursor: ISO8601 datetime string of last sync.

        Yields:
            bytes: raw <Worker>...</Worker> XML element bytes
        """
        start_index = 0
        total_yielded = 0

        params = {"count": BATCH_SIZE, "startIndex": start_index}
        if cursor:
            params["Last_Modified_After"] = cursor

        while True:
            params["startIndex"] = start_index
            logger.info(f"[Workday] Fetching batch starting at {start_index} (cursor={cursor})")

            response = _request_with_retry(self.client, "GET", "/workers", params=params)
            xml_bytes = response.content

            # Parse XML to extract individual Worker elements
            from lxml import etree
            root = etree.fromstring(xml_bytes)
            total = int(root.get("total", 0))
            workers = root.findall("Worker")

            if not workers:
                logger.info(f"[Workday] No more records. Total fetched: {total_yielded}")
                break

            for worker in workers:
                yield etree.tostring(worker)
                total_yielded += 1

            if total_yielded >= total:
                break

            start_index += BATCH_SIZE

    def get_next_cursor(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def close(self):
        self.client.close()
