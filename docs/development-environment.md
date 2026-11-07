# Development environment

The repository foundation needs Git, Python 3.12+, and GitHub CLI for the owner
administration helper. CI uses the GitHub-hosted `ubuntu-24.04` runner. The workflow
records its pinned checkout action and actionlint archive/checksum directly.

The app toolchain has not been selected or verified. Before app implementation:

1. Establish a dedicated development context with no owner-authorized write
   connection across shell, connectors, browser, environment administration,
   or other execution tools. Verify representative harmless permission denials.
2. Keep retained signing keys, release administration, and the Windows test
   station outside this context. Do not configure VPN, remote shell, forwarded
   ADB, or a self-hosted runner on the test station.
3. Select exact compatible Godot, export-template, JDK, Android SDK/build-tools,
   Gradle, arm64 ABI, renderer, and optional Vendors plugin versions. Record
   official source URLs and checksums in the eventual setup recipe.
4. Build from a fresh workspace, inspect the APK, and record source and artifact
   identity. Only then add the export and inspection as a required CI check.

Use existing capacity. Restrict network access to the actual repository and
package/download hosts needed by the selected recipe. Do not add credentials to
the repository or paste secrets into chat. Cache only replaceable downloads;
clean import/export remains a separate reproducibility check.

Current setup used a cloud workspace with the bot's GitHub CLI credentials and
both GitHub connector identities available. It is an authorized administration
context, not a verified isolated implementation context. No headset access,
signing identity, Android SDK setup, or reusable cloud configuration has been
established by this bootstrap.
