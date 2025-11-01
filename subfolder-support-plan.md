## Plan: Menu Subfolders Rollout

Add folder-aware discovery, icons, and navigation so the launcher can browse nested directories with a fixed back entry and alphabetical grouping while keeping the firmware testable after each incremental change.

**Steps 5:**
1. Refactor listing in [`__init__.py`](badge/apps/menu/__init__.py) to scan current path, tag entries, and sort apps then folders alphabetically.
2. Stage new assets `folder_icon.png` and `folder_up_icon.png` under [`menu`](badge/apps/menu/) without altering runtime behavior.
3. Map entry types to sprites in [`icon.py`](badge/apps/menu/icon.py) and adjust `load_page_icons` in [`__init__.py`](badge/apps/menu/__init__.py) to pin the back icon at slot 0 when depth > 0.
4. Extend navigation state in [`__init__.py`](badge/apps/menu/__init__.py) (path stack, selection offsets, `io.BUTTON_HOME` reset) so A enters folders, B launches apps, and HOME returns to root.
5. Validate after each commit on hardware: post-refactor flat menu, folder/back icon rendering, then full navigation with HOME-to-root.

**Open Questions 1:**
1. None.
