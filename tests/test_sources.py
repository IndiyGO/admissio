import httpx
import pytest

from admissio.config import FieldMap, SourceConfig, interpolate
from admissio.sources import to_new_hires
from admissio.sources.rest_source import fetch_records


def test_rest_source_follows_records_path_and_sends_headers():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": {"items": [{"id": "7", "name": "Rafael  Lima", "site": "SP"}]}})

    cfg = SourceConfig(
        type="rest",
        url="https://hr.example.com/api/hires",
        headers={"Authorization": "Bearer t0ken"},
        records_path="data.items",
        fields=FieldMap(employee_id="id", full_name="name", branch="site"),
    )
    records = fetch_records(cfg, httpx.Client(transport=httpx.MockTransport(handler)))
    hires = list(to_new_hires(records, cfg))

    assert seen["auth"] == "Bearer t0ken"
    assert [(h.employee_id, h.full_name, h.branch) for h in hires] == [("7", "Rafael Lima", "SP")]


def test_rest_source_rejects_non_list():
    cfg = SourceConfig(type="rest", url="https://x", records_path="data")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": {}})))
    with pytest.raises(ValueError, match="did not point to a list"):
        fetch_records(cfg, client)


def test_interpolation_defaults_and_missing():
    assert interpolate("${A}-${B:-fallback}", {"A": "x"}) == "x-fallback"
    with pytest.raises(ValueError, match="TOKEN"):
        interpolate("Bearer ${TOKEN}", {})
