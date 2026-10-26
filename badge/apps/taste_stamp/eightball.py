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


def face_edges(faces):
    # Every edge once, as (i, j, face, other face), so the renderer can
    # outline the visible faces without drawing a shared edge twice.
    edges = []
    for f in range(len(faces)):
        face = faces[f]
        for e in range(3):
            i = face[e]
            j = face[(e + 1) % 3]
            if i > j:
                continue
            for g in range(len(faces)):
                other = faces[g]
                if g != f and i in other and j in other:
                    edges.append((i, j, f, g))
                    break
    return edges


# Quaternions are (w, x, y, z) and map body space to world space.

def q_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def q_normalise(q):
    d = math.sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3])
    return (q[0] / d, q[1] / d, q[2] / d, q[3] / d)


def q_axis_angle(axis, angle):
    s = math.sin(angle * 0.5)
    return (math.cos(angle * 0.5), axis[0] * s, axis[1] * s, axis[2] * s)


def q_matrix(q):
    w, x, y, z = q
    return (
        (1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)),
        (2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)),
        (2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)),
    )


def q_from_rows(r):
    # Quaternion for a rotation matrix given as three rows.
    m00, m01, m02 = r[0]
    m10, m11, m12 = r[1]
    m20, m21, m22 = r[2]
    trace = m00 + m11 + m22
    if trace > 0:
        s = math.sqrt(trace + 1.0) * 2.0
        q = (0.25 * s, (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s)
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        q = ((m21 - m12) / s, 0.25 * s, (m01 + m10) / s, (m02 + m20) / s)
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        q = ((m02 - m20) / s, (m01 + m10) / s, 0.25 * s, (m12 + m21) / s)
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        q = ((m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, 0.25 * s)
    return q_normalise(q)


def q_angle(a, b):
    # Rotation angle in radians between two orientations.
    d = abs(a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3])
    return 2.0 * math.acos(min(1.0, d))


def q_slerp(a, b, t):
    d = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
    if d < 0:
        b = (-b[0], -b[1], -b[2], -b[3])
        d = -d
    if d > 0.9995:
        return q_normalise((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t))
    theta = math.acos(d)
    s = math.sin(theta)
    wa = math.sin((1.0 - t) * theta) / s
    wb = math.sin(t * theta) / s
    return (a[0] * wa + b[0] * wb, a[1] * wa + b[1] * wb, a[2] * wa + b[2] * wb, a[3] * wa + b[3] * wb)


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def random_axis(rand):
    z = 2.0 * rand() - 1.0
    a = 6.2831853 * rand()
    r = math.sqrt(max(0.0, 1.0 - z * z))
    return (r * math.cos(a), r * math.sin(a), z)
