# P1 Windows handoff — owner only

P1 is **pending physical evidence**. The unsigned candidate is
`questos-p1-unsigned.apk`, package `org.johnsondev.questos.dev`, version code 2,
version `0.1.0-p1`, arm64, minSdk 29 / targetSdk 32. It is a disposable development
identity, not a retained release. The known device firmware/API remains unknown.
No key, device, or Windows test-station access is granted to the agent.

## Select the candidate

After owner review/merge, select a specific passing Actions run/attempt and source
SHA (not a floating latest link). Download its `quest2-p1-ubuntu-24.04` or
`quest2-p1-windows-2022` artifact directly from GitHub. PR jobs normally build the
synthetic merge SHA; confirm the run's checkout and workflow revision. Each
artifact contains the unsigned APK and `build-manifest.json`; artifacts expire
in three days. A rebuild is a new candidate. Cross-check the source and workflow
against GitHub's run/checkout metadata, not just the artifact's manifest. Keep the
chosen artifact/run identity and hash in owner-controlled local notes.

The owner reported successful local tool setup and signing of this first Windows
candidate using the procedure below:

| Field | First signed development candidate's unsigned input |
| --- | --- |
| Source | `8e374e1d21d1e6f2992adab7d6d12d130e30a405` |
| Actions run | [42427663747, attempt 1](https://github.com/Johnson-Dev-Agent-Management/questos/actions/runs/42427663747) |
| Artifact | [13596401126, quest2-p1-windows-2022](https://github.com/Johnson-Dev-Agent-Management/questos/actions/runs/42427663747/artifacts/13596401126) |
| Unsigned APK SHA-256 | `f5f2ab7aedd9cec9a52088e8e51760a9c96b2adc6838382bfb82a7191ffddcf2` |

This is a historical reference, not a default hash for future builds or the
artifact ZIP's hash. The signed hash and certificate record stay owner-local.
Successful signing does not establish headset installation or a P1 pass.

## Install the owner tools once (Windows x64)

Use ordinary Windows PowerShell; administrator privileges, Android Studio, Git,
and Python are unnecessary for this handoff. Review the
[Android SDK terms](https://developer.android.com/studio/terms); run the following
block only if you accept them. Read and use an owner-reviewed copy of this
procedure. It installs official Temurin JDK 17.0.21+9, Android build-tools 36.0.0,
and platform-tools 37.0.1 with the URLs/checksums in
[toolchain.lock.json](../toolchain.lock.json). Keep those pins and this procedure
in sync when reviewing toolchain updates.

The tools go under `%LOCALAPPDATA%\QuestOS\OwnerTools`. The block does not need
Java on PATH and does not change the machine PATH or an existing SDK. Paste the
whole block, including `& { ... }`, so an error stops the remaining commands.
Wait for **Tools installed successfully** before proceeding. Downloading and
extracting the archives can take several minutes.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    $ToolRoot = "$env:LOCALAPPDATA\QuestOS\OwnerTools"
    New-Item -ItemType Directory -Force -Path $ToolRoot | Out-Null

    $Packages = @(
        @{
            Name = 'java'
            Url = 'https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.21%2B9/OpenJDK17U-jdk_x64_windows_hotspot_17.0.21_9.zip'
            Sha256 = '98518ecf554465057ee5509462631deeee374bc368c12a411d225cd29381f84b'
        }
        @{
            Name = 'build-tools'
            Url = 'https://dl.google.com/android/repository/build-tools_r36_windows.zip'
            Sha256 = 'aa1095cb14d83e483818a748a2c06faaeb8e601561b06a356a119a1b2ca280d3'
        }
        @{
            Name = 'platform-tools'
            Url = 'https://dl.google.com/android/repository/platform-tools_r37.0.1-win.zip'
            Sha256 = '45f4d63113e895ebde0c90f194099a4676b6ac653bd28d54314a9e022bbc1a99'
        }
    )

    foreach ($Package in $Packages) {
        $Archive = Join-Path $ToolRoot ($Package.Name + '.zip')
        Write-Host "Preparing $($Package.Name)..."

        if (-not (Test-Path -LiteralPath $Archive)) {
            Invoke-WebRequest -UseBasicParsing -Uri $Package.Url -OutFile $Archive
        }

        if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash -ne $Package.Sha256) {
            throw "Checksum mismatch: $Archive. Stop here."
        }

        Expand-Archive -LiteralPath $Archive `
            -DestinationPath (Join-Path $ToolRoot $Package.Name) -Force
    }

    & "$ToolRoot\java\jdk-17.0.21+9\bin\java.exe" -version
    if ($LASTEXITCODE -ne 0) { throw 'Java verification failed' }

    Write-Host 'Tools installed successfully.'
}
```

## Inspect the unsigned APK

Use a separate owner-only signing folder and reviewed, trusted Android build
tools 36.0.0/JDK 17. Receive the APK and manifest as input; do not execute candidate
repository scripts in the signing context. Open PowerShell in that folder. Check
the unsigned hash against the selected run's export log and artifact manifest;
the checksum does not replace the source/run checks above.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $BuildTools = "$env:LOCALAPPDATA\QuestOS\OwnerTools\build-tools\android-16"

    Get-FileHash .\questos-p1-unsigned.apk -Algorithm SHA256
    Get-Content .\build-manifest.json
    & "$BuildTools\aapt2.exe" dump badging .\questos-p1-unsigned.apk
    if ($LASTEXITCODE -ne 0) { throw 'Package inspection failed' }
    & "$BuildTools\aapt2.exe" dump xmltree .\questos-p1-unsigned.apk --file AndroidManifest.xml
    if ($LASTEXITCODE -ne 0) { throw 'Manifest inspection failed' }
}
```

Review the output before signing. Confirm package/version,
SDK 29/32, arm64-only, release/non-debuggable, Quest 2 and focus-aware metadata,
headtracking v1, the exported Godot launcher alias with MAIN + Launcher/Meta VR/
OpenXR immersive categories, and only the two `org.khronos.openxr.permission.*`
permissions (`OPENXR`, `OPENXR_SYSTEM`). Confirm the arm64 OpenXR loader exists;
its unsigned bytes' SHA-256 is
`12b10b0d6f3a93c52f9aaf8b0d2452771eeff6e6d0852fe0ecc16412c6b9c311`.
Do not use the old regular-Android PR #2 smoke APK.

## Create a development key, align, sign and identify

Run the whole block below from the folder containing the unsigned APK. When
prompted, enter the **unsigned APK SHA-256 from the selected passing CI run**,
cross-checked during inspection. For the historical candidate above, use its
listed hash. For a different build, select and inspect that candidate's own hash;
do not substitute a new hash just to bypass a mismatch.

On the first run, `keytool` creates a separate development key and prompts for a
password twice. `apksigner` then asks for that same password. Typed passwords may
not display; never paste them into chat, commands, or the repository. The key uses
RSA 3072, PKCS12 format, alias `questos-dev`, and a 3,650-day certificate validity.
Subsequent runs reuse the existing key without replacing it.

Keep `%LOCALAPPDATA%\QuestOS\Keys\questos-dev.p12` and its password for future
updates to this development installation. This location is outside the repository
and the OneDrive Documents folder; keep it and any backup inaccessible to agents.
It is a separate development signing identity. Retained release keys remain
outside agent access. Do not regenerate the key to resolve a password/signature
error: a different certificate cannot update the existing installation.

```powershell
& {
    $ErrorActionPreference = 'Stop'

    $ToolRoot = "$env:LOCALAPPDATA\QuestOS\OwnerTools"
    $env:JAVA_HOME = "$ToolRoot\java\jdk-17.0.21+9"
    $BuildTools = "$ToolRoot\build-tools\android-16"

    $KeyDirectory = "$env:LOCALAPPDATA\QuestOS\Keys"
    $Keystore = "$KeyDirectory\questos-dev.p12"

    $ExpectedHash = (Read-Host 'Unsigned APK SHA-256 from the selected CI run').Trim()
    if ($ExpectedHash -notmatch '^[0-9a-fA-F]{64}$') {
        throw 'Expected a 64-character SHA-256 hash. Stop here.'
    }
    $ActualHash = (Get-FileHash .\questos-p1-unsigned.apk -Algorithm SHA256).Hash
    if ($ActualHash -ne $ExpectedHash) {
        throw 'Unexpected APK hash. Stop here.'
    }

    New-Item -ItemType Directory -Force -Path $KeyDirectory | Out-Null

    # Create once; subsequent runs reuse the existing development key.
    if (-not (Test-Path -LiteralPath $Keystore)) {
        & "$env:JAVA_HOME\bin\keytool.exe" -genkeypair `
            -keystore $Keystore -storetype PKCS12 `
            -alias questos-dev -keyalg RSA -keysize 3072 `
            -validity 3650 -dname 'CN=QuestOS Development'
        if ($LASTEXITCODE -ne 0) { throw 'Key creation failed' }
    }

    & "$BuildTools\zipalign.exe" -P 16 -f 4 `
        .\questos-p1-unsigned.apk .\questos-p1-aligned.apk
    if ($LASTEXITCODE -ne 0) { throw 'Alignment failed' }

    & "$BuildTools\zipalign.exe" -c -P 16 -v 4 .\questos-p1-aligned.apk
    if ($LASTEXITCODE -ne 0) { throw 'Alignment verification failed' }

    & "$BuildTools\apksigner.bat" sign `
        --ks $Keystore --ks-key-alias questos-dev `
        --out .\questos-p1-signed.apk .\questos-p1-aligned.apk
    if ($LASTEXITCODE -ne 0) { throw 'Signing failed' }

    & "$BuildTools\apksigner.bat" verify --verbose --print-certs `
        .\questos-p1-signed.apk
    if ($LASTEXITCODE -ne 0) { throw 'Signature verification failed' }

    Get-FileHash .\questos-p1-unsigned.apk -Algorithm SHA256
    Get-FileHash .\questos-p1-aligned.apk -Algorithm SHA256
    Get-FileHash .\questos-p1-signed.apk -Algorithm SHA256

    Write-Host 'SUCCESS: questos-p1-signed.apk is ready for USB installation.'
    Write-Host "Keep your development keystore at: $Keystore"
}
```

`zipalign` arranges the APK contents for Android loading before signing, including
16 KiB native-library page alignment. Signing adds the development identity;
signature verification checks the resulting APK. The password protects the key,
not the APK. `JAVA_HOME` is set for this PowerShell session; no persistent system
environment change is required.

Record unsigned → aligned → signed hashes and the signing certificate fingerprint
outside the development repository. Do not modify the APK after signing. Re-signing
or rebuilding produces a new candidate requiring its own identity and test record.

## Troubleshooting setup and signing

| Symptom | Meaning and next step |
| --- | --- |
| `\zipalign.exe` or `\apksigner.bat` is not recognized | `$BuildTools` was empty. Use the complete blocks above, which set the path locally. |
| `java` is not recognized, or Android Studio's default SDK directory is missing | A global installation is unnecessary. Install the owner tools above; use their explicit paths and the signing block's `JAVA_HOME`. |
| Download checksum mismatch | Stop. An interrupted download can leave an incomplete ZIP. Remove only the named cached ZIP from `OwnerTools`, then retry the official download; do not change the expected checksum. |
| Aligned or signed APK is missing | An earlier command failed. Resolve the first error and rerun the complete block; later file-not-found errors are consequences. |
| Keystore password/alias or signature mismatch | Preserve the existing keystore. Check the locally retained password and `questos-dev` alias; do not silently replace the key or uninstall the app. |

Retain the first error message for diagnosis; never share the keystore or password.

## Local USB installation and physical test

This does not authorize resetting or changing firmware. Follow your existing
preservation/provisioning sequence first. Developer mode/USB authorization must
already be owner-authorized. Use only local USB on the Windows test station;
no remote or network ADB. With only the intended headset connected by USB, run the
following from the signed APK's folder. The `-d` flag selects a USB device and
fails if more than one USB device is connected.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $Adb = "$env:LOCALAPPDATA\QuestOS\OwnerTools\platform-tools\platform-tools\adb.exe"
    & $Adb -d install -r .\questos-p1-signed.apk
    if ($LASTEXITCODE -ne 0) { throw 'USB installation failed' }
}
```

This command installs the APK; the tool setup and signing blocks do not contact
the headset. If a different signing certificate is already installed, stop and
resolve that locally; do not silently
uninstall an existing app or bypass signature checks. Keep device identifiers
and any diagnostic logs private.

Disconnect USB/PC and turn off headset networking. In a clear stationary
boundary, seated or standing:

1. Open **QuestOS P1** from the headset's app library/Unknown Sources UI. Confirm
   an immersive stationary scene, head tracking and a floor/cube at usable height.
2. Aim each controller ray at the cube and press/release trigger: teal → orange →
   teal. An off-target press should do nothing. No locomotion or growing load.
3. Select **Exit** with a trigger. Relaunch and check B/Y exit. Open the Meta system
   menu and verify normal system exit/resume; input should be inactive under it.
4. Relaunch from the headset UI offline again; confirm baseline teal and normal exit.

Stop for discomfort, tracking problems or inability to exit. Record pass/fail/
not-run against the **exact signed hash**, source/run identity, firmware/API if
available through ordinary UI, controller behavior and exit observations. No
telemetry or performance acceptance is claimed. P1 passes only after the owner
observes offline standalone launch, rendering, controller input and normal exit
for those exact signed bytes. Keep the accepted APK and private record outside
agent write access.
