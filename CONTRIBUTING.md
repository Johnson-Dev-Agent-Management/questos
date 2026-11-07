# Contributing

Start with a short issue or an agreed task. Keep one small, coherent PR active.
Include the concrete behavior changed, validation performed, and remaining
limitations. Never include serial numbers, account identifiers, raw device logs,
signing keys, or private acceptance records in public issues or commits.

Use topic branches and squash merges. `Joshbomb75` owns code review and merges;
`codexcodemachine` proposes implementation changes. CI and agent review inform
the owner's decision but do not replace human acceptance.

Repository checks:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/admin/configure_repository.py --plan
```

CI also validates workflow syntax and exercises fresh toolchain setup and clean
Android smoke exports on Windows and Linux. The required `repository-checks`
gate depends on both platform jobs. Required checks must keep stable names and
report on every PR. Updates to checks, toolchain.lock.json, dependencies,
fixtures, thresholds, exclusions, and permissions require owner review.

For app changes, record the source/toolchain and exact APK identity. Physical
testing is performed by the owner. An ordinary app iteration needs affected
smoke checks; the complete lifecycle matrix belongs to retained releases.

Do not add a new language, native library, service, persistent framework, or
recurring paid dependency without a concrete need and scope decision.
