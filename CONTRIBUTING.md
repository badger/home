# Contributing to the GitHub Universe Badge

The repository targets the Universe 2026 badge. The Universe 2025 source is
preserved under `badge25/` for compatibility fixes.

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:
- A clear description of the problem
- Steps to reproduce the issue
- Expected vs. actual behavior
- Any relevant screenshots or error messages

### Contributing Code

We accept pull requests for:
- New badge apps
- Improvements to existing apps
- Bug fixes
- Documentation improvements
- Infrastructure improvements

## Adding New Apps

If you're contributing a new app, please follow these guidelines:

### 1. App Structure

Your app should follow the standard structure:

```
/badge/apps/your_app/
  __init__.py      # Main app code with update() function
  icon.png         # 24x24 PNG icon for the menu
  assets/          # Optional: images, data files, etc.
```

See the [README](./README.md#creating-a-2026-app),
[`badge/AGENTS.md`](./badge/AGENTS.md), and the
[hardware reference](./hardware/README.md) for current development guidance.

### 2. Test on a real badge

The simulator under `badge25/simulator/` models the Universe 2025 runtime and
is not a reliable validator for 2026 apps. Test on Universe 2026 hardware,
including both physical orientations and the capacitive controls.

For fast iteration before testing on hardware, use the
[Badge Simulator canvas](./.github/extensions/badge-simulator/README.md) in the
GitHub Copilot app. It runs your app on the badger.github.io 3D simulator,
reloads on every save, and its **Deploy** button installs the app on your badge.

Pimoroni also publishes a
[desktop Badgeware Simulator](https://github.com/pimoroni/badgeware-simulator)
and a
[web Badgeware Simulator](https://github.com/pimoroni/badgeware-web-simulator).
They are useful references for the upstream Tufty 2350 and Badgeware platform,
but may not reproduce the Universe 2026 derivative's onboard accelerometer,
IR transmitter/receiver, capacitive gaming controls, or custom firmware APIs.
See [`pimoroni/badgeware-docs`](https://github.com/pimoroni/badgeware-docs) for
upstream Badgeware documentation and examples.

### 3. Include a Screenshot

**All new apps must include a screenshot showing the app in action.**

Screenshots should:
- Be saved in PNG format at the app's selected logical resolution
- Show the app's main functionality or most interesting screen
- Be named descriptively (e.g., `your_app_screenshot.png`)
- Be included in your pull request description

### 4. Code Quality

- Follow the existing code style in the repository
- Add comments to explain complex logic
- Keep your code clean and readable
- Test edge cases (e.g., button mashing, rapid state changes)
- Use frame-rate-independent timing with `badge.ticks_delta`
- Use logical, orientation-aware input constants
- Manage memory carefully

### 5. Documentation

Include in your pull request:
- A brief description of what your app does
- How to use it (which buttons do what)
- Any special features or Easter eggs
- Screenshot(s) of the app in action

### 6. Assets and Resources

If your app includes images, sounds, or other assets:
- Place them in your app's `assets/` directory
- Use appropriate file formats (PNG for images)
- Optimize file sizes when possible (the badge has limited storage)
- Ensure you have the rights to use any third-party assets

## Agent Plugin and canvas

The repository root is the installable plugin; do not add a legacy
`.github/plugin/plugin.json` or Awesome Copilot's internal composition
namespace. Portable skills belong in `skills/`, with their scripts and
references. Copilot canvas code belongs in
`com.github.copilot/extensions/badge-simulator/`. Keep the `.github/` project
loaders thin so project and installed-plugin behavior cannot drift.
Only the Universe 2026 simulator is exposed.

Run these checks from the repository root (Node.js 24+ and Python 3.10+):

```sh
node --experimental-vm-modules --test tests/plugin.test.mjs
python -m unittest discover -s skills/hyb26-skill/tests -v
copilot --plugin-dir . plugin list
```

CI also runs Awesome Copilot's pinned `@microsoft/vally` skill checks via
`.github/scripts/lint_plugin.mjs`. This validator is a development-only tool;
the installed canvas has no npm dependencies to restore.

The Node tests exercise the actual extension with a mocked SDK connection,
including installation outside the app project, HTTP assets, app switching,
live reload, deployment requests, and lifecycle cleanup. Also open the
`badge-simulator` canvas in the Copilot app, run `check_app`, and exercise
`run_script`, `get_output`, `screenshot`, and `exec`. A real simulator screen
capture belongs at `assets/preview.png`; it is the marketplace logo, not a
placeholder.

### Awesome Copilot external-plugin submission

Follow [Awesome Copilot's external-plugin workflow](https://github.com/github/awesome-copilot/blob/main/CONTRIBUTING.md#adding-external-plugins).
Do **not** send a PR editing its `plugins/external.json`.

1. Publish these changes in the public `badger/home` repository. Choose a
   release tag and/or full 40-character commit SHA containing the plugin.
   Do not submit a mutable branch or a SHA predating these files.
2. Open its [external plugin submission form](https://github.com/github/awesome-copilot/issues/new?template=external-plugin.yml).
   Use `universe-2026-badge`, version `1.0.0` (or the current manifest version),
   repository `badger/home`, and plugin path `/` (repository root).
   Copy the description, author, license, and keywords from `plugin.json`.
   Include **canvas** in the keywords and the immutable revision from step 1.
3. Note that the canvas entry point is
   `com.github.copilot/extensions/badge-simulator/extension.mjs`, the logo is
   `assets/preview.png` via `extensions.com.github.copilot.logo`, and skills
   are discovered from `skills/`. No materialization step is needed.
4. Intake checks the manifest, skill lint, installation, version/revision
   consistency, and canvas structure. Resolve any requested fixes and update
   the submitted immutable revision before requesting another intake pass.
   Marketplace listing still requires maintainer approval.

## Code Review

All submissions require review before being merged. We'll check that:
- The code follows project conventions
- The app works correctly
- Documentation and screenshots are included (for new apps)
- The code doesn't introduce bugs or security issues
- The code doesn't obviously infringe on anyone elses IP (i.e. uses trademarks of known games in a way that could be confusing)

## License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project (see [LICENSE](./LICENSE)).

---

Thank you for helping make the GitHub Universe badge even better. Please share
your creations with `@github` and the `#GitHubUniverse` hashtag where possible.
