Your badge comes preloaded with the `image` example, which allows you to display images on your badge. This example is a great way to get started with the basics of loading and running apps on your badge.

This directory contains a few images to get you started.

Drop image files into the `/images` directory using Thonny to get them to show up in the image example.

A few quick tips:
1. Images should be 296x128 pixels or less.
2. File names must have an extension of `.jpg` or `.png`.
3. Images don't have to be greyscale, but they will be dithered to greyscale when displayed and color images may not look great.

From [the docs](https://learn.pimoroni.com/article/getting-started-with-badger-2040):
>Our jpeg decoder jpegdec will attempt to dither your image into a 1-bit colour palette - we've found images with a lot of contrast turn out best. If you want more control over what your image will look like, you could convert it into a 1-bit image yourself using image editing software. In GIMP, you can do this with 'Image > Mode > Indexed... > Use black and white (1-bit) palette'.
>
>Make sure you export your jpeg without progressive encoding. We've had good results from turning off jpeg optimization as well (in GIMP, you can find these settings under 'advanced options').