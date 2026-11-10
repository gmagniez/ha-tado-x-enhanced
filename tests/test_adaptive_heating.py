"""Standalone Adaptive Heating regression checks (no live Tado requests)."""
import ast
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "tado_x"
for module in ("api", "coordinator", "switch", "api_projection"):
    ast.parse((ROOT / f"{module}.py").read_text(), filename=module)

tree = ast.parse((ROOT / "api.py").read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TadoXApi")
methods = [n for n in cls.body if isinstance(n, ast.AsyncFunctionDef)
           and n.name in {"get_adaptive_heating", "set_adaptive_heating"}]
module = ast.Module(body=[ast.ClassDef(name="Api", bases=[], keywords=[],
                                      body=methods, decorator_list=[])], type_ignores=[])
class ApiError(Exception):
    pass

namespace = {"TadoXApiError": ApiError, "TADO_HOPS_API_URL": "https://hops.tado.com", "Any": object}
exec(compile(ast.fix_missing_locations(module), "<api>", "exec"), namespace)
api = namespace["Api"]()
api._home_id = 42
calls = []
async def request(*args, **kwargs):
    calls.append((args, kwargs))
    return {"adaptiveHeatingEnabled": True} if args[0] == "GET" else None
api._request = request
uri = "https://hops.tado.com/homes/42/settings/adaptiveHeating"
assert asyncio.run(api.get_adaptive_heating()) == {"adaptiveHeatingEnabled": True}
asyncio.run(api.set_adaptive_heating(True))
asyncio.run(api.set_adaptive_heating(False))
assert calls == [
    (("GET", uri), {}),
    (("PATCH", uri), {"json_data": {"adaptiveHeatingEnabled": True}}),
    (("PATCH", uri), {"json_data": {"adaptiveHeatingEnabled": False}}),
]

api._home_id = None
for method, args in ((api.get_adaptive_heating, ()), (api.set_adaptive_heating, (True,))):
    try:
        asyncio.run(method(*args))
        raise AssertionError("Home ID should be required")
    except ApiError:
        pass

source = (ROOT / "coordinator.py").read_text()
assert 'isinstance(response.get("adaptiveHeatingEnabled"), bool)' in source
assert 'data.adaptive_heating_enabled = enabled' in source
assert 'monotonic() - last >= 86400' in source
assert 'self._supplementary_last_success["adaptive_heating"] = monotonic()' in source
switch = (ROOT / "switch.py").read_text()
assert 'f"{coordinator.home_id}_adaptive_heating"' in switch
assert "if coordinator.data.adaptive_heating_enabled is not None:" in switch
assert "_attr_entity_registry_enabled_default = False" in switch
assert "await self.coordinator.api.set_adaptive_heating(enabled)" in switch
assert "self.coordinator.invalidate_adaptive_heating()" in switch
print("PASS: Adaptive Heating API shape, cache and switch checks")
