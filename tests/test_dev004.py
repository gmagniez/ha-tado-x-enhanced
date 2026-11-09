"""Standalone source-level regression checks; no Home Assistant or live API."""
import ast
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'custom_components' / 'tado_x'
for name in ('const.py', 'config_flow.py', 'coordinator.py', 'holiday_mode.py', '__init__.py'):
    ast.parse((root/name).read_text(), filename=name)

# Execute the actual coordinator's pure caching/accounting methods in a small stub.
mod = ast.parse((root/'coordinator.py').read_text())
cls = next(n for n in mod.body if isinstance(n, ast.ClassDef) and n.name == 'TadoXDataUpdateCoordinator')
names = {'get_api_calls_per_update', 'should_refresh_supplementary', 'mark_supplementary_success', 'update_supplementary_settings'}
methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
module = ast.Module(body=[ast.ClassDef(name='Stub', bases=[], keywords=[], body=methods, decorator_list=[])], type_ignores=[])
ns = {'Any': object}
exec(compile(ast.fix_missing_locations(module), '<extracted coordinator methods>', 'exec'), ns)
obj = ns['Stub']()
for key in ('weather', 'mobile_devices', 'air_comfort', 'running_times', 'flow_temp', 'hot_water'):
    setattr(obj, 'enable_'+key, True)
assert obj.get_api_calls_per_update() == 9
obj.enable_flow_temp = False
assert obj.get_api_calls_per_update() == 8
obj._scan_interval = 30
obj._supplementary_last_success = {}
obj._supplementary_cache = {}
obj.supplementary_poll_multiplier = 5
assert obj.should_refresh_supplementary('weather')
obj.mark_supplementary_success('weather', {'temperature': 10})
assert not obj.should_refresh_supplementary('weather')
assert obj._supplementary_cache['weather'] == {'temperature': 10}
obj.update_supplementary_settings(1)
assert obj.should_refresh_supplementary('weather')
obj.update_supplementary_settings(10)
assert obj.should_refresh_supplementary('weather')
for path in [root/'strings.json', *(root/'translations').glob('*.json')]:
    step = json.loads(path.read_text())['options']['step']['init']
    sections = step['sections']
    for section_name, key in (('supplementary_polling', 'enable_holiday_polling'),
                              ('supplementary_polling', 'supplementary_poll_multiplier')):
        section_data = sections[section_name]
        assert key in section_data['data'] and key in section_data['data_description'], (path, key)
for feature in ('weather', 'air_comfort', 'running_times', 'flow_temp', 'holiday_mode'):
    assert f'Supplementary API request: {feature} (home_id=%s)' in (root/'coordinator.py').read_text()
print('PASS: DEV-004 syntax, flow/translation keys, API accounting and supplementary cache eligibility')
