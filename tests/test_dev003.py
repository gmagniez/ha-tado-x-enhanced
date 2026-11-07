"""Standalone mock tests for DEV-003. No Home Assistant or live Tado calls."""
import asyncio
import importlib.util
import json
import logging
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path

root=Path(__file__).resolve().parent.parent
pkg=types.ModuleType('custom_components');pkg.__path__=[str(root/'custom_components')];sys.modules['custom_components']=pkg
pkg=types.ModuleType('custom_components.tado_x');pkg.__path__=[str(root/'custom_components/tado_x')];sys.modules['custom_components.tado_x']=pkg
ha=types.ModuleType('homeassistant');ha.__path__=[];sys.modules['homeassistant']=ha
util=types.ModuleType('homeassistant.util');util.__path__=[];sys.modules['homeassistant.util']=util
ssl=types.ModuleType('homeassistant.util.ssl');ssl.get_default_context=lambda:None;sys.modules['homeassistant.util.ssl']=ssl
spec=importlib.util.spec_from_file_location('custom_components.tado_x.api',root/'custom_components/tado_x/api.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

class Response:
    def __init__(self,status=200,data=None):
        self.status=status;self.data=data or {};self.headers={};self.content_length=0 if status==204 else 1
    async def __aenter__(self):return self
    async def __aexit__(self,*a):pass
    async def json(self):return self.data
    async def text(self):return json.dumps(self.data)
class Session:
    def __init__(self,mode='expiry',error=None):
        self.mode=mode;self.error=error;self.refreshes=0;self.requests=0;self.valid_refresh='refresh0'
    def post(self,url,data=None,headers=None):
        self.refreshes+=1
        if self.error:return Response(self.error,{'error':'invalid_grant'} if self.error==400 else {})
        if data['refresh_token']!=self.valid_refresh:return Response(400,{'error':'invalid_grant'})
        self.valid_refresh='refresh'+str(self.refreshes)
        return Response(200,{'access_token':'access'+str(self.refreshes),'refresh_token':self.valid_refresh,'expires_in':600})
    def request(self,method,url,headers=None,json=None):
        self.requests+=1
        if self.mode=='401' and headers['Authorization']=='Bearer access0':return Response(401)
        if self.mode=='204':return Response(204)
        return Response(200,{'ok':True})

async def main():
    log_records=[]
    class Capture(logging.Handler):
        def emit(self, record):
            log_records.append(record.getMessage())
    handler=Capture()
    logger=logging.getLogger('custom_components.tado_x.api')
    old_level=logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    for mode in ('expiry','401'):
        session=Session(mode)
        expiry=datetime.now()-timedelta(seconds=1) if mode=='expiry' else datetime.now()+timedelta(minutes=5)
        saves=[]
        api=m.TadoXApi(session,access_token='access0',refresh_token='refresh0',token_expiry=expiry,on_token_refresh=lambda:saves.append(api.refresh_token))
        api.home_id = 2243481 if mode == 'expiry' else 1985739
        result=await asyncio.gather(*(api._request('GET','mock') for _ in range(6)))
        assert any(f'home_id={api.home_id}, reason={"expiry" if mode == "expiry" else "http_401"}, expires_in=600s' in msg for msg in log_records)
        assert session.refreshes==1,(mode,session.refreshes)
        assert len(saves)==1 and len(result)==6
    session=Session('204');api=m.TadoXApi(session,access_token='access0',refresh_token='refresh0',token_expiry=datetime.now()+timedelta(minutes=5))
    assert await api._request('POST','mock') is None
    for status,expected in [(400,m.TadoXAuthError),(401,m.TadoXAuthError),(408,m.TadoXApiError),(429,m.TadoXApiError),(503,m.TadoXApiError)]:
        session=Session(error=status);api=m.TadoXApi(session,refresh_token='refresh0')
        try:await api.refresh_access_token()
        except expected:pass
        else:raise AssertionError(f'{status} did not raise {expected}')
    session=Session();api=m.TadoXApi(session,access_token='access0',refresh_token='refresh0',token_expiry=datetime.now()+timedelta(minutes=5))
    await api._ensure_valid_token();assert session.refreshes==0
    api.home_id=2243481
    await api.refresh_access_token();assert session.refreshes==1
    assert any('home_id=2243481, reason=explicit, expires_in=600s' in msg for msg in log_records)
    logger.removeHandler(handler)
    logger.setLevel(old_level)
    print('PASS: concurrent expiry and 401 (6 requests each), token persistence callback, 204, HTTP error classification, conditional and explicit refresh, per-home refresh-reason logging')
asyncio.run(main())
