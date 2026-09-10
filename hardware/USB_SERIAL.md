# USB serial and MicroPython REPL

The Universe 2026 badge presents a USB CDC serial interface when connected to
a computer. That interface provides the onboard MicroPython REPL and can also
be used to inspect, copy, and remove files.

This workflow was tested on a physical badge on 8 September 2026 using
`mpremote`.

## Tested device identity

On macOS, `mpremote devs` reported:

```text
/dev/cu.usbmodem2101 5db304b0e9a89057 2e8a:1101 Pimoroni Pimoroni Tufty 2350 MicroPython
```

The serial path is assigned by the host and may change after reconnecting.
Select the entry with USB vendor/product ID `2e8a:1101` and product name
`Pimoroni Tufty 2350 MicroPython`, not a Bluetooth or debug-console port.

Typical port names are:

| Platform | Example |
| --- | --- |
| macOS | `/dev/cu.usbmodem2101` |
| Linux | `/dev/ttyACM0` |
| Windows | `COM4` |

On macOS, prefer `/dev/cu.usbmodem*` for initiating a connection. Discover the
current path each time:

```bash
mpremote devs
```

Set a shell variable to make subsequent commands easier:

```bash
PORT=/dev/cu.usbmodem2101
```

## Tooling

Install the official MicroPython command-line tool if it is not already
available:

```bash
python3 -m pip install mpremote
```

Use a virtual environment when the system Python environment does not permit
package installation.

The serial line operates at 115200 baud. `mpremote` handles the REPL control
sequences and raw-REPL protocol automatically, so it is safer for scripted
file transfer than manually typing commands into a terminal.

Only one process can own the serial port. Do not run `mpremote`, `screen`, a
Web Serial page, Thonny, or another serial client concurrently. A second
client fails with a message such as:

```text
failed to access /dev/cu.usbmodem2101 (it may be in use by another program)
```

## Interactive REPL

Open the friendly MicroPython REPL:

```bash
mpremote connect "$PORT" repl
```

Press `Ctrl-]` to exit `mpremote`'s REPL session.

Connecting to the REPL or running an `mpremote` command can interrupt the app
currently running on the badge. `mpremote` normally performs a soft reset when
it first enters raw REPL for a command. Expect the menu or app to stop while
developing. Reboot after file operations when you want to exercise the normal
startup path:

```bash
mpremote connect "$PORT" reset
```

Use `resume` only when deliberately attaching without `mpremote`'s initial
soft reset:

```bash
mpremote connect "$PORT" resume repl
```

## Runtime observed on the tested badge

The following command queries the runtime without requiring an interactive
session:

```bash
mpremote connect "$PORT" exec \
  "import sys, os; print(sys.implementation); print(os.uname())"
```

The tested badge reported:

```text
MicroPython 1.29.0-preview
build: tufty
machine: Pimoroni Tufty 2350 with RP2350
RP2 firmware build date: 2026-09-08
```

Firmware versions and build dates will change, so query the connected badge
instead of assuming these exact values.

`mpremote eval` accepts an expression. Use `mpremote exec` for imports,
assignments, semicolon-separated statements, or multi-line code.

## Filesystem layout

List the filesystem root:

```bash
mpremote connect "$PORT" fs ls :
```

The tested badge root contained:

```text
rom/
system/
state/
.fsbackup
.fsbackup.crc32
text.txt
```

The important locations are:

| Device path | Purpose |
| --- | --- |
| `/system` | Firmware files, shared assets, `main.py`, and apps; read-only in the normal REPL runtime on the tested firmware |
| `/system/apps` | Installed application directories and packaged app archives |
| `/state` | Persistent application state managed by the firmware |
| `/rom` | Firmware-provided/frozen resources; treat as read-only |
| `/` | Small writable data filesystem that also contains `/state` |

Useful inspection commands:

```bash
mpremote connect "$PORT" fs ls :/system
mpremote connect "$PORT" fs ls :/system/apps
mpremote connect "$PORT" fs ls :/state
mpremote connect "$PORT" fs cat :/system/secrets.py
```

`mpremote fs ls` expects a directory on this firmware. To inspect a single
file's metadata, use `os.stat()`:

```bash
mpremote connect "$PORT" eval "os.stat('/text.txt')"
```

`os` is commonly available in the raw REPL environment, but use `exec` with an
explicit import if needed:

```bash
mpremote connect "$PORT" exec "import os; print(os.stat('/text.txt'))"
```

### Observed storage

The values below came from `os.statvfs()` on one badge and are approximate:

| Path | Block size | Total | Free during test | Notes |
| --- | ---: | ---: | ---: | --- |
| `/` and `/state` | 4096 bytes | 1 MiB | about 980 KiB | Writable state/data partition |
| `/system` | 4096 bytes | about 12 MiB | about 10.1 MiB reported | Read-only in the normal runtime despite the reported free-block count |
| `/rom` | Firmware-defined | N/A | 0 | Frozen/read-only resources |

Check free space before copying large assets:

```bash
mpremote connect "$PORT" exec \
  "import os; print(os.statvfs('/')); print(os.statvfs('/system'))"
```

## Copying files

Remote paths are prefixed with `:` in `mpremote` filesystem commands.

Copy a local file to the badge:

```bash
mpremote connect "$PORT" fs cp local-file.txt :/text.txt
```

Read it back:

```bash
mpremote connect "$PORT" fs cat :/text.txt
```

Copy a file from the badge to the current directory:

```bash
mpremote connect "$PORT" fs cp :/text.txt ./text-from-badge.txt
```

Create and remove directories or files on the writable root/state filesystem:

```bash
mpremote connect "$PORT" fs mkdir :/apps
mpremote connect "$PORT" fs rm :/text.txt
mpremote connect "$PORT" fs rmdir :/empty-directory
```

The live transfer test copied an 83-byte `/text.txt` file containing:

```text
GitHub Universe 2026 badge serial copy test
Written with mpremote over USB serial.
```

It was read back successfully with `mpremote fs cat`. The file was intentionally
left on the tested badge as a marker that the workflow completed.

## Installing an app

The tested 2026 firmware mounts `/system` read-only during normal execution.
Direct serial writes such as the following fail with `OSError: 30` (`EROFS`):

```bash
mpremote connect "$PORT" fs cp local.py :/system/apps/my_app/local.py
```

Use the badge's USB mass-storage mode for a persistent deployment:

1. Double-tap the badge reset control, or launch the built-in **Mass Storage**
   app on firmware whose startup script handles `WAKE_DOUBLETAP`.
2. Wait for the badge filesystem to appear as a USB volume.
3. Copy the complete app directory into `system/apps/` on that volume.
4. Replace `system/main.py` only when changing startup behavior.
5. Eject the volume cleanly and reset the badge.

On macOS, for example:

```bash
BADGE_VOLUME="/Volumes/<badge-volume-name>"
cp -R badge/apps/my_app "$BADGE_VOLUME/system/apps/"
diskutil eject "$BADGE_VOLUME"
```

After the badge returns to serial mode, verify the remote directory:

```bash
mpremote connect "$PORT" fs ls :/system/apps/my_app
```

Avoid overwriting `/system/main.py`, the menu, shared assets, or other system
files unless that is the explicit purpose of the change.

## Running code without installing it

Execute a local script on the badge:

```bash
mpremote connect "$PORT" run path/to/probe.py
```

Execute a short snippet:

```bash
mpremote connect "$PORT" exec "import os; print(os.listdir('/system/apps'))"
```

For repeated development, `mpremote mount badge` exposes the local `badge/`
tree at `/remote`. Apps that support `/remote/apps/<name>` can then be
render-tested without copying. Mounted-host behavior differs from the real
onboard filesystem, and this `mpremote` version cannot stream PNG data through
the mount reliably, so copy asset-heavy apps to writable scratch space for
their transient test or perform the final test from USB mass storage.

## Manual/Web Serial transfers

The `martinwoodward/bodger` example opens a Web Serial connection at 115200
baud and writes files through normal MicroPython REPL statements:

```python
f = open("badge.png", "wb")
f.write(b"...")
f.close()
```

Binary data is represented as escaped byte literals and sent in 256-byte
chunks with a delay between chunks to avoid overrunning the serial buffer.
This works for browser-based tooling, but production scripts should prefer
raw REPL or `mpremote`, which provides command framing, response handling, and
filesystem copy operations.

Never send arbitrary binary bytes directly to the friendly REPL: control
characters and line editing can corrupt the transfer. Encode data as Python
byte literals, use raw REPL, or use `mpremote fs cp`.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| No USB modem entry | Try a data-capable USB cable, reconnect, and run `mpremote devs` |
| Port is in use | Close Thonny, `screen`, Web Serial browser tabs, and other `mpremote` processes |
| Command hangs or app keeps drawing | Press `Ctrl-C` in an interactive REPL or reconnect with `mpremote` |
| App does not appear in menu | Confirm `/system/apps/<name>/__init__.py` exists, then reset |
| Import or asset failure | Verify every module and asset path in the remote app directory |
| Copy fails for lack of space | Check `os.statvfs('/system')` and remove obsolete files deliberately |
| Serial path changed | Run `mpremote devs` again; do not hard-code a machine-specific suffix |

Do not use name-based process-killing commands to release the port. Identify
the specific owning process and close it normally or terminate that PID.
