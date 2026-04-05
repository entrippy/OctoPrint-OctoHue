# Contributing to OctoHue

Thanks for your interest in contributing. This document covers how to report bugs, suggest features, and submit code changes.

## Reporting bugs

Use the [bug report template](ISSUE_TEMPLATE/bug_report.md) and include:

- OctoPrint and OctoHue versions
- Python version (`python3 --version` on your Pi)
- The relevant section of `octoprint.log` — look for lines tagged `octoprint.plugins.octohue`
- Steps to reproduce

## Suggesting features

Use the [feature request template](ISSUE_TEMPLATE/feature_request.md). Please check open issues first to avoid duplicates.

## Submitting a pull request

### Setup

```bash
git clone https://github.com/entrippy/OctoPrint-OctoHue.git
cd OctoPrint-OctoHue
pip install -e ".[develop]"   # installs the plugin in editable mode
npm install                   # installs Jest for JS tests
```

### Making changes

- **Python plugin logic** lives in `octoprint_octohue/__init__.py`
- **Frontend viewmodel** lives in `octoprint_octohue/static/js/OctoHue.js`
- **Settings UI** lives in `octoprint_octohue/templates/octohue_settings.jinja2`

Keep changes focused — one fix or feature per pull request.

### Tests are required

All pull requests must include passing tests that cover the new or changed behaviour. PRs without tests will not be merged.

```bash
# Python (run from the repo root)
python -m pytest

# JavaScript
npx jest
```

Both suites must pass. If you are fixing a bug, add a test that fails before your fix and passes after. If you are adding a feature, add tests covering the expected behaviour and any edge cases.

### Settings migrations

If your change adds or modifies a plugin setting, you must:

1. Add the new key and its default to `get_settings_defaults()`
2. Increment `get_settings_version()` by one
3. Add a migration block in `on_settings_migrate()` using the cascading `if current < N` pattern (not `elif`) so users upgrading across multiple versions are migrated correctly

### Opening the PR

- Target the `master` branch
- Describe what the change does and why
- Reference any related issue with `Closes #NNN`

## Hue API notes

OctoHue uses the **Hue v2 CLIP API** over HTTPS. All requests are verified against the bundled Signify root CA (`octoprint_octohue/signify-root-ca.pem`). The bridge uses its serial number as the TLS certificate CN, so hostname verification is disabled at the urllib3 pool manager level (`assert_hostname=False`) — this is intentional.

Device IDs are UUIDs (v2 format). The `lampisgroup` setting is set automatically by the frontend based on whether the selected item is a `light` or `group` type — it does not need to be set manually.

## Licence

By contributing you agree your changes will be released under the project's [AGPLv3 licence](../LICENSE).
