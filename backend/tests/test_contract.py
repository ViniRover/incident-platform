import json
from pathlib import Path

from pulse.export_openapi import main
from pulse.main import create_app


def test_committed_contract_matches_the_application(settings):
    committed = Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"
    assert json.loads(committed.read_text(encoding="utf-8")) == create_app(settings).openapi()


def test_export_works_without_deployment_secrets(capsys):
    main()
    schema = json.loads(capsys.readouterr().out)
    assert schema["info"]["version"] == "0.2.0"


def test_v1_contract_keeps_required_inputs_and_response_fields(settings):
    schema = create_app(settings).openapi()
    schemas = schema["components"]["schemas"]
    # These M1 inputs remain minimal; additive optional fields do not break callers.
    assert set(schemas["MonitorInput"]["required"]) == {"name", "url"}
    assert set(schemas["MonitorUpdate"]["required"]) == {"name", "url", "config_version"}
    assert set(schemas["LoginRequest"]["required"]) == {"tenant_slug", "email", "password"}
    assert {"tenant_id", "user_id", "role", "csrf_token"} <= set(
        schemas["SessionResponse"]["required"]
    )
    assert schemas["Role"]["enum"] == ["owner", "admin", "operator", "viewer"]
    assert all(path.startswith("/api/v1/") for path in schema["paths"])
    operations = [
        operation["operationId"] for path in schema["paths"].values() for operation in path.values()
    ]
    assert len(operations) == len(set(operations))
