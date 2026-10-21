import ipaddress
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID


def validate_url(value: str) -> str:
    if len(value) > 2048 or any(ord(char) < 33 or ord(char) == 127 for char in value):
        raise ValueError("URL contains invalid characters or is too long.")
    try:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").encode("idna").decode().lower()
        port = parsed.port
    except (ValueError, UnicodeError) as error:
        raise ValueError("Invalid URL.") from error
    if (
        parsed.scheme not in ("http", "https")
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or port == 0
    ):
        raise ValueError("Use a public HTTP(S) URL without credentials or fragments.")
    if (
        "\\" in value
        or hostname == "localhost"
        or hostname.endswith(
            (".localhost", ".local", ".localdomain", ".internal", ".home.arpa", ".")
        )
        or "%" in hostname
    ):
        raise ValueError("Local hostnames are not allowed.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if (
            "." not in hostname
            or hostname.rsplit(".", 1)[-1].isdigit()
            or any(
                not part
                or len(part) > 63
                or part.startswith("-")
                or part.endswith("-")
                or any(not (char.isalnum() or char == "-") for char in part)
                for part in hostname.split(".")
            )
        ):
            raise ValueError("Use a public hostname.") from None
    else:
        if not address.is_global:
            raise ValueError("Private and reserved IP addresses are not allowed.")
    host = f"[{hostname}]" if ":" in hostname else hostname
    netloc = f"{host}:{port}" if port else host
    return urlunsplit((parsed.scheme, netloc, parsed.path or "/", parsed.query, ""))


@dataclass(frozen=True)
class MonitorConfig:
    name: str
    url: str
    interval_seconds: int = 60
    timeout_seconds: int = 10
    expected_status: int = 200
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip() or len(self.name) > 100:
            raise ValueError("Name must contain 1 to 100 characters.")
        if not 30 <= self.interval_seconds <= 86400 or not 1 <= self.timeout_seconds <= 30:
            raise ValueError("Invalid interval or timeout.")
        if self.timeout_seconds >= self.interval_seconds:
            raise ValueError("Timeout must be shorter than the interval.")
        if not 100 <= self.expected_status <= 599:
            raise ValueError("Invalid expected HTTP status.")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "url", validate_url(self.url))


@dataclass(frozen=True)
class Monitor:
    id: UUID
    tenant_id: UUID
    config: MonitorConfig
    config_version: int
    created_at: datetime
    updated_at: datetime
