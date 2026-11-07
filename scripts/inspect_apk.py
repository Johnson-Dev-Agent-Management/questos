"""Inspect actual unsigned Quest candidate bytes; hardware behavior is not proven."""

import hashlib
from pathlib import Path
import re
import struct
import subprocess
import zipfile

from bootstrap import sha256

PACKAGE = "org.johnsondev.questos.dev"
PERMISSIONS = ["org.khronos.openxr.permission.OPENXR", "org.khronos.openxr.permission.OPENXR_SYSTEM"]


def manifest_tree(dump):
    """Parse aapt2 xmltree hierarchy so unrelated names/values cannot satisfy checks."""
    root = {"tag": "root", "attrs": {}, "children": []}
    stack = [(-1, root)]
    for line in dump.splitlines():
        indent = len(line) - len(line.lstrip())
        element = re.match(r'\s*E: ([\w-]+)', line)
        if element:
            while stack[-1][0] >= indent:
                stack.pop()
            node = {"tag": element[1], "attrs": {}, "children": []}
            stack[-1][1]["children"].append(node)
            stack.append((indent, node))
        attr = re.match(r'\s*A: (?:http[^ ]*:)?([\w]+)(?:\(0x[0-9a-f]+\))?=(.*)', line)
        if attr:
            value = attr[2].split(' (Raw:', 1)[0].strip('"')
            stack[-1][1]["attrs"][attr[1]] = value
    return root


def children(node, tag):
    return [child for child in node['children'] if child['tag'] == tag]


def validate_xr_manifest(dump):
    manifest = children(manifest_tree(dump), 'manifest')[0]
    app = children(manifest, 'application')[0]
    metadata = {n['attrs'].get('name'): n['attrs'].get('value') for n in children(app, 'meta-data')}
    if metadata.get('com.oculus.supportedDevices') != 'quest2' or metadata.get('com.oculus.vr.focusaware') != 'true':
        raise RuntimeError('Quest 2 application metadata is missing or incorrect.')
    features = [n['attrs'] for n in children(manifest, 'uses-feature')]
    if not any(n.get('name') == 'android.hardware.vr.headtracking' and n.get('version') == '1' for n in features):
        raise RuntimeError('VR headtracking feature is missing.')
    activities = children(app, 'activity')
    main = next((n for n in activities if n['attrs'].get('name') == 'com.godot.game.GodotApp'), None)
    launch = next((n for n in children(app, 'activity-alias') if n['attrs'].get('targetActivity') == 'com.godot.game.GodotApp' and n['attrs'].get('exported') == 'true'), None)
    if main is None or launch is None:
        raise RuntimeError('Exported headset launcher alias must target the Godot activity.')
    categories = set()
    for intent in children(launch, 'intent-filter'):
        if any(a['attrs'].get('name') == 'android.intent.action.MAIN' for a in children(intent, 'action')):
            categories.update(c['attrs'].get('name') for c in children(intent, 'category'))
    required = {'android.intent.category.LAUNCHER', 'com.oculus.intent.category.VR', 'org.khronos.openxr.intent.category.IMMERSIVE_HMD'}
    if not required <= categories:
        raise RuntimeError('Main activity lacks Quest/OpenXR immersive launch categories.')
    queries = children(manifest, 'queries')
    providers = [p['attrs'].get('authorities', '') for q in queries for p in children(q, 'provider')]
    if not any('org.khronos.openxr.runtime_broker' in p for p in providers):
        raise RuntimeError('OpenXR runtime discovery query is missing.')
    if app['attrs'].get('allowBackup') != 'false':
        raise RuntimeError('Candidate backup must be disabled.')
    return sorted(categories)


def inspect_apk(apk, config, env):
    lock = config['toolchain']
    suffix = '.exe' if config['host'] == 'windows' else ''
    tool = Path(config['android_home']) / 'build-tools' / lock['android_build_tools'] / ('aapt2' + suffix)

    def dump(*args):
        result = subprocess.run([str(tool), 'dump', *args], env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
                                encoding='utf-8', errors='replace')
        if result.returncode:
            raise RuntimeError(f'APK inspection failed: {result.stderr}')
        return result.stdout

    badging = dump('badging', str(apk))
    manifest = dump('xmltree', str(apk), '--file', 'AndroidManifest.xml')
    if f"package: name='{PACKAGE}' versionCode='2' versionName='0.1.0-p1'" not in badging:
        raise RuntimeError('Unexpected APK package or version identity.')
    if not re.search(r"(?:minSdkVersion|sdkVersion):'29'", badging) or "targetSdkVersion:'32'" not in badging:
        raise RuntimeError('Unexpected Android SDK compatibility.')
    if "native-code: 'arm64-v8a'" not in badging or 'application-debuggable' in badging:
        raise RuntimeError('Expected a non-debuggable arm64-only release export.')
    permissions = sorted(set(re.findall(r"uses-permission(?:-sdk-\d+)?: name='([^']+)'", badging)))
    if permissions != PERMISSIONS:
        raise RuntimeError('Unexpected APK permissions: ' + ', '.join(permissions))
    try:
        categories = validate_xr_manifest(manifest)
    except (IndexError, KeyError) as error:
        raise RuntimeError('Malformed or incomplete XR manifest.') from error
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        abis = sorted({name.split('/')[1] for name in names if name.startswith('lib/') and name.endswith('.so')})
        if abis != ['arm64-v8a']:
            raise RuntimeError(f'Unexpected native-library ABIs: {abis}')
        if 'lib/arm64-v8a/libopenxr_loader.so' not in names:
            raise RuntimeError('OpenXR runtime loader is missing.')
        loader = archive.read('lib/arm64-v8a/libopenxr_loader.so')
        loader_digest = hashlib.sha256(loader).hexdigest()
        if loader_digest != lock['openxr_loader_arm64_sha256']:
            raise RuntimeError('OpenXR runtime loader does not match the locked Khronos AAR.')
        for name in (n for n in names if n.startswith('lib/') and n.endswith('.so')):
            header = archive.read(name)[:20]
            if header[:6] != b'\x7fELF\x02\x01' or struct.unpack('<H', header[18:20])[0] != 183:
                raise RuntimeError(f'Native library is not AArch64 ELF64: {name}')
        command = archive.read('assets/_cl_')
        if b'--xr_mode_openxr' not in command or b'--xr_mode_regular' in command or b'--xr-mode' in command:
            raise RuntimeError('Expected OpenXR launch mode without a desktop XR override.')
        if any(re.match(r'META-INF/.*\.(SF|RSA|DSA|EC)$', name, re.I) for name in names):
            raise RuntimeError('Development APK unexpectedly contains signing metadata.')
        with apk.open('rb') as stream:
            stream.seek(max(0, archive.start_dir - 16))
            if stream.read(16) == b'APK Sig Block 42':
                raise RuntimeError('Development APK unexpectedly contains an APK signing block.')
    return {'apk_sha256': sha256(apk), 'package': PACKAGE, 'version_code': 2,
            'version_name': '0.1.0-p1', 'minimum_sdk': 29, 'target_sdk': 32,
            'abis': abis, 'permissions': permissions, 'xr_headset_candidate': True,
            'xr_launch_categories': categories, 'openxr_loader_version': lock['openxr_loader'],
            'openxr_loader_sha256': loader_digest, 'hardware_validation': 'not run',
            'signing': 'unsigned', 'size_bytes': apk.stat().st_size}
