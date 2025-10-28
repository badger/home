# Loading Apps onto Your Universe Badge

Welcome to the GitHub Universe badge tutorial, using the Badger 2040 (or 2350) by [Pimoroni](https://pimoroni.com). This will walk you through the process of loading a simple app onto your badge. Once you've completed this tutorial, you'll know how to install other apps (available in the [examples](/examples) folder), and be ready to learn how to create your own Badger programs as well!

## Using the Thonny IDE for Badger programming

Thonny is a Integrated Development Environment (IDE), a tool that helps you write and run code. While you could use any Python-capable IDE to edit your code, Thonny is especially useful in this context since it also has the ability to communicate directly with your Badger 2040, reading and writing files on the device (and even triggering programs to run directly on the badge hardware).

### Installing Thonny

1. Open your web browser and go to [thonny.org](https://thonny.org). Click the appropriate download button for Windows, Mac, or Linux.
2. Open the downloaded file and follow the on-screen instructions. If you're not sure about an option, it's okay to use the default settings.

## Connecting to your Badge

1. Connect your Badger 2040 badge to your computer via a USB cable.
2. Your computer might make a sound or show a message when it recognizes the Badger 2040. If prompted with a dialog, allow the device to be used with your computer.
3. Open Thonny by double-clicking its icon on your desktop or finding it in your computer's program list.
4. At the bottom of the Thonny window, you'll see a bar that probably says "Local Python 3" with a version number.
5. Click on that bar and choose "MicroPython (Raspberry Pi Pico)" from the list that appears.
6. If you don't see that option, click "Configure interpreter..." at the bottom of the list, then choose "MicroPython (Raspberry Pi Pico)" and click OK.

## Loading a Program

Now that you have Thonny installed and your Badger 2040 connected, let's walk through the process of loading a program onto your badge. While you could write one from scratch (see the [feature and function reference](/2040reference.md) later), this can be a complex and error-prone process, so we'll begin by loading some prebuilt programs (which we'll call "apps") onto the device.

### Each of these apps has two parts:

- A MicroPython file (e.g. `hello.py`)
    - MicroPython is a trimmed-down version of Python 3 which works well on devices
    - it is mostly equivalent to Python 3.4, but there are [a few other differences](https://docs.micropython.org/en/latest/genrst/index.html)
- An image file which will be the app's icon (e.g. `icon-hello.jpg`)
    - the name must be with "icon-" followed by the name of your Python file (no `.py`)
    - icons must be JPEG format and end in `.jpg` (not `.jpeg`), and Universe 2024 badges also support PNG (`.png`) with no alpha-channel transparency
    - 1-bit (black-and-white), undithered, high-contrast images work best
    - they should be exactly 52 pixels high and 52 pixels wide

### To load apps, we use Thonny to copy these files onto the device:

1. Make sure you have a copy of this repository on your local computer (clone or download this repo).
2. In Thonny, find "View" menu and select "Files".
1. You should see two new windows appear on the left: "This computer" and "Raspberry Pi Pico".
   - If the "Raspberry Pi Pico" window is missing, check that "MicroPython (Raspberry Pi Pico) - Board in FS mode" is selected in the lower-right corner of Thonny. You can also try clicking "the Stop/Restart backend" (the stop sign icon), or pressing the "reset" button on the back of the badge (wait 15s after each of these... the board needs some time to think!), or using a different cable.
3. In the "Raspberry Pi Pico" window of Thonny, click into the "examples" folder.
   - You should see about a dozen Python and image files (such as `badge.py` and `icon-badge.jpg`).
4. In the "This computer" window, navigate to this repo. Then descend into the "examples" folder, and the "hello" folder under that.
   - You should see two files, `hello.py` and `icon-hello.jpg`.
   - Hold down Shift and select both files, then right-click and select "Upload to /examples".
   - Click through the dialogs and wait for the files to copy.

### How to Run Your New App

Now that the files are on your badge, you can use your new app, even if you disconnect from your computer. However, the badge needs a power source for its buttons and screen activity to work. You can connect the USB-C port to a standard power bank or wall plug, or use the two-pin power port on the back of the badge to attach a [battery holder](https://shop.pimoroni.com/products/battery-holder-2-x-aaa-with-switch) or [LiPo](https://shop.pimoroni.com/products/lipo-battery-pack).

1. Press the **A** and **C** buttons simultaneously to get to the list of all apps (these are ordered alphabetically).
    - be patient... it can take a few seconds to respond the first time!
2. Use the up `^` and down `ˇ` buttons to navigate through the list.
3. When you see your app (in this example, a globe icon with "hello" beneath it), press the corresponding column button (**A**, **B**, or **C**) to run it.
4. When you are done, click **A** and **C** simultaneously to return to the list of all apps.

See [examples/README.md](examples/README.md) to learn how to use each app, and find out who made them!

> [!NOTE]
> It's safe to disconnect the badge from power anytime it isn't actively being programmed or transferring files; the e-paper screen will simply freeze in place. For some apps, like ones that simply display static text or a still image, that makes sense. But for interactive apps, it needs power.
> 
> Even if you're not actively programming your badge, the cable connecting it to your computer will supply power. But we've found that sometimes the badge can freeze when it is connected this way, so we like to move it to a "dumb" power source like a battery pack when we are testing the badge.

## Debugging Tips

### App icons don't appear correctly

If you cannot scroll to the row which contains your app, there may be a problem with your app icon.

- Ensure that it is exactly 52x52 pixels and is black-and-white.
- Check that the filename ends in ".jpg" (not ".jpeg"), or ".png" if you have a Universe 2024 badge.
- Check that the filename starts with "icon-" followed by the exact (case-sensitive) name of your Python file before the dot.
- If you are building your own icons, and have [ImageMagick](https://imagemagick.org/script/download.php) available, this one-liner will trim and convert an input image to black-and-white at 52x52px with a 2px white border:

```bash
magick convert -trim -density 1200 -resize 48x48^ -bordercolor white -border 2 -gravity center -extent 52x52 -monochrome input.svg output.jpg
```

### App doesn't load correctly after selecting button

- Unplug from your computer, wait 15-30 seconds, and plug into a "dumb" power source (e.g., USB power plug or battery), then press "reset" on the back twice (waiting 15 seconds between each press).
- If it is still not working, plug the board back into your computer and press reset on the board, then try launching your app manually (see the Appendix below).

## Keep Playing

Now that you've loaded your first app, reconnect the badge to your computer and load some more! Each subfolder of this repository's [examples](examples) folder has a different app. Simply copy all the files from that subfolder directly into the "examples" directory on your badge. For example, open [examples/copilot](examples/copilot) here, and copy **copilot-book.txt**, **copilot.py**, and **icon-copilot.jpg** right into the **examples** folder of your badge. Now you have a GitHub Copilot cheat sheet available anytime you need it!

![Copying files in Thonny IDE](tutorial_load_files.png)

When you tire of prebuilt examples, try building a program of your own. Find an example you can modify, or read the [feature and function reference](/2040reference.md) to dig deeper. 

If you build something fun, consider open-sourcing your code so other attendees can try it out.

Thanks again for being part of GitHub Universe 2024. We can't wait to see what you build!

## Appendix: manually running files

In addition to loading files onto your board, Thonny can directly load a program into your badge's memory and start it running. To do so:

1. Get to a state where you can see the files (see "Loading a Program" above).
2. Double-click your MicroPython file to get it open in the main editor window.
    - You can open either a `.py` file from "This computer", or one in the "Raspberry Pi Pico" window, by double-clicking it. The file will show up in an editor window on the right; note that files opened from the badge filesystem have square brackets in the editor tab title (e.g. `[hello.py]`), while local files do not.
    - Press the green "Run" button in Thonny to start the program; it will run on the board hardware, but send console output back to Thonny.
    - If the program produces an error, you will see it in the "Shell" window in Thonny. Click on any line of the traceback to see where your program broke.
    - Once you are done, click the "Stop/restart backend" button to stop debugging on the board.
    - If you made changes, be sure to copy your edited file to the correct destination before unplugging.
