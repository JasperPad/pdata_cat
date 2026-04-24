"""PlayStation Store GraphQL API client."""

from __future__ import annotations

import logging
from typing import Any

from ps5_scraper.api.base import APIClientError, BaseAPIClient

logger = logging.getLogger(__name__)

# GraphQL Persisted Query Hash for category listing
CATEGORY_LIST_HASH = "4ce7d410a4db2c8b635a48c1dcec375906ff63b19dadd87e073f8fd0c0481d35"

# Default PS5 category ID for HK store
PS5_CATEGORY_ID = "4cbf39e2-5749-4970-ba81-93a489e4570c"

PS_STORE_BASE_URL = "https://web.np.playstation.com/api/graphql/v1/op"


class PSStoreHashExpiredError(APIClientError):
    """Raised when the GraphQL persisted query hash has expired."""


class PSStoreClient(BaseAPIClient):
    """Client for PlayStation Store GraphQL API.

    Handles:
    - Building GraphQL persisted query requests
    - Setting required PS Store headers (locale, operation name)
    - Detecting hash expiration errors
    """

    def __init__(
        self,
        *,
        locale: str = "zh-hant-hk",
        currency: str = "HKD",
        requests_per_minute: int = 30,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            base_url=PS_STORE_BASE_URL,
            requests_per_minute=requests_per_minute,
            **kwargs,
        )
        self.locale = locale
        self.currency = currency  # v2.0: multi-region support

    async def fetch_category_games(
        self,
        category_id: str | None = None,
        offset: int = 0,
        size: int = 24,
    ) -> dict[str, Any]:
        """Fetch games from a PS Store category via GraphQL.

        Args:
            category_id: Category UUID. Defaults to PS5 HK category.
            offset: Pagination offset.
            size: Number of items per page.

        Returns:
            Raw JSON response dict from the API.

        Raises:
            PSStoreHashExpiredError: If the GraphQL hash is expired/invalid.
            APIClientError: On other request failures.
        """
        if category_id is None:
            category_id = PS5_CATEGORY_ID

        body = self._build_graphql_body(category_id, offset, size)
        headers = self._build_headers()

        response = await self.request("POST", "", json=body, headers=headers)

        # Check for hash expiration errors
        self._check_hash_errors(response)

        return response

    def _build_graphql_body(
        self,
        category_id: str,
        offset: int,
        size: int,
    ) -> dict[str, Any]:
        """Build the GraphQL persisted query POST body.

        Variable structure matches the actual PS Store GraphQL schema:
        - id: Category UUID (top-level)
        - pageArgs: Nested pagination { offset, size }
        - currency: Price currency code (e.g., HKD, USD, JPY)
        """
        return {
            "operationName": "categoryGridRetrieve",
            "variables": {
                "id": category_id,
                "pageArgs": {"offset": offset, "size": size},
                "currency": self.currency,
            },
            "extensions": {
                "persistedQuery": {
                    "sha256Hash": CATEGORY_LIST_HASH,
                    "version": 1,
                },
            },
        }

    def _build_headers(self) -> dict[str, str]:
        """Build PS Store specific headers."""
        return {
            "x-psn-store-locale-override": self.locale,
            "x-apollo-operation-name": "categoryGridRetrieve",
        }

    @staticmethod
    def _check_hash_errors(response: dict[str, Any]) -> None:
        """Check for hash expiration / unknown operation errors in response."""
        errors = response.get("errors")
        if not errors:
            return

        for error in errors:
            message = error.get("message", "")
            code = error.get("code", "")

            if any(
                keyword in message.lower()
                for keyword in [
                    "unknown operation",
                    "persistedquerynotfound",
                    "hash",
                    "expired",
                ]
            ):
                raise PSStoreHashExpiredError(
                    f"GraphQL hash may be expired. Error: {message} (code: {code})"
                )
