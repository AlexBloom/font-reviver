from pathlib import Path
import hashlib
import io
import json
import shutil
import struct
import subprocess
import zipfile
import pytest
from fontTools.ttLib import TTFont, TTCollection
from font_reviver.engine import scan_folder, convert_folder
from font_reviver.formats import apple_double, escape_header, pfb_from_resources
from font_reviver.gallery import write_gallery


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resource_font(blob):
    # One sfnt resource in a complete classic resource map.
    data = struct.pack('>I', len(blob)) + blob
    type_list = struct.pack('>H4sHH', 0, b'sfnt', 0, 10)
    reference = struct.pack('>hh', 128, -1) + b'\0\0\0\0' + b'\0'*4
    header = struct.pack('>IIII', 256, 256+len(data), len(data), 50)
    mapping = header + b'\0'*8 + struct.pack('>HH', 28, 50) + type_list + reference
    return header + b'\0'*(256-16) + data + mapping


def adouble(blob):
    return struct.pack('>II16sH', 0x00051607, 0x00020000, b'\0'*16, 1) + struct.pack('>III', 2, 38, len(blob)) + blob


def test_copy_unchanged_repeat_and_sources_preserved(tmp_path, font_factory):
    src = tmp_path/'Originals'
    f = font_factory(src/'Family'/'Regular.ttf')
    original = sha(f)
    plan = scan_folder(src)
    assert not (tmp_path/'Originals Revived').exists()
    assert plan['records'][0]['fonts'][0]['kind'] == 'modern'
    first = convert_folder(src)
    second = convert_folder(src)
    out = Path(first['output_root'])
    item = first['records'][0]['fonts'][0]
    assert first['summary']['copied'] == second['summary']['copied'] == 1
    assert sha(out/item['output']) == original == sha(f)
    assert len(list((out/'Fonts').rglob('*.ttf'))) == 1
    gallery = (out/'Gallery.html').read_text()
    assert 'id="expand-all"' in gallery and 'id="collapse-all"' in gallery
    assert 'details[data-font]:not([hidden])' in gallery


def test_excludes_nested_output_and_rejects_source_target(tmp_path, font_factory):
    src = tmp_path/'fonts'; font_factory(src/'A.ttf')
    for target in [src, tmp_path]:
        with pytest.raises(ValueError):
            convert_folder(src, target)
    out = src/'Revived'
    assert convert_folder(src, out)['summary']['copied'] == 1
    assert convert_folder(src, out)['summary']['source_entries'] == 1


def test_skips_placeholders_and_symlinks(tmp_path, font_factory, monkeypatch):
    import font_reviver.engine as engine
    src = tmp_path/'source'; font_factory(src/'online.ttf'); font_factory(src/'local.ttf')
    monkeypatch.setattr(engine, 'online_only', lambda p: p.name == 'online.ttf')
    plan = scan_folder(src)
    assert plan['summary']['skipped_online_only'] == 1
    assert len([r for r in plan['records'] if r['fonts']]) == 1
    try:
        (src/'linked.ttf').symlink_to(src/'local.ttf')
    except OSError:
        return
    assert any(r['status']=='skipped_symlink' for r in scan_folder(src)['records'])


def test_zero_data_fork_with_appledouble_and_zip(tmp_path, font_factory):
    base = font_factory(tmp_path/'model.ttf').read_bytes()
    src = tmp_path/'source'; src.mkdir()
    (src/'Legacy.suit').write_bytes(b'')
    fork = resource_font(base)
    (src/'._Legacy.suit').write_bytes(adouble(fork))
    assert apple_double(adouble(fork)) == fork
    result = convert_folder(src)
    assert result['summary']['extracted'] == 1
    assert (Path(result['output_root'])/result['records'][0]['fonts'][0]['output']).read_bytes() == base
    zipped = tmp_path/'zipped'; zipped.mkdir()
    with zipfile.ZipFile(zipped/'collection.zip', 'w') as z:
        z.writestr('Family/Legacy.suit', b'')
        z.writestr('__MACOSX/Family/._Legacy.suit', adouble(fork))
        z.writestr('../escape.ttf', base)
        z.writestr('C:\\escape.ttf', base)
    report = convert_folder(zipped)
    assert report['summary']['extracted'] == 1
    assert sum(r['status']=='skipped_archive_entry' for r in report['records']) == 2
    assert not (tmp_path/'escape.ttf').exists()


def test_invalid_font_quarantined_and_safe_collisions(tmp_path, font_factory):
    src = tmp_path/'source'; src.mkdir()
    (src/'broken.otf').write_bytes(b'OTTOjunk')
    original = font_factory(src/'Valid.ttf')
    out = tmp_path/'output'; (out/'Fonts').mkdir(parents=True)
    (out/'Fonts'/'Valid.ttf').write_bytes(b'unrelated')
    report = convert_folder(src, out)
    assert report['summary']['review_entries'] == 1
    assert (out/'Fonts'/'Valid.ttf').read_bytes() == b'unrelated'
    included = [i for r in report['records'] for i in r['fonts'] if 'output' in i]
    assert len(included)==1 and (out/included[0]['output']).read_bytes() == original.read_bytes()
    assert not (out/'Fonts'/'broken.otf').exists()


def test_collection_all_faces_preserved(tmp_path, font_factory):
    src = tmp_path/'source'; src.mkdir()
    a=font_factory(tmp_path/'a.ttf', 'One'); b=font_factory(tmp_path/'b.ttf', 'Two')
    collection=TTCollection(); collection.fonts=[TTFont(a),TTFont(b)]; collection.save(src/'Pair.ttc')
    report=convert_folder(src)
    item=report['records'][0]['fonts'][0]
    assert len(item['validation']['faces']) == 2
    assert sha(src/'Pair.ttc') == sha(Path(report['output_root'])/item['output'])


def test_header_repair_does_not_touch_encrypted_outline_bytes():
    clear=b'%!PS-AdobeFont-1.0\r/Notice (bad\x00byte\xff) def\rcurrentfile eexec\r'
    encrypted=b'\x00\xff\x01\x02' * 12
    pfb=b'\x80\x01'+struct.pack('<I',len(clear))+clear+b'\x80\x02'+struct.pack('<I',len(encrypted))+encrypted+b'\x80\x03'
    fixed=escape_header(pfb)
    assert fixed and b'bad\\000byte\\377' in fixed
    assert fixed.endswith(b'\x80\x02'+struct.pack('<I',len(encrypted))+encrypted+b'\x80\x03')
    with pytest.raises(ValueError):
        escape_header(b'\x80\x01\xff\xff\xff\xff')


def test_output_symlink_does_not_write_into_originals(tmp_path, font_factory):
    src=tmp_path/'source'; font_factory(src/'A.ttf')
    out=tmp_path/'output'; out.mkdir()
    try:
        (out/'Fonts').symlink_to(src, target_is_directory=True)
    except OSError:
        pytest.skip('Symlinks unavailable')
    before={p.name:sha(p) for p in src.iterdir()}
    report=convert_folder(src,out)
    assert report['summary']['included_files']==0
    assert before=={p.name:sha(p) for p in src.iterdir()}


@pytest.mark.skipif(not shutil.which('fontforge'), reason='FontForge integration needs external tool')
def test_legacy_conversion_and_cache(tmp_path, font_factory):
    sourcefont=font_factory(tmp_path/'model.ttf')
    src=tmp_path/'legacy';src.mkdir()
    pfb=src/'Test.pfb'
    subprocess.run(['fontforge','-lang=py','-c','import fontforge,sys; f=fontforge.open(sys.argv[1]); f.generate(sys.argv[2]); f.close()',str(sourcefont),str(pfb)],check=True,capture_output=True)
    original=sha(pfb)
    first=convert_folder(src,jobs=2);second=convert_folder(src,jobs=2)
    item=next(i for r in first['records'] for i in r['fonts'] if i['status']=='converted')
    assert first['summary']['converted']==second['summary']['converted']==1
    assert item['width_changes']==[] and item['glyphs']>=4
    assert sha(pfb)==original
    assert len(list((Path(first['output_root'])/'Fonts').glob('*.otf')))==1
