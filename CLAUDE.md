# OctoHue — Claude Code context

This file gives Claude Code the project context it needs to assist effectively. If you are a human contributor, the same information is covered in [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## Project overview

OctoHue is an OctoPrint plugin (Python + KnockoutJS) that controls Philips Hue lights based on print events. It communicates with the Hue bridge via the **v2 CLIP API** over HTTPS, verified against the bundled Signify root CA certificate.

**Key files:**
- `octoprint_octohue/__init__.py` — the entire Python plugin
- `octoprint_octohue/static/js/OctoHue.js` — KnockoutJS viewmodel
- `octoprint_octohue/templates/octohue_settings.jinja2` — settings UI
- `extras/octohue.md` — source of truth for the OctoPrint plugin registry entry; copy to `~/git/plugins.octoprint.org/_plugins/octohue.md` when updating

## Running tests

```bash
# Python (169 tests) — no live OctoPrint install required
python -m pytest

# JavaScript (68 tests)
npx jest
```

Both suites must pass before opening a PR. All new or changed behaviour requires tests.

## Branching and release workflow

**Never commit directly to `master`.** Always create a branch, open a PR, and merge via GitHub. Branch protection with `enforce_admins` is enabled.

**Branch naming:**
- `feature/description` — new features
- `fix/description` — bug fixes
- `chore/description` — housekeeping
- `release/x.y.z` — version bump + CHANGELOG only

**Three release channels:**

| Branch | Channel | Version format | Who receives it |
|--------|---------|----------------|-----------------|
| `master` | Stable | `1.1.0` | All users (default) |
| `rc` | Release Candidate | `1.1.0rc1` | Opt-in testers |
| `devel` | Development | `1.1.0.dev1` | Opt-in cutting-edge users |

**Release flow:**
1. New work → feature branch → PR → merge to `devel`
2. Pre-release → merge `devel` → `rc`, tag `x.y.zrc1`, mark GitHub release as pre-release
3. Stable release → merge `rc` → `master` via `release/x.y.z` branch, tag `x.y.z`, full GitHub release
4. After tagging master, fast-forward `rc` and `devel` to match: `git push origin master:rc master:devel --force`

## Settings migrations

When adding or changing a plugin setting:
1. Add the key and default to `get_settings_defaults()`
2. Increment `get_settings_version()` by one
3. Add a migration block in `on_settings_migrate()` using cascading `if current < N` blocks — **not** `elif` — so users upgrading across multiple versions receive all intermediate migrations

## Hue v2 API notes

- All requests use HTTPS verified against `octoprint_octohue/signify-root-ca.pem` (Signify root CA)
- The bridge uses its serial number as the TLS certificate CN, so hostname verification is disabled at the urllib3 pool manager level (`assert_hostname=False`) — this is intentional
- Device and group IDs are UUIDs (v2 format); the old integer IDs from v1 are no longer valid
- `lampisgroup` is set automatically by the JS frontend based on whether the selected dropdown item is a `light` or `group` type
- Brightness is stored as a percentage (0–100); the v2 API rejects values above 100.0

## Commit style

Include `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` in commit messages when Claude assisted with the change. Do not add attribution footers to PR descriptions or release notes.
