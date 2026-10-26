# The Creative 8-Ball: a d20 (icosahedron) for Taste Stamp.
#
# Pure maths with no badge APIs, so the tests can drive it. World space has
# x right, y up and z towards the viewer.

import math

PHI = (1.0 + math.sqrt(5.0)) * 0.5


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    d = math.sqrt(_dot(a, a))
    return (a[0] / d, a[1] / d, a[2] / d)


def icosahedron():
    # Returns (vertices, faces, numbers). Each face is (top, left, right):
    # counter-clockwise seen from outside, with the number's top pointing at
    # the first vertex. numbers[i] is face i's number; opposite faces add up
    # to 21 like a real d20.
    verts = []
    for a in (-1.0, 1.0):
        for b in (-PHI, PHI):
            verts.append((0.0, a, b))
            verts.append((a, b, 0.0))
            verts.append((b, 0.0, a))
    n = len(verts)

    def close(i, j):
        d = _sub(verts[i], verts[j])
        return abs(_dot(d, d) - 4.0) < 0.01

    faces = []
    for i in range(n):
        for j in range(i + 1, n):
            if not close(i, j):
                continue
            for k in range(j + 1, n):
                if close(i, k) and close(j, k):
                    a = verts[i]
                    normal = _cross(_sub(verts[j], a), _sub(verts[k], a))
                    centre = (a[0] + verts[j][0] + verts[k][0], a[1] + verts[j][1] + verts[k][1], a[2] + verts[j][2] + verts[k][2])
                    if _dot(normal, centre) > 0:
                        faces.append((i, j, k))
                    else:
                        faces.append((i, k, j))

    numbers = [0] * len(faces)
    low = 1
    for f in range(len(faces)):
        if numbers[f]:
            continue
        c = face_centre(verts, faces[f])
        for g in range(len(faces)):
            o = face_centre(verts, faces[g])
            if abs(o[0] + c[0]) + abs(o[1] + c[1]) + abs(o[2] + c[2]) < 0.01:
                numbers[f] = low
                numbers[g] = 21 - low
                low += 1
                break
    return verts, faces, numbers


def face_centre(verts, face):
    a = verts[face[0]]
    b = verts[face[1]]
    c = verts[face[2]]
    return ((a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0, (a[2] + b[2] + c[2]) / 3.0)


def face_normal(verts, face):
    a = verts[face[0]]
    return _unit(_cross(_sub(verts[face[1]], a), _sub(verts[face[2]], a)))
