"""Standalone regression checks for read-only hydronic balancing support.

These tests do not need Home Assistant, and never connect to the Tado API.
"""
import ast
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "tado_x"
for module in ("api", "coordinator", "binary_sensor", "api_projection"):
    ast.parse((ROOT / f"{module}.py").read_text(), filename=module)

# Execute only the actual async API method with stub network transport.
tree = ast.parse((ROOT / "api.py").read_text())
api_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TadoXApi")
method = next(node for node in api_class.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "get_hydronic_balancing")
isolated = ast.Module(body=[ast.ClassDef(name="Api", bases=[], keywords=[], body=[method], decorator_list=[])], type_ignores=[])
class ApiError(Exception):
    pass
ns = {"TadoXApiError": ApiError, "TADO_HOPS_API_URL": "https://hops.tado.com", "Any": object}
exec(compile(ast.fix_missing_locations(isolated), "<api>", "exec"), ns)
calls = []
async def get(*args, **kwargs):
    calls.append((args, kwargs))
    return {"hydronicBalancingEnabled": False, "isPanasonicThermInterfaceType": False}
api = ns["Api"]()
api._home_id = 42
api._request = get
assert asyncio.run(api.get_hydronic_balancing())["hydronicBalancingEnabled"] is False
assert calls == [(("GET", "https://hops.tado.com/homes/42/settings/hydronicBalancing"), {})]
api._home_id = None
try:
    asyncio.run(api.get_hydronic_balancing())
    raise AssertionError("Home ID must be required")
except ApiError:
    pass

# Both boolean values are valid; absent responses must not silently read as Off.
coordinator = (ROOT / "coordinator.py").read_text()
assert 'isinstance(response.get("hydronicBalancingEnabled"), bool)' in coordinator
assert 'data.hydronic_balancing_enabled = enabled' in coordinator
assert 'self._supplementary_last_success["hydronic_balancing"] = monotonic()' in coordinator
assert 'monotonic() - last >= 86400' in coordinator

# There must be no writes to the balancing endpoint.
api_source = (ROOT / "api.py").read_text()
assert api_source.count("/settings/hydronicBalancing") == 1
assert '"GET",\n            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/settings/hydronicBalancing"' in api_source

# The binary sensor must be attached to each home's stable device ID.
sensor = (ROOT / "binary_sensor.py").read_text()
assert 'f"{coordinator.home_id}_hydronic_balancing"' in sensor
assert 'if coordinator.data.hydronic_balancing_enabled is not None:' in sensor

print("PASS: read-only hydronic balancing API, cache and entity checks")
