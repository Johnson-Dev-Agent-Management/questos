# Development scene and first headset milestone

Open this project with `python scripts/dev.py editor` from the repository root.
It contains a stationary floor, cube, and title using the Compatibility renderer.
The desktop helpers explicitly disable XR so no desktop runtime is required.
The scene has an XROrigin/XRCamera and enables the XR viewport when an initialized
runtime exists, but controller interaction has not been implemented.

`Android Smoke` exports an unsigned, non-debuggable, arm64 regular-Android APK.
It verifies the installed tools and package inspection path. One-click device
deployment is disabled, which also prevents Godot's automatic ADB device polling
for this preset. The scripts never install an APK or operate a headset.

Inspection of Godot 4.6.3's standard export found no XR immersive activity
metadata or separately packaged OpenXR loader. Do not install/promote the smoke
APK as a VR candidate or mark P1 complete. The first headset milestone must add
and verify the appropriate Gradle/XR packaging, evaluate the Vendors plugin,
add controller input, and obtain owner-observed standalone launch and exit.

The toolchain is pinned in `toolchain.lock.json`. Current Android templates use
minSdk 24 and targetSdk 36. Gradle, native compilation, and the Vendors plugin
are not part of the current smoke export. No clock or thermal controls, root,
launcher replacement, firmware changes, or device reset belong to app setup.
