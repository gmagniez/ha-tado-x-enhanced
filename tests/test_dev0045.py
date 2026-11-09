"""Standalone DEV-004.5 regression checks (no Home Assistant or cloud access)."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1] / 'custom_components' / 'tado_x'
source = ast.parse((root/'polling_options.py').read_text())
methods = [n for n in source.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
           and n.name in ('validate_polling_changes', 'apply_polling_changes')]
namespace = {'HomeAssistantError': type('HomeAssistantError', (Exception,), {})}
keys = ('scan_interval','schedule_poll_interval','supplementary_poll_multiplier',
        'enable_schedule_polling','enable_holiday_polling','enable_weather',
        'enable_air_comfort','enable_running_times','enable_flow_temp',
        'enable_mobile_devices','enable_hot_water')
for name in keys:
    namespace['CONF_'+name.upper()] = name
namespace['BOOL_KEYS'] = keys[3:]
namespace['POLLING_KEYS'] = keys
namespace['SUPPLEMENTARY_POLL_MULTIPLIERS'] = (1,2,5,10)
namespace['FEATURE_ENTITY_MAP'] = {}
namespace['DOMAIN'] = 'tado_x'
namespace['er'] = SimpleNamespace(async_get=lambda hass: SimpleNamespace(entities={}),RegistryEntryDisabler=SimpleNamespace(INTEGRATION='integration'))
exec(compile(ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[])), '<polling_options>', 'exec'), namespace)
validate=namespace['validate_polling_changes']
for value in (1,2,5,10):validate({'supplementary_poll_multiplier':value})
for invalid in ({'supplementary_poll_multiplier':3},{'scan_interval':29},
                {'schedule_poll_interval':899},{'enable_weather':1},
                {'unknown':True},{'scan_interval':'30'}):
    try:validate(invalid)
    except namespace['HomeAssistantError']:pass
    else:raise AssertionError(f'Accepted invalid setting {invalid}')
class Entry:
    entry_id='entry-1'
    data={'scan_interval':30,'supplementary_poll_multiplier':1,
          'enable_schedule_polling':True,'schedule_poll_interval':3600,
          'enable_holiday_polling':True,'enable_weather':True}
class Entries:
    calls=0
    def async_update_entry(self,entry,*,data):
        self.calls+=1
        entry.data=data
class Coordinator:
    def __init__(self):
        self.scans=[];self.mult=[];self.invalidations=[];self.notifications=0
        self.enable_weather=True
        self.schedule_profile_manager=SimpleNamespace(configure_polling=lambda *args:None)
        self.holiday_mode_manager=SimpleNamespace(configure_polling=lambda *args:None)
    def async_update_listeners(self):self.notifications+=1
    def update_scan_interval(self,value):self.scans.append(value)
    def update_supplementary_settings(self,value):self.mult.append(value)
    def invalidate_supplementary(self,value):self.invalidations.append(value)
entry=Entry();entries=Entries();hass=SimpleNamespace(config_entries=entries);coord=Coordinator()
apply=namespace['apply_polling_changes']
async def run():
    await apply(hass,entry,coord,{'scan_interval':300,'supplementary_poll_multiplier':5})
    assert entry.data['enable_weather'] is True and coord.scans==[300] and coord.mult==[5]
    assert entries.calls==1 and coord.notifications==1
    await apply(hass,entry,coord,{'scan_interval':300})
    assert entries.calls==1
    try:await apply(hass,entry,coord,{'scan_interval':400,'supplementary_poll_multiplier':4})
    except namespace['HomeAssistantError']:pass
    else:raise AssertionError('Invalid patch accepted')
    assert entry.data['scan_interval']==300 and entries.calls==1
asyncio.run(run())
print('PASS: DEV-004.5 option validation, atomicity, partial update, no-op and persistence')
