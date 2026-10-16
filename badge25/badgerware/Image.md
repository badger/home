# `Image` - drawing surface and framebuffer

This class provides functions for loading images, drawing shapes and text, and blitting sprites.

Images can be either true colour (RGBA) or paletted (up to 256 colours).
Because available RAM is limited, it’s recommended to use paletted images whenever possible — they use roughly one quarter of the memory compared to true colour images.

> Note: Drawing operations cannot currently be performed on paletted images, though this limitation may be removed in a future update.

## Properties

`width` and `height`\
Return the width and the height of the image in pixels.

`has_palette`\
True if the image is palette based.

`antialias`\
The current antialiasing level for vector drawing operations.

Valid values are `Image.OFF`, `Image.X2`, and `Image.X4`.

`alpha`\
The alpha value of this image for blitting.

`brush`\
The current brush used for drawing operations.

`font`\
The current font for drawing text. Can either be a `PixelFont` or `VectorFont`.

> Note: currently vector fonts are experimental and perform badly

## Methods

`draw(shape)`\
Draws the supplied vector shape using the currently selected brush.

`window(x, y, w, h)`\
Returns a reference to a subsection of this image.

Any drawing operations performed on the window are restricted to the specified area, and the origin (0, 0) is relative to the window’s top-left corner, not the original image.

`clear()`\
Fills the image with the selected brush.

`text(message, x, y)`\
Writes text using the current font and brush to the image at location `x`, `y`.

`measure_text(message)`\
Returns a tuple with the width and height of the message provided in the current font.

`blit(source, x, y)`\
Blits the source image onto this image at location `x`, `y`.

`scale_blit(source, x, y, w, h)`\
Blits the source image onto this image at the position `x`, `y`, scaled to the specified width (`w`) and height (`h`).

If either dimension is negative, the image will be flipped horizontally and/or vertically in addition to being scaled.

## Static methods

`load(path)`\
Creates and returns a new `Image` object loaded from the specified file path.

> Note: currently only PNG format images are supported

## Constants

`Image.X4`\
`Image.X2`\
`Image.OFF`

Identifiers for each of the available antialiasing levels.