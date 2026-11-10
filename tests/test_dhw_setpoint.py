"""Standalone OpenTherm DHW regression checks (no Home Assistant required)."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1] / "custom_components" / "tado_x"
for file in ("api.py", "coordinator.py", "number.py", "sensor.py"):
    ast.parse((root / file).read_text(), filename=file)

# Run the actual API implementation with a stub transport.
api_ast = ast.parse((root / "api.py").read_text())
api_class = next(n for n in api_ast.body if isinstance(n, ast.ClassDef) and n.name == "TadoXApi")
method = next(n for n in api_class.body if isinstance(n, ast.AsyncFunctionDef)
              and n.name == "set_domestic_hot_water_temperature")
module = ast.Module(body=[ast.ClassDef(name="Api", bases=[], keywords=[], body=[method],
                                      decorator_list=[])], type_ignores=[])
class ApiError(Exception):
    pass
ns = {"TadoXApiError": ApiError, "TADO_HOPS_API_URL": "https://hops.tado.com"}
exec(compile(ast.fix_missing_locations(module), "<extracted api>", "exec"), ns)

calls = []
async def request(*args, **kwargs):
    calls.append((args, kwargs))
api = ns["Api"]()
api._home_id = 123
api._request = request
asyncio.run(api.set_domestic_hot_water_temperature(51))
assert calls == [(
    ("POST", "https://hops.tado.com/homes/123/programmer/domesticHotWater/manualControl"),
    {"json_data": {"setpoint": 51}},
)]
api._home_id = None
try:
    asyncio.run(api.set_domestic_hot_water_temperature(51))
    raise AssertionError("Missing home ID must fail")
except ApiError:
    pass

# Execute the actual NumberEntity write method with a fake coordinator.
number_ast = ast.parse((root / "number.py").read_text())
number_class = next(n for n in number_ast.body if isinstance(n, ast.ClassDef)
                    and n.name == "TadoXDhwSetpoint")
write = next(n for n in number_class.body if isinstance(n, ast.AsyncFunctionDef)
             and n.name == "async_set_native_value")
module = ast.Module(body=[ast.ClassDef(name="Number", bases=[], keywords=[], body=[write],
                                      decorator_list=[])], type_ignores=[])
ns = {}
exec(compile(ast.fix_missing_locations(module), "<extracted number>", "exec"), ns)
saved = []
async def setpoint(v):
    saved.append(v)
async def refresh():
    saved.append("refreshed")
entity = ns["Number"]()
entity.coordinator = SimpleNamespace(
    data=SimpleNamespace(dhw_setpoint_min=30, dhw_setpoint_max=65),
    api=SimpleNamespace(set_domestic_hot_water_temperature=setpoint),
    async_request_refresh=refresh,
)
asyncio.run(entity.async_set_native_value(51.0))
assert saved == [51, "refreshed"]
for invalid in (29, 66, 50.5):
    try:
        asyncio.run(entity.async_set_native_value(invalid))
        raise AssertionError(f"Setpoint {invalid} must be rejected")
    except ValueError:
        pass
assert saved == [51, "refreshed"]

# Capability detection must be based on both the observed interface and a
# setpoint-capable DHW response; OpenTherm alone is not a relay capability flag.
coordinator_source = (root / "coordinator.py").read_text()
assert 'device.get("thermInterfaceType") == "OPENTHERM"' in coordinator_source
assert "data.dhw_setpoint is not None" in coordinator_source
for platform in ("button.py", "select.py"):
    source = (root / platform).read_text()
    assert "data.dhw_relay_actions_unverified" in source
    assert "_attr_entity_registry_enabled_default = False" in source
    # Guard the registry reconciliation so it does not re-enable the
    # default-disabled entities on startup.
    assert "if any(entity_entry.unique_id.endswith" in source

print("OpenTherm DHW setpoint regression checks passed")
