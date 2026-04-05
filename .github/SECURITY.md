# Security Policy

## Supported versions

Only the latest release on `master` is actively maintained. Security fixes will not be backported to older versions.

| Version | Supported |
|---------|-----------|
| 1.x (latest) | Yes |
| < 1.0 | No |

## Reporting a vulnerability

Please **do not** report security vulnerabilities via public GitHub issues.

Use GitHub's private vulnerability reporting feature instead — this keeps the details confidential until a fix is released:

**[Report a vulnerability](https://github.com/entrippy/OctoPrint-OctoHue/security/advisories/new)**

You can expect an acknowledgement within a few days. If a fix is warranted, a patched release will be published and you will be credited in the release notes unless you prefer otherwise.

## Scope

This plugin runs locally on your network and communicates only with your Philips Hue bridge. It does not transmit data to any external service. Relevant security concerns include:

- The SimpleAPI endpoints (`turnon`, `turnoff`, `togglehue`, `cooldown`) are intentionally unauthenticated to allow use from external scripts — this is by design and documented
- Sensitive commands (`bridge`, `getdevices`, `getgroups`, `getstate`) require OctoPrint admin access
- TLS connections to the Hue bridge are verified against the bundled Signify root CA certificate
