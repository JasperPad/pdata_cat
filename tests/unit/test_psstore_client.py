"""Tests for PSStoreClient: GraphQL API client for PlayStation Store."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from ps5_scraper.api.psstore_client import PSStoreClient, PSStoreHashExpiredError


@pytest.fixture
def client():
    return PSStoreClient()


class TestPSStoreClientInit:
    """Test client initialization."""

    def test_default_locale(self):
        c = PSStoreClient()
        assert c.locale == "zh-hant-hk"

    def test_custom_locale(self):
        c = PSStoreClient(locale="en-us")
        assert c.locale == "en-us"

    def test_default_base_url(self):
        c = PSStoreClient()
        assert "playstation.com" in c.base_url


class TestGraphQLRequestBuild:
    """Test GraphQL request body construction."""

    @pytest.mark.asyncio
    async def test_builds_correct_graphql_body(self, client):
        """Should build correct GraphQL persisted query POST body."""
        expected_hash = "4ce7d410a4db2c8b635a48c1dcec375906ff63b19dadd87e073f8fd0c0481d35"
        category_id = "4cbf39e2-5749-4970-ba81-93a489e4570c"

        with respx.mock as mock:
            resp_body = {"data": {"categoryGridRetrieve": {"pageInfo": {"totalCount": 0}, "products": []}}}

            captured_request = {}

            def side_effect(request):
                captured_request["body"] = json.loads(request.content)
                return httpx.Response(200, json=resp_body)

            mock.post("https://web.np.playstation.com/api/graphql/v1/op").mock(
                side_effect=side_effect
            )

            await client.fetch_category_games(category_id, offset=0, size=24)

            body = captured_request["body"]
            assert body["operationName"] == "categoryGridRetrieve"
            assert body["variables"]["id"] == category_id
            # Variables use nested pageArgs structure (actual PS Store schema)
            assert body["variables"]["pageArgs"]["offset"] == 0
            assert body["variables"]["pageArgs"]["size"] == 24
            assert body["variables"]["currency"] == "HKD"
            assert body["extensions"]["persistedQuery"]["sha256Hash"] == expected_hash

    @pytest.mark.asyncio
    async def test_sets_correct_headers(self, client):
        """Should set required PS Store headers."""
        with respx.mock as mock:
            resp_body = {"data": {"categoryGridRetrieve": {"pageInfo": {"totalCount": 0}, "products": []}}}

            captured_headers = {}

            def side_effect(request):
                captured_headers.update(dict(request.headers))
                return httpx.Response(200, json=resp_body)

            mock.post("https://web.np.playstation.com/api/graphql/v1/op").mock(
                side_effect=side_effect
            )

            await client.fetch_category_games("test-id", offset=0, size=10)

            assert captured_headers.get("x-psn-store-locale-override") == "zh-hant-hk"
            assert captured_headers.get("x-apollo-operation-name") == "categoryGridRetrieve"


class TestResponseParsing:
    """Test response parsing."""

    @pytest.mark.asyncio
    async def test_parse_success_response(self, client):
        """Should parse successful response and return raw JSON."""
        response_data = {
            "data": {
                "categoryGridRetrieve": {
                    "__typename": "CategoryGrid",
                    "pageInfo": {
                        "totalCount": 7047,
                        "offset": 0,
                        "size": 24,
                        "isLast": False,
                    },
                    "products": [
                        {
                            "__typename": "Product",
                            "name": "劍星",
                            "id": "HP9000-PPSA13198_00-STELLARBLADECE00",
                        }
                    ],
                }
            }
        }

        with patch.object(client, "request", return_value=response_data):
            result = await client.fetch_category_games("cat-id", 0, 24)

        assert result == response_data


class TestHashExpirationDetection:
    """Test detection of expired GraphQL hash."""

    @pytest.mark.asyncio
    async def test_detects_unknown_operation_error(self, client):
        """Should raise PSStoreHashExpiredError on 'Unknown operation'."""
        error_response = {
            "errors": [
                {"message": "Unknown operation", "code": "OPERATION_NOT_FOUND"}
            ]
        }

        with (
            patch.object(client, "request", return_value=error_response),
            pytest.raises(PSStoreHashExpiredError) as exc_info,
        ):
            await client.fetch_category_games("cat-id", 0, 24)

        err_msg = str(exc_info.value).lower()
        assert "unknown operation" in err_msg or "hash" in err_msg

    @pytest.mark.asyncio
    async def test_detects_persisted_query_not_found(self, client):
        """Should raise PSStoreHashExpiredError on 'PersistedQueryNotFound'."""
        error_response = {
            "errors": [
                {
                    "message": "PersistedQueryNotFound",
                    "code": "PERSISTED_QUERY_NOT_FOUND",
                }
            ]
        }

        with (
            patch.object(client, "request", return_value=error_response),
            pytest.raises(PSStoreHashExpiredError) as exc_info,
        ):
            await client.fetch_category_games("cat-id", 0, 24)


class TestPaginationParameters:
    """Test pagination parameter passing."""

    @pytest.mark.asyncio
    async def test_passes_offset_and_size(self, client):
        """Offset and size should be passed to GraphQL variables correctly."""
        with respx.mock as mock:
            resp_body = {
                "data": {
                    "categoryGridRetrieve": {
                        "pageInfo": {
                            "totalCount": 100,
                            "offset": 48,
                            "size": 24,
                            "isLast": False,
                        },
                        "products": [],
                    }
                }
            }

            captured_body = {}

            def side_effect(request):
                captured_body["data"] = json.loads(request.content)
                return httpx.Response(200, json=resp_body)

            mock.post("https://web.np.playstation.com/api/graphql/v1/op").mock(
                side_effect=side_effect
            )

            await client.fetch_category_games("cat-id", offset=48, size=24)

            body = captured_body["data"]
            # Variables use nested pageArgs structure (actual PS Store schema)
            assert body["variables"]["pageArgs"]["offset"] == 48
            assert body["variables"]["pageArgs"]["size"] == 24


class TestLocaleConfiguration:
    """Test locale configuration."""

    @pytest.mark.asyncio
    async def test_custom_locale_in_headers(self):
        """Custom locale should be reflected in headers."""
        custom_client = PSStoreClient(locale="en-us")

        with respx.mock as mock:
            resp_body = {
                "data": {
                    "categoryGridRetrieve": {
                        "pageInfo": {"totalCount": 0},
                        "products": [],
                    }
                }
            }
            captured_headers = {}

            def side_effect(request):
                captured_headers.update(dict(request.headers))
                return httpx.Response(200, json=resp_body)

            mock.post("https://web.np.playstation.com/api/graphql/v1/op").mock(
                side_effect=side_effect
            )

            await custom_client.fetch_category_games("cat-id", 0, 10)

            assert captured_headers.get("x-psn-store-locale-override") == "en-us"
