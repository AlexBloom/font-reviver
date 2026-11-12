import json
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path
from font_reviver.cli import main
from font_reviver.server import make_server


def test_cli_stdout_json(tmp_path,font_factory,capsys):
    src=tmp_path/'source';font_factory(src/'A.ttf')
    assert main(['scan',str(src)])==0
    report=json.loads(capsys.readouterr().out)
    assert report['schema_version']==1 and report['operation']=='scan'
    assert main(['convert',str(src),'--output',str(src)])==2
    assert 'error' in json.loads(capsys.readouterr().out)


def test_http_auth_job_and_result_allowlist(tmp_path,font_factory):
    src=tmp_path/'source';font_factory(src/'A.ttf')
    server,app=make_server(0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_address[1]}'
    def request(path,body=None,token=None,origin=None):
        headers={}
        if token:headers['X-Font-Reviver-Token']=token
        if origin:headers['Origin']=origin
        if body is not None:headers['Content-Type']='application/json'
        req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        return urllib.request.urlopen(req)
    try:
        with request('/') as response:
            assert b'Font Reviver' in response.read()
        for endpoint,origin in [('/api/status',None),('/api/status','https://other.example')]:
            try:request(endpoint,token=app.token if origin else None,origin=origin)
            except urllib.error.HTTPError as error:assert error.code==403
            else:raise AssertionError('Untrusted call was accepted')
        with request('/api/convert',{'source':str(src)},app.token) as response:assert response.status==202
        for _ in range(100):
            with request('/api/status',token=app.token) as response:status=json.load(response)
            if not status['running']:break
            time.sleep(.05)
        assert status['phase']=='complete' and status['summary']['included_files']==1
        with request(status['gallery']) as response:assert b'Expand all' in response.read()
        try:request(f'/results/{app.token}/.font-reviver/lock')
        except urllib.error.HTTPError as error:assert error.code==404
        else:raise AssertionError('Private work path was served')
    finally:
        server.shutdown();server.server_close();thread.join()


def test_versioned_report_schema(tmp_path,font_factory):
    import jsonschema
    from font_reviver.engine import scan_folder,convert_folder
    source=tmp_path/'fonts';font_factory(source/'A.ttf')
    schema=json.loads((Path(__file__).parents[1]/'docs/report.schema.json').read_text())
    jsonschema.validate(scan_folder(source),schema)
    jsonschema.validate(convert_folder(source),schema)
