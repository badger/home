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
