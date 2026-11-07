# Toolchain provenance

`toolchain.lock.json` is the source of exact versions, download URLs, and SHA-256
digests. Setup never requests `latest`. It installs only inside `.tools/`.

| Component | Pinned selection |
| --- | --- |
| Godot editor and templates | 4.6.3 stable, standard GDScript build |
| JDK | Eclipse Temurin 17.0.21+9, x64 |
| Android build tools | 36.0.0 |
| Android platform | API 36, revision 2 |
| Android platform tools | 37.0.1 |
| Renderer | Compatibility / OpenGL |
| Android output | Unsigned arm64 Gradle/OpenXR candidate, minSdk 29, targetSdk 32 |
| Gradle / Android Gradle plugin | 8.11.1 / 8.6.1 |
| Kotlin / AndroidX | 2.1.21 / full resolved coordinates in `scripts/android/gradle.lockfile` |
| OpenXR loader | Khronos `openxr_loader_for_android:1.1.54`, Maven Central |
| NDK | Not used: precompiled Godot libraries, no second stripping pass |
| Vendors plugin | 5.1.0-stable evaluated at `7afcd397e6206d9751b82100559ff39a93a8f59e`; not included |

Godot 4.6.3 is the conservative 4.6-series baseline already present in the cloud
image. The scripts download and verify their own copy instead of trusting the
image's unpinned global executable. This selection is not a claim that it is the
latest Godot release or that it works on the owner's headset.

Godot and Temurin SHA-256 values were checked against the official GitHub release
asset metadata. Google's SDK archives were downloaded from `dl.google.com`,
checked against Google's repository XML checksums, and then hashed with SHA-256
for this lock. The original SHA-1 values are retained as provenance metadata;
every setup uses the recorded SHA-256 values for verification.

Sources inspected during setup:

- [Godot 4.6.3 release](https://github.com/godotengine/godot-builds/releases/tag/4.6.3-stable)
- [Temurin 17.0.21+9 release](https://github.com/adoptium/temurin17-binaries/releases/tag/jdk-17.0.21%2B9)
- [Google SDK package metadata](https://dl.google.com/android/repository/repository2-1.xml)
- [Godot 4.6 Android export documentation](https://docs.godotengine.org/en/4.6/tutorials/export/exporting_for_android.html)
- [Godot Android XR guidance](https://docs.godotengine.org/en/4.6/tutorials/xr/deploying_to_android.html)

The 4.6-series documentation's SDK examples differ from the 4.6.3 binary
templates. Package inspection established API 36 in the selected templates, so
this recipe uses the matching API 36 tooling. A clean import needs ETC2/ASTC
texture import enabled even for the small Compatibility scene.

Only Android templates (`android_debug.apk`, `android_release.apk`, and
`android_source.zip`) are extracted from the full upstream template archive.
The Gradle project is freshly extracted at export time, never committed as a
large generated Android tree. The template's build-tools 36.1.0 constant is
explicitly replaced by the already verified 36.0.0 selection. Compile SDK remains
36. AGP 8.6.1 emits an upstream warning that it was tested through compile SDK
35; both platform exports must pass with the pinned template combination. We do
not suppress this warning or claim official API 36 certification from it.

Gradle's distribution SHA-256 comes from its official `.sha256` sidecar at
[downloads.gradle.org](https://downloads.gradle.org/distributions/gradle-8.11.1-bin.zip.sha256).
Resolved Maven artifacts and metadata are SHA-256 pinned in
`scripts/android/verification-metadata.xml`; exact application dependency
versions are locked in the adjacent Gradle lockfiles. The hashes cover the
resolved graph, including tooling and the native Windows aapt2 classifier.
These files' digests are themselves recorded in `toolchain.lock.json`.
Generated checksums identify the downloaded bytes, not an independent security
audit of every transitive dependency. New artifacts require explicit owner review.

The actual 4.6.3 editor requests loader **1.1.54** during OpenXR export, despite
the template config's unused 1.1.53 constant. The lock records the observed
coordinate. The bundled `libopenxr_loader.so` must exactly match the arm64 member
of the [Khronos AAR](https://repo.maven.apache.org/maven2/org/khronos/openxr/openxr_loader_for_android/1.1.54/openxr_loader_for_android-1.1.54.aar).
It discovers the headset's runtime; the runtime/Quest drivers are not bundled.

Vendors v5.1 was evaluated against its pinned
[Meta manifest](https://github.com/GodotVR/godot_openxr_vendors/blob/7afcd397e6206d9751b82100559ff39a93a8f59e/plugin/src/meta/AndroidManifest.xml)
and [export adapter](https://github.com/GodotVR/godot_openxr_vendors/blob/7afcd397e6206d9751b82100559ff39a93a8f59e/plugin/src/main/cpp/export/meta_export_plugin.cpp).
P1 only needs standard Touch aim/trigger/button actions. Godot supplies the
loader, broker queries and OpenXR intent; the small local editor adapter adds
`quest2`, focus-aware metadata and Meta's VR intent. No vendor extension,
Horizon SDK minimum, vendor native library, or camera/hand-tracking permission is
introduced. Revisit Vendors when a concrete feature needs it or device evidence
shows this path insufficient. This choice still requires physical validation.

The APK inspection checks the exported launcher alias targets Godot's activity,
its MAIN filters contain Launcher/Meta VR/OpenXR immersive categories, the
headtracking declaration exists, the exact permissions match, backup is off,
and every packaged library is arm64 ELF64. It rejects a regular Android launch
mode, loader substitution and signing metadata. Runtime compatibility, working
tracking, offline launch and normal headset exit remain owner observations.
