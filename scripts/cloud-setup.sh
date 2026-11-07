#!/usr/bin/env bash
# Setup command for a project-specific Codex Cloud environment.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bash "$script_dir/setup.sh" --android --accept-android-sdk-license
python3 "$script_dir/dev.py" doctor --android
