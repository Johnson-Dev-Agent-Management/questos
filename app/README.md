# First headset candidate (P1)

One stationary floor, cube, and Exit control. No locomotion, workloads, network,
persistence, telemetry instrumentation, or downloaded content.

Either Touch controller supplies an aim ray. Point at the cube and press trigger
to toggle teal/orange; release and press again to restore teal. Point at Exit and
press trigger, or press B/Y, to quit. The Meta button remains the system-menu
escape. Rays/input require tracking and a focused XR session. Stage space keeps
the floor at the runtime's calibrated floor; the app never changes the boundary.
Start seated or standing in the owner's cleared stationary boundary.

The desktop editor/run helpers turn XR off. Escape/window-close exits. Headless
checks exercise actual ray collisions and color toggling, not physical tracking.

`Quest 2 Candidate` exports an unsigned release APK via a fresh Gradle template.
Godot supplies Khronos loader 1.1.54; a local manifest-only editor adapter adds
Quest 2 identity and VR launch metadata. Vendors 5.1 was evaluated and is not
needed for these core OpenXR inputs. See [provenance](../docs/toolchain-provenance.md)
and the [owner handoff](../docs/p1-headset-handoff.md).

**Not yet hardware tested.** A packaged XR candidate is not a passed P1.
