# P1 Windows handoff — owner only

P1 is **pending physical evidence**. The unsigned candidate is
`questos-p1-unsigned.apk`, package `org.johnsondev.questos.dev`, version code 2,
version `0.1.0-p1`, arm64, minSdk 29 / targetSdk 32. It is a disposable development
identity, not a retained release. The known device firmware/API remains unknown.
No key, device, or Windows test-station access is granted to the agent.

## Select and inspect

After owner review/merge, select a specific passing Actions run/attempt and source
SHA (not a floating latest link). Download its `quest2-p1-ubuntu-24.04` or
`quest2-p1-windows-2022` artifact directly from GitHub. PR jobs normally build the
synthetic merge SHA; confirm the run's checkout and workflow revision. Each
artifact contains the unsigned APK and `build-manifest.json`; artifacts expire
in three days. A rebuild is a new candidate. Keep the chosen artifact/run identity
and hash in owner-controlled local notes.

Use a separate owner-only signing folder and reviewed, trusted Android build
tools 36.0.0/JDK 17. Receive the APK as input; do not execute candidate repository
scripts in the signing context. Check `Get-FileHash` against that artifact's
manifest and inspect with trusted `aapt2 dump badging` and
`aapt2 dump xmltree <apk> --file AndroidManifest.xml`. Confirm package/version,
SDK 29/32, arm64-only, release/non-debuggable, Quest 2 and focus-aware metadata,
headtracking v1, the exported Godot launcher alias with MAIN + Launcher/Meta VR/
OpenXR immersive categories, and only the two `org.khronos.openxr.permission.*`
permissions (`OPENXR`, `OPENXR_SYSTEM`). Confirm the arm64 OpenXR loader exists;
its unsigned bytes' SHA-256 is
`12b10b0d6f3a93c52f9aaf8b0d2452771eeff6e6d0852fe0ecc16412c6b9c311`.
Do not use the old regular-Android PR #2 smoke APK.

## Align, sign and identify

In PowerShell, set `$BuildTools` to the trusted installed build-tools directory.
Replace the owner key/alias placeholders locally; never paste keys/passwords
into chat or commit them. Use a separate disposable development key for this
development package. Retained keys remain outside agent access.

```powershell
Get-FileHash .\questos-p1-unsigned.apk -Algorithm SHA256
& "$BuildTools\zipalign.exe" -P 16 -f 4 .\questos-p1-unsigned.apk .\questos-p1-aligned.apk
if ($LASTEXITCODE -ne 0) { throw 'Alignment failed' }
& "$BuildTools\zipalign.exe" -c -P 16 -v 4 .\questos-p1-aligned.apk
if ($LASTEXITCODE -ne 0) { throw 'Alignment verification failed' }
& "$BuildTools\apksigner.bat" sign --ks '<owner-local-development-keystore>' --ks-key-alias '<alias>' --out .\questos-p1-signed.apk .\questos-p1-aligned.apk
if ($LASTEXITCODE -ne 0) { throw 'Signing failed' }
& "$BuildTools\apksigner.bat" verify --verbose --print-certs .\questos-p1-signed.apk
if ($LASTEXITCODE -ne 0) { throw 'Signature verification failed' }
Get-FileHash .\questos-p1-aligned.apk -Algorithm SHA256
Get-FileHash .\questos-p1-signed.apk -Algorithm SHA256
```

Record unsigned → aligned → signed hashes and the signing certificate fingerprint
outside the development repository. Do not modify the APK after signing.

## Local USB installation and physical test

This does not authorize resetting or changing firmware. Follow your existing
preservation/provisioning sequence first. Developer mode/USB authorization must
already be owner-authorized. Use only local USB on the Windows test station;
no remote or network ADB. With only the intended headset connected, use trusted
platform-tools `adb install -r .\questos-p1-signed.apk`. If a different signing
certificate is already installed, stop and resolve that locally; do not silently
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
