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
| Android output | Unsigned arm64 standard template smoke export, minSdk 24, targetSdk 36 |
| Gradle, NDK, Vendors plugin | Not installed or used; evaluate with XR packaging for P1 |

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

Only Android templates are extracted from Godot's full template archive. This
avoids installing unrelated desktop exporters; the upstream download is still
approximately 1.25 GB. Standard export uses prebuilt engine libraries and does
not compile native code or fetch Maven dependencies.
