"""Prepare a fresh, locked Godot Gradle project; never use a developer's build tree."""

import os
from pathlib import Path
import shutil
from urllib.parse import urlparse

from bootstrap import ROOT, TOOLS, extract, sha256


def gradle_environment(env):
    env = env.copy()
    env['GRADLE_USER_HOME'] = str(TOOLS / 'gradle-user-home')
    options = env.get('JAVA_TOOL_OPTIONS', '')
    # Gradle/Java do not consume HTTP(S)_PROXY themselves. Preserve TLS validation.
    for protocol in ('http', 'https'):
        proxy = env.get(protocol.upper() + '_PROXY') or env.get(protocol + '_proxy')
        if proxy:
            parsed = urlparse(proxy)
            if parsed.username or parsed.password:
                raise RuntimeError('Authenticated proxies need a separately configured Java proxy; do not put credentials in build logs.')
            options += f' -D{protocol}.proxyHost={parsed.hostname} -D{protocol}.proxyPort={parsed.port or 80}'
    # Managed Linux supplies an OS-maintained Java trust store with its proxy CA.
    # Native Windows uses Temurin's trust store unless the operator selects one.
    trust = env.get('QUESTOS_JAVA_TRUSTSTORE')
    if not trust and env.get('SSL_CERT_FILE') and Path('/etc/ssl/certs/java/cacerts').is_file():
        trust = '/etc/ssl/certs/java/cacerts'
    if trust:
        options += f' -Djavax.net.ssl.trustStore="{trust}"'
    if options.strip():
        env['JAVA_TOOL_OPTIONS'] = options.strip()
    return env


def prepare_gradle(project, config):
    lock = config['toolchain']
    template = Path(config['godot']).parent / 'editor_data/export_templates/4.6.3.stable/android_source.zip'
    destination = project / 'android/build'
    destination.mkdir(parents=True)
    extract(template, destination)
    (project / 'android/.build_version').write_text('4.6.3.stable', encoding='utf-8')
    # The engine binaries are precompiled. Retain the baseline build tools and
    # do not fetch an NDK just to strip already-stripped libraries.
    path = destination / 'config.gradle'
    path.write_text(path.read_text().replace("buildTools         : '36.1.0'", f"buildTools         : '{lock['android_build_tools']}'"), encoding='utf-8')
    props = destination / 'gradle.properties'
    props.write_text(props.read_text().replace('-Xmx4536m', '-Xmx2048m') + '\norg.gradle.daemon=false\norg.gradle.workers.max=2\ndoNotStrip=true\n', encoding='utf-8')
    wrapper = destination / 'gradle/wrapper/gradle-wrapper.properties'
    distribution = (TOOLS / 'downloads' / lock['assets']['gradle']['file']).as_uri()
    wrapper.write_text('distributionUrl=' + distribution + '\ndistributionSha256Sum=' + lock['assets']['gradle']['sha256'] + '\n', encoding='utf-8')
    if os.name != 'nt':
        (destination / 'gradlew').chmod(0o755)
    for name, digest in lock['android_dependency_files'].items():
        if sha256(ROOT / 'scripts/android' / name) != digest:
            raise RuntimeError(f'Android dependency lock checksum mismatch: {name}')
    for name in ('verification-metadata.xml',):
        source = ROOT / 'scripts/android' / name
        shutil.copy2(source, destination / 'gradle' / name)
    for name in ('gradle.lockfile', 'assetPackInstallTime/gradle.lockfile'):
        source = ROOT / 'scripts/android' / name
        shutil.copy2(source, destination / name)
    with (destination / 'build.gradle').open('a', encoding='utf-8') as output:
        output.write('\nallprojects { dependencyLocking { lockAllConfigurations(); lockMode = LockMode.STRICT } }\n')
    return destination
