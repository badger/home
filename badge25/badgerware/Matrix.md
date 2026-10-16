# `Matrix` - transform drawing operations

This class provides functions for defining transformation matrices used when drawing vector primitives.

Matrices provide a unified way to handle transformations such as translation, rotation, scaling, and shearing. By combining these into a single matrix, you can apply complex transformations to vectors with a single operation.

Multiple transformations can also be chained together through matrix multiplication, making matrices both efficient and elegant tools for managing motion and geometry in 2D space.

```python
from badgeware import shapes, Matrix

circle = shapes.circle(0, 0, 1)
# chain operations to create a single transformation matrix that performs
# multiple modifications
circle.transform = Matrix().scale(10, 10).rotate(20).translate(10, 10)
```

## Methods

`Matrix()`\
Creates and returns a new identity matrix.

`translate(x, y)`\
Returns a new matrix representing the current matrix multiplied by a translation matrix for the specified translation.

`scale(x, y)`\
Returns a new matrix representing the current matrix multiplied by a scale matrix for the specified scale.

`rotate(angle)`\
`rotate_radians(angle)`\
Returns a new matrix representing the current matrix multiplied by a rotation matrix for the specified angle (in degrees or radians).

`multiply(matrix)`\
Returns a new matrix representing the current matrix multiplied by the supplied matrix.
