## Plan: Menu Subfolders Rollout

Add folder-aware discovery, icons, and navigation so the launcher can browse nested directories with a fixed back entry and alphabetical grouping while keeping the firmware testable after each incremental change.

**Steps 5:**
1. Refactor listing in [`__init__.py`](badge/apps/menu/__init__.py) to scan the active directory, tag each entry, and sort folders before apps alphabetically. Keep to MicroPython-friendly calls (`os.listdir`, `badgeware.is_dir`, `badgeware.file_exists`).
   ```python
   def scan_entries(root):
	   entries = []
	   try:
		   for name in os.listdir(root):
			   if name.startswith("."):
				   continue
			   full_path = "{}/{}".format(root, name)
			   if is_dir(full_path):
				   has_module = file_exists("{}/__init__.py".format(full_path))
				   kind = "app" if has_module else "folder"
				   entries.append({"name": name, "path": full_path, "kind": kind})
	   except OSError as exc:
		   print("scan_entries failed for {}: {}".format(root, exc))
	   folders = [item for item in entries if item["kind"] == "folder"]
	   apps = [item for item in entries if item["kind"] == "app"]
	   folders.sort(key=lambda item: item["name"])
	   apps.sort(key=lambda item: item["name"])
	   return folders + apps
   ```
2. Stage new assets `folder_icon.png` and `folder_up_icon.png` under [`menu`](badge/apps/menu/) without altering runtime behavior. Use 24x24 PNGs so the existing `Image.load` calls continue working on-device.
3. Map entry types to sprites in [`icon.py`](badge/apps/menu/icon.py) and adjust `load_page_icons` in [`__init__.py`](badge/apps/menu/__init__.py) to pin the back icon at slot 0 when depth > 0.
   ```python
   ICON_SPRITES = {
	   "app": "/system/apps/menu/default_icon.png",
	   "folder": "/system/apps/menu/folder_icon.png",
	   "back": "/system/apps/menu/folder_up_icon.png",
   }

   def sprite_for(entry):
	   path = ICON_SPRITES.get(entry["kind"], ICON_SPRITES["app"])
	   try:
		   return Image.load(path)
	   except OSError:
		   return Image.load(ICON_SPRITES["app"])
   ```
   In `load_page_icons`, insert a synthetic `{"kind": "back", "name": "..", "path": current_path}` entry at index 0 whenever the depth is greater than zero, then pad the grid as usual.
4. Extend navigation state in [`__init__.py`](badge/apps/menu/__init__.py) (path stack, selection offsets, `io.BUTTON_HOME` reset) so A enters folders, B launches apps, and HOME returns to root. Preserve pagination behavior and reuse the scanning helper for each stack change.
   ```python
   ROOT = "/system/apps"
   path_stack = []
   current_entries = scan_entries(ROOT)
   cursor_index = 0

   def enter_folder(entry):
	   global current_entries, cursor_index
	   path_stack.append(entry["path"])
	   current_entries = [{"name": "..", "path": entry["path"], "kind": "back"}]
	   current_entries.extend(scan_entries(entry["path"]))
	   cursor_index = 0

   def leave_folder():
	   global current_entries, cursor_index
	   if path_stack:
		   path_stack.pop()
	   active_path = ROOT if not path_stack else path_stack[-1]
	   current_entries = scan_entries(active_path)
	   cursor_index = 0

   def handle_input():
	   global cursor_index
	   if io.BUTTON_HOME in io.pressed:
		   while path_stack:
			   leave_folder()
		   return None
	   if io.BUTTON_A in io.pressed:
		   entry = current_entries[cursor_index]
		   if entry["kind"] == "folder":
			   enter_folder(entry)
		   elif entry["kind"] == "back":
			   leave_folder()
	   if io.BUTTON_B in io.pressed:
		   entry = current_entries[cursor_index]
		   if entry["kind"] == "app":
			   return entry["path"]
	   return None
   ```
5. Validate after each commit on hardware: first ensure the refactor keeps flat menu behavior, then verify folder/back icon rendering with pagination, and finally confirm full navigation (A-to-enter, B-to-launch, HOME-to-root) matches expectations.

**Open Questions 1:**
1. None.
