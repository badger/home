# Contributing to Universe 2025 Badge

Thank you for your interest in contributing to the Universe 2025 Badge project! We love seeing what creative apps and improvements the community comes up with.

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

See the [README.md](./README.md#creating-your-own-apps) for detailed app development guidelines.

### 2. Test with the Simulator & with a real badge

Before submitting your app, **test it thoroughly using the badge simulator**:

```bash
python simulator/badge_simulator.py badge/apps/your_app
```

The simulator helps you:
- Catch bugs quickly without needing hardware
- Test your app's behavior and performance
- Verify button controls work correctly
- Ensure graphics render properly

After testing in the simulator, **also test your app on a real badge** to ensure it works as expected in the actual hardware environment.

### 3. Include a Screenshot

**All new apps must include a screenshot showing the app in action.**

To capture a screenshot:

```bash
# Run your app with screenshot directory specified
python simulator/badge_simulator.py -C badge --screenshots ./screenshots badge/apps/your_app/__init__.py

# Press F12 while the app is running to save a screenshot
```

Screenshots should:
- Be saved in PNG format at native resolution (160×120 pixels)
- Show the app's main functionality or most interesting screen
- Be named descriptively (e.g., `your_app_screenshot.png`)
- Be included in your pull request description

### 4. Code Quality

- Follow the existing code style in the repository
- Add comments to explain complex logic
- Keep your code clean and readable
- Test edge cases (e.g., button mashing, rapid state changes)
- Manage memory carefully (the badge has limited RAM)

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

Thank you for helping make the Universe 2025 Badge even better! We can't wait to see what you create! Please do share your creations on social and tag in `@github` with the hashtag `#GitHubUniverse` where possible.
