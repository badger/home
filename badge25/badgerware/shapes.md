# `shapes` - create and manipulate shapes

This module provides ways to create primitive shapes and manipulate them.

> note: in future there will be a way to define custom shapes

## Properties

`transform`\
Matrix transformation that will be applied to this shape when drawing.

```python
shape = shapes.rectangle(-10, -10, 20, 20)
shape.transform = Matrix().rotate(20)
```

## Methods

`stroke(w)`\
Strokes an existing shape to create a new shape that defines it's outline with width `w`. All of the shape primitive methods return solid (filled) shapes, you can turn them into outlines using this method.

```python
stroked_circle = shapes.circle(80, 60, 30).stroke(5)
```

## Primitives
A collection of static methods create and return new primitives.

`shapes.circle(x, y, r)`\
Circle centered at `x`, `y` with radius of `r`.

`shapes.rectangle(x, y, w, h)`\
Draws a rectangle with its top-left corner at `x`, `y`, a width of `w`, and a height of `h`.

`shapes.rounded_rectangle(x, y, w, h, r)`\
`shapes.rounded_rectangle(x, y, w, h, r1, r2, r3, r4)`\
Draws a rectangle with its top-left corner at (x, y), a width of w, and a height of h.

If a single radius `r` is provided, all corners use the same rounding.

If multiple radii are specified, `r1` applies to the top-left corner, and the remaining radii (`r2`, `r3`, `r4`) apply clockwise around the rectangle.

`shapes.line(x1, y1, x2, y2, t)`\
Defines a line from `x1`, `y1` to `x2`, `y2` with thickness `t`.

`shapes.regular_polygon(x, y, r, s)`\
Defines a regular polygon centered at `x`, `y` with a radius of `r` and `s` sides.

`shapes.squircle(x, y, r, n=4)`
Define a squircle (square-circle) of radius `r` centred at `x`, `y`.

Optionally you can supply the `n` parameter which defines how rounded the resulting shape is, `4` is the default.

`shapes.arc(x, y, r, f, t)`\
Defines an arc with a radius of `r`, centered at `x`, `y`.

The parameters `f` and `t` specify the start (“from”) and end (“to”) angles of the arc, in degrees.

Angles are measured with 0° pointing straight down, increasing clockwise.

`shapes.pie(x, y, r, f, t)`\
Works identically to `arc` but creates a pie (pacman) shape instead.
