"""Standalone regression checks for hydronic balancing control.

No Home Assistant dependency and no real API calls.
"""
import ast
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "tado_x"
for module in ("api", "coordinator", "switch", "api_projection"):
    ast.parse((ROOT / f"{module}.py").read_text(), filename=module)

# Execute API methods against an isolated recording transport.
tree = ast.parse((ROOT / "api.py").read_text())
api_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TadoXApi")
method_names = ("get_hydronic_balancing", "set_hydronic_balancing")
methods = [n for n in api_class.body if isinstance(n, ast.AsyncFunctionDef) and n.name in method_names]
isolated = ast.Module(body=[ast.ClassDef(name="Api", bases=[], keywords=[], body=methods, decorator_list=[])], type_ignores=[])
class ApiError(Exception):
    pass
ns = {"TadoXApiError": ApiError, "TADO_HOPS_API_URL": "https://hops.tado.com", "Any": object}
exec(compile(ast.fix_missing_locations(isolated), "<api>", "exec"), ns)

calls = []
async def request(*args, **kwargs):
    calls.append((args, kwargs))
    if args[0] == "GET":
        return {"hydronicBalancingEnabled": False, "isPanasonicThermInterfaceType": False}
    return None

api = ns["Api"]()
api._home_id = 42
api._request = request
uri = "https://hops.tado.com/homes/42/settings/hydronicBalancing"
assert asyncio.run(api.get_hydronic_balancing())["hydronicBalancingEnabled"] is False
asyncio.run(api.set_hydronic_balancing(True))
asyncio.run(api.set_hydronic_balancing(False))
assert calls == [
    (("GET", uri), {}),
    (("PATCH", uri), {"json_data": {"hydronicBalancingEnabled": True}}),
    (("PATCH", uri), {"json_data": {"hydronicBalancingEnabled": False}}),
]

api._home_id = None
for method, args in ((api.get_hydronic_balancing, ()), (api.set_hydronic_balancing, (True,))):
    try:
        asyncio.run(method(*args))
        raise AssertionError("Home ID must be required")
    except ApiError:
        pass

coordinator = (ROOT / "coordinator.py").read_text()
assert 'isinstance(response.get("hydronicBalancingEnabled"), bool)' in coordinator
assert 'data.hydronic_balancing_enabled = enabled' in coordinator
assert 'self._supplementary_last_success["hydronic_balancing"] = monotonic()' in coordinator
assert 'monotonic() - last >= 86400' in coordinator
switch = (ROOT / "switch.py").read_text()
assert 'f"{coordinator.home_id}_hydronic_balancing"' in switch
assert "if coordinator.data.hydronic_balancing_enabled is not None:" in switch
assert "_attr_entity_registry_enabled_default = False" in switch
assert "self.coordinator.invalidate_hydronic_balancing()" in switch
assert "await self.coordinator.api.set_hydronic_balancing(enabled)" in switch
print("PASS: hydronic balancing GET/PATCH, caching and opt-in switch checks")
