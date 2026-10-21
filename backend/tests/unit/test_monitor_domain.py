import pytest

from pulse.features.monitors.domain import MonitorConfig, validate_url


@pytest.mark.parametrize(
    "url", ["https://example.com", "http://8.8.8.8/", "https://[2606:4700:4700::1111]/"]
)
def test_accepts_public_http_targets(url):
    assert validate_url(url).startswith(("http://", "https://"))


@pytest.mark.parametrize(
    "url",
    [
        "http://10.0.0.1",
        "http://[::1]",
        "http://localhost.localdomain",
        "http://metadata.internal",
        "http://bad_name.com",
        "https://bad-.com",
        "https://example.com:99999",
        "https://example.com/\n",
        "https://example.com\\@localhost/",
        "http://singlelabel",
        "http://a..com",
        "http://127.1",
        "https://example.com.",
    ],
)
def test_rejects_non_public_or_ambiguous_targets(url):
    with pytest.raises(ValueError):
        validate_url(url)


@pytest.mark.parametrize(
    "changes",
    [
        {"name": " "},
        {"name": "x" * 101},
        {"interval_seconds": 1},
        {"timeout_seconds": 31},
        {"interval_seconds": 30, "timeout_seconds": 30},
        {"expected_status": 600},
    ],
)
def test_configuration_enforces_domain_invariants(changes):
    with pytest.raises(ValueError):
        MonitorConfig(**{"name": "A", "url": "https://example.com", **changes})
