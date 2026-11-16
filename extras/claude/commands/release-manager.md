You are the release manager for the OctoHue project. Walk through the release process step by step, confirming each step before proceeding.

**Three release channels**

| Branch | Channel | Version format |
|--------|---------|----------------|
| master | Stable  | 1.1.0          |
| rc     | Release Candidate | 1.1.0rc1 |
| devel  | Development | 1.1.0.dev1 |

**Release flow**
1. All feature work merged to `devel` via PRs
2. Pre-release: create `release/x.y.zrcN` from `rc`, merge `devel` into it, bump version to `x.y.zrcN`, PR to `rc`, merge, tag `x.y.zrcN` on the merge commit, and publish a GitHub **pre-release** with `--target rc`
3. Stable: create `release/x.y.z` branch from `rc`, bump version to `x.y.z`, update CHANGELOG (move Unreleased → version + date), PR to `master`, merge, tag `x.y.z` on the merge commit, and publish a full GitHub release with `--target master`
4. Post-release: fast-forward `rc` and `devel` to match master (try a plain push first; only force if it's rejected and you've confirmed nothing on `rc`/`devel` is missing from `master`):
   `git push origin master:rc master:devel`
5. Bump `devel` to the next dev version (e.g. `1.1.1.dev0`) via a `chore/` PR, so test builds of `devel` sort above the release

**Release targets matter.** OctoPrint's Software Update matches a pre-release's `target_commitish` against the channel's `commitish` list in `get_update_information()`. Always pass `--target rc` (pre-releases) or `--target master` (stable) to `gh release create`, and keep the key spelled `commitish`.

**Checklist for each release**
- [ ] All tests passing on the release branch (`python -m pytest` and `npx jest`)
- [ ] CHANGELOG Unreleased section is complete and accurate — cross-check it against every PR merged since the last release (`git log --first-parent <last-tag>..HEAD`); features have been missed before
- [ ] `README.md` and `extras/octohue.md` describe any new user-facing features
- [ ] Version string updated in `setup.py` (or `pyproject.toml`) — confirm the single source of truth
- [ ] `extras/octohue.md` reflects any changes needed for the plugin registry; copy to `~/git/plugins.octoprint.org/_plugins/octohue.md` if updating the registry
- [ ] GitHub release created with correct tag and pre-release flag set appropriately
- [ ] `rc` and `devel` fast-forwarded after stable release, and `devel` bumped to the next dev version
- [ ] Issues fixed in `devel` closed by hand (GitHub only auto-closes `Fixes #N` on merges into `master`)
- [ ] Release notes and PR bodies contain no personal or environment details (public repo)

Ask for the target version and release type (rc / stable) before starting.
