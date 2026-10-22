## What does this PR do?

<!-- Explain why this change is needed and summarize the approach. Link any related issue (for example, "Fixes #123"). -->

## Type of change

- [ ] New badge app
- [ ] Improvement or bug fix to an existing app
- [ ] Firmware, menu, or system change
- [ ] Documentation
- [ ] Infrastructure (workflows, scripts, tooling)
- [ ] Universe 2025 (`badge25/`) maintenance

## Badge app checklist

<!-- Complete this section for new or changed apps under badge/apps/. Delete it otherwise. -->

- [ ] The app lives in `badge/apps/<name>/` with `__init__.py` and a 24x24 `icon.png`
- [ ] `README.md` starts with a one-sentence description, followed by usage and any hardware or network requirements
- [ ] Uses the 2026 runtime globals (`badge`, `screen`, `image`, ...) and logical buttons such as `BUTTON_SELECT`
- [ ] Movement and animation are frame-rate independent (`badge.ticks_delta`)
- [ ] Tested on Universe 2026 badge hardware, including both orientations and the capacitive controls
- [ ] Assets are in `assets/`, are PNG where possible, and are as small as practical
- [ ] No secrets, tokens, or personal data are committed (`badge/secrets.py` stays empty)

### Screenshots

<!-- Required for new apps. Add at least one screenshot of the app running at its logical resolution. -->

### How to use it

<!-- Which buttons do what? Any special features or Easter eggs? -->

## Licensing and intellectual property

This is an open source repository released under the [MIT License](https://github.com/badger/home/blob/main/LICENSE). Everything merged here is distributed under the terms of that license.

We can't accept contributions that use someone else's intellectual property (for example, characters, artwork, logos, trademarks, game names, music, fonts, or code) unless that person or company has agreed to its release under the project license. This includes recognizable likenesses of existing games or brands that could be confusing.

- [ ] I created all code and assets in this PR, or they are already available under an MIT-compatible license and I have credited them in the app README
- [ ] This PR doesn't include third-party characters, logos, trademarks, or other IP, or the owner has agreed to its release under the MIT License
- [ ] I agree that my contribution is licensed under this project's MIT License

## Additional notes

<!-- Anything reviewers should pay special attention to, trade-offs, or follow-up work. -->
