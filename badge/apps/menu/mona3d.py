# Draw the GitHub Mona model on the badge with pico3d.
# Expects /mona_dec_2.0e.p3d on the badge (built by glb2p3d.py from WebGL-Mona's mona2.glb).
# Also loads the older P3DM files from obj2p3d.py, e.g. /mona_xlo.p3d.
# The head pivots at the neck to follow the tilt sensor; the torso stays put.
# Runs standalone, or import it and drive Mona.draw() from another script.

import gc
import math
import struct
import pico3d

# The model to use: 2 px everywhere, with the eyes and mouth held at 0.6 px,
# about 4k triangles (26 fps with vsync off, against 20 for the 0.6 px model).
# Built with:
#   glb2p3d.py mona2.glb mona_dec_2.0e.p3d --error-px 2.0 \
#     --node-error Eye=0.6 --node-error Eyelash=0.6 --node-error Pupil=0.6 \
#     --node-error Pupil_Highlight=0.6 --node-error Mouth=0.6
# /mona_hi.p3d is the full 20k-triangle original; MODELS below has the rest.
MODEL = "/mona_dec_2.0e.p3d"
# left / right step through these; each is (path, label on the counter)
MODELS = [
    ("/mona_hi.p3d", "full"),
    ("/mona_dec.p3d", "0.6px"),
    ("/mona_dec_0.8.p3d", "0.8px"),
    ("/mona_dec_1.0.p3d", "1.0px"),
    ("/mona_dec_2.0.p3d", "2.0px"),
    ("/mona_dec_2.0e.p3d", "2.0px+eyes"),   # the one to use (see MODEL)
]
FIELD_OF_VIEW = 37
# depth is z/w in 16 bits, so the planes hug the model (about 3 to 5.5 units from the camera)
NEAR_PLANE = 2.5
FAR_PLANE = 8.0
CAMERA = pico3d.vec3(0.0, 0.05, 4.2)
TARGET = pico3d.vec3(0.0, 0.05, 0.0)
UP = pico3d.vec3(0.0, 1.0, 0.0)
NECK_Y = -0.95
# uniform size, scaled about the neck so it stays put on screen
SCALE = 1.0
SWAY_DEGREES = 25
SWAY_PERIOD_MS = 7000
IMU_GRAVITY = 16384.0
TILT_GAIN = 90.0
ROLL_LIMIT = 45.0
NOD_LIMIT = 30.0
# Smoothing as time constants, so the feel doesn't change with the frame rate:
# roll and nod ease towards the tilt with TILT_SMOOTH_MS, and the nod's rest
# position drifts to the current lean with NOD_RECENTRE_MS.
TILT_SMOOTH_MS = 180
NOD_RECENTRE_MS = 2800
BACKGROUND = color.rgb(234, 237, 236)
WHITE = color.rgb(255, 255, 255)
BLACK = color.rgb(0, 0, 0)
# The light is ambient only (see Mona.__init__), so Gouraud shading would work
# out a normal and a light value for every vertex just to multiply by white.
# UNLIT draws the same pixels without reading or transforming a normal.
SHADING = pico3d.material.UNLIT


def load_model(path):
    parts = []
    with open(path, "rb") as f:
        magic, count = struct.unpack("<4sI", f.read(8))
        if magic == b"P3DM":
            records = [struct.unpack("<16sIIIIII", f.read(40)) + (0,) for _ in range(count)]
        elif magic == b"P3D2":
            # P3D2 adds a per-vertex colour offset (0 = none) to each record
            records = [struct.unpack("<16sIIIIIII", f.read(44)) for _ in range(count)]
        else:
            raise ValueError("not a P3DM or P3D2 file")
        for name, rgb, nverts, ntris, pos_off, nrm_off, idx_off, col_off in records:
            pos = bytearray(nverts * 12)
            nrm = bytearray(nverts * 12)
            idx = bytearray(ntris * 6)
            f.seek(pos_off)
            f.readinto(pos)
            f.seek(nrm_off)
            f.readinto(nrm)
            f.seek(idx_off)
            f.readinto(idx)
            colors = None
            if col_off:
                colors = bytearray(nverts * 4)
                f.seek(col_off)
                f.readinto(colors)
            mesh = pico3d.mesh(positions=pos, normals=nrm, indices=idx, colors=colors,
                               quantise=True)
            material = pico3d.material(
                color=color.rgb((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255),
                shading=SHADING,
            )
            parts.append((name.rstrip(b"\0").decode(), mesh, material, nverts, ntris))
    return parts


def clamp(value, limit):
    return max(-limit, min(limit, value))


class Mona:
    """Mona rendered onto an image (the screen by default). Call draw() once per frame."""

    def __init__(self, target=None, model=None):
        target = target or screen
        width, height = target.width, target.height
        self.renderer = pico3d.surface(target)
        self.load(model or MODEL)
        projection = pico3d.mat4.perspective(FIELD_OF_VIEW, width / height, NEAR_PLANE, FAR_PLANE)
        self.view_projection = projection * pico3d.mat4.look_at(CAMERA, TARGET, UP)
        # black diffuse leaves the ambient term as the whole light
        self.light = pico3d.light(color=BLACK, ambient=WHITE)
        self.roll = 0.0
        self.nod = 0.0
        self.rest_z = None
        self.tilt_ticks = None
        self.started = badge.ticks
        self.scale = SCALE

    def load(self, path):
        """Swap in the model at path, with a scene sized to it."""
        # drop the old model and scene first: the full one is large
        self.parts = self.geometry = None
        gc.collect()
        self.parts = load_model(path)
        total_verts = sum(p[3] for p in self.parts)
        total_tris = sum(p[4] for p in self.parts)
        self.geometry = pico3d.scene(
            self.renderer, meshes=len(self.parts), vertices=total_verts, triangles=total_tris
        )

    def sized(self, m):
        """Scale m by self.scale about the neck, which keeps the neck where it is on screen."""
        return m.translate(0, NECK_Y, 0).scale(self.scale).translate(0, -NECK_Y, 0)

    def update_tilt(self):
        ax, ay, az = badge.imu()[:3]
        now = badge.ticks
        dt = min(now - self.tilt_ticks, 200) if self.tilt_ticks is not None else 0
        self.tilt_ticks = now
        smooth = 1 - math.exp(-dt / TILT_SMOOTH_MS)
        recentre = 1 - math.exp(-dt / NOD_RECENTRE_MS)
        # sideways gravity rolls the head the opposite way so it stays level.
        # Forward and back lean nods it relative to a slowly recentred rest, so a
        # badge lying flat settles with the head straight.
        if self.rest_z is None:
            self.rest_z = az
        self.rest_z += (az - self.rest_z) * recentre
        self.roll += (clamp(-ax / IMU_GRAVITY * TILT_GAIN, ROLL_LIMIT) - self.roll) * smooth
        self.nod += (clamp((az - self.rest_z) / IMU_GRAVITY * TILT_GAIN, NOD_LIMIT) - self.nod) * smooth

    def draw(self, lift=0.0):
        """Render Mona raised by lift world units; negative sinks her below the frame.
        Returns the number of triangles drawn."""
        self.prepare(lift)
        return self.render()

    def prepare(self, lift=0.0):
        """The CPU half of a frame: tilt, matrices and scene adds. Touches no
        pixels, so with async display updates it runs while the previous frame
        is still streaming to the panel; clear() and render() after it."""
        self.update_tilt()
        sway = SWAY_DEGREES * math.sin((badge.ticks - self.started) * 2 * math.pi / SWAY_PERIOD_MS)
        body_model = self.sized(pico3d.mat4().translate(0, lift, 0)).rotate_y(sway)
        head_model = (
            self.sized(pico3d.mat4().translate(0, lift, 0))
            .rotate_y(sway)
            .translate(0, NECK_Y, 0)
            .rotate_z(self.roll)
            .rotate_x(self.nod)
            .translate(0, -NECK_Y, 0)
        )
        geometry = self.geometry
        geometry.reset()
        for name, mesh, material, _, _ in self.parts:
            model = body_model if name == "torso" else head_model
            geometry.add(mesh, model, self.view_projection, material, self.light)

    def render(self):
        """Rasterise what prepare() queued; the first pixel write waits for the
        panel to finish with the previous frame."""
        return self.renderer.draw(self.geometry)


# off while profiling, so the counter shows the real frame time rather than
# the next display refresh
USE_VSYNC = True

if __name__ == "__main__":
    badge.mode(HIRES | VSYNC if USE_VSYNC else HIRES)
    # the frame streams to the panel while the next one is being built; the
    # first framebuffer write of the new frame waits for it (display fence)
    display.set_async(True)
    badge.default_clear = BACKGROUND   # cleared for free when the fence opens
    pico3d.engine.cores(2)
    # six bands balance the two cores best for this model (measured 2026-09-29)
    pico3d.engine.work_bands(6)
    model_index = [m[0] for m in MODELS].index(MODEL)
    mona = Mona(model=MODEL)
    frames = 0
    last_report = badge.ticks
    # on-screen counter: fps over the last half second, and triangles drawn
    screen.font = font.futile
    hud_frames = 0
    hud_start = badge.ticks
    hud_fps = 0.0
    while True:
        # badge.update() polls the buttons at the end of each frame, so no
        # poll here: a second one would clear the press it just caught.
        # The frame is ordered around the async display: prepare() (tilt,
        # matrices, scene adds - no pixels) runs while the last frame still
        # streams to the panel; the clear is the first pixel write, so it is
        # what waits for the stream to finish.
        # down toggles between full and half size
        if badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
            step = 1 if badge.pressed(BUTTON_RIGHT) else -1
            # skip models this badge doesn't have on it
            for _ in range(len(MODELS)):
                model_index = (model_index + step) % len(MODELS)
                try:
                    mona.load(MODELS[model_index][0])
                    break
                except OSError:
                    pass
        if badge.pressed(BUTTON_DOWN):
            mona.scale = SCALE * 0.5 if mona.scale == SCALE else SCALE
        mona.prepare()
        drawn = mona.render()
        hud_frames += 1
        if badge.ticks - hud_start >= 500:
            hud_fps = hud_frames * 1000 / (badge.ticks - hud_start)
            hud_frames = 0
            hud_start = badge.ticks
        screen.pen = color.rgb(40, 40, 48)
        screen.text("%s  %.1f fps  %d tris" % (MODELS[model_index][1], hud_fps, drawn), 4, 2)
        badge.update()
        frames += 1
        if badge.ticks - last_report >= 5000:
            print("%.1f fps  roll %.1f nod %.1f" % (
                frames * 1000 / (badge.ticks - last_report), mona.roll, mona.nod))
            frames = 0
            last_report = badge.ticks
