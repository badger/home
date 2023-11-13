# Let's get Hacking!

Hello 👋 - if you've landed at this repo it's probably because you are one of the lucky people at GitHub Universe 2023 who has been handed a hackable conference badge and you are now wondering what the heck this thing is and how you can get started.

<p align="center"><img src="https://github.com/badger2040/home/assets/856858/6ddd3d91-0e22-4a5c-9367-2bdfacd73127" alt="The GitHub Universe Badger" width="400px"/></p>

## What is it?
The GitHub Universe Badger is a hackable conference badge running Micropython on a RP2040 microprocessor and comes with a built in 2.9" E Ink® display (296 x 128 pixels) along with a battery connector, 5 user configurable buttons and a QT/Stemma expansion port for connecting additional sensors and accesories.  The GitHub Universe Badger is a custom version of the [Badger2040](https://learn.pimoroni.com/article/getting-started-with-badger-2040) made by our wonderful friends at [Pimoroni](https://pimoroni.com/). Electronically we kept it identical so that all the open source examples that you can find of cool things you can do with your Badger2040 you can do with your brand new GitHub Badger.  We just blinged up the PCB a bit and installed some little easter eggs into the [BadgerOS](https://github.com/pimoroni/badger2040) image hung around your neck.

## How do I get started
If you want to just play with the badge you have, you can plug it into power via the USB-C connection.  However you can also power the device with a battery pack as it is extremely low power.

You can power over USB or via the JST power connector that can accept a 2xAAA battery pack ot standard 3.7v LiPo cell.

Once you have power, if you press and hold the A & C buttons simultaneously, you get into the secret menu of the badger operating system.  From there you can explore the installed applications including an eBook reader, ToDo list and image viewer.

## Yeah, yeah cool - how do I hack this thing?
Check out the [Badger tutorial](https://learn.pimoroni.com/article/getting-started-with-badger-2040) from Pimoroni to learn more about connecting to your Badger and running your own Micropython code on it.  But remember you are not limited to Micropython.  This is a full Raspberry Pi Pico device so if you wanted to entirely flash your firmware and turn your badger into a USB Macro Keyboard or make it play doom then all that and more is possible.  We've deliberately left solderable exansion pins available on your badge as well as a serial QT/Stemma port so you can connect your badge to a whole ecosystem of sensors from the likes of [Adafruit](https://www.adafruit.com/) and [Pimoroni](https://pimoroni.com/).  To learn more about Stemma see this [excellent tutorial from Adafruit](https://learn.adafruit.com/introducing-adafruit-stemma-qt/what-is-stemma).

## How can I create my own custom event badge
As well as the [Badger2040](https://learn.pimoroni.com/article/getting-started-with-badger-2040), there is a thriving community of badge hackers at open source and security events.  Be sure to check out [Badge.team](https://badge.team/) if you are thinking about creating your own.

