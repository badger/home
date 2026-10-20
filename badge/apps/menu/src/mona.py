import math

import pico3d
from mona3d import NECK_Y, SWAY_PERIOD_MS, Mona, clamp

MODEL = "/system/apps/menu/mona_menu.p3d"
STAGE_X = 1.44
STAGE_Y = -0.48
STAGE_SCALE = 0.62
WORK_BANDS = 3

HEAD_X = 299
HEAD_Y = 188
LOOK_DISTANCE = 200
YAW_LIMIT = 40
PITCH_LIMIT = 25
BODY_FOLLOW = 0.3
LOOK_SMOOTH_MS = 160
SWAY_DEGREES = 6
DUCK_LIFT = -0.12
DUCK_LEFT = 240
DUCK_TOP = 120
DUCK_SMOOTH_MS = 140
# the scene is rebuilt only once the pose has moved this far since the last build
REBUILD_DEGREES = 0.25
REBUILD_UNITS = 0.002


shared_mona = None


def shared():
    global shared_mona
    if shared_mona is None:
        shared_mona = MenuMona()
    return shared_mona


class MenuMona(Mona):
    def __init__(self):
        pico3d.engine.cores(2)
        pico3d.engine.work_bands(WORK_BANDS)
        super().__init__(model=MODEL)
        self.scale = STAGE_SCALE
        self.yaw = 0.0
        self.pitch = 0.0
        self.look_ticks = None
        self.duck = 0.0
        self.built = None

    def look_at(self, x, y):
        now = badge.ticks
        dt = min(now - self.look_ticks, 200) if self.look_ticks is not None else 1000
        self.look_ticks = now
        smooth = 1 - math.exp(-dt / LOOK_SMOOTH_MS)
        target_yaw = clamp(math.degrees(math.atan2(x - HEAD_X, LOOK_DISTANCE)), YAW_LIMIT)
        target_pitch = clamp(math.degrees(math.atan2(y - HEAD_Y, LOOK_DISTANCE)), PITCH_LIMIT)
        self.yaw += (target_yaw - self.yaw) * smooth
        self.pitch += (target_pitch - self.pitch) * smooth
        target_duck = DUCK_LIFT if x > DUCK_LEFT and y > DUCK_TOP else 0.0
        self.duck += (target_duck - self.duck) * (1 - math.exp(-dt / DUCK_SMOOTH_MS))

    def prepare(self, lift=0.0):
        self.update_tilt()
        sway = SWAY_DEGREES * math.sin((badge.ticks - self.started) * 2 * math.pi / SWAY_PERIOD_MS)
        yaw = self.yaw + sway
        tilt = self.nod + self.pitch
        height = lift + self.duck
        built = self.built
        if (
            built is not None
            and abs(yaw - built[0]) < REBUILD_DEGREES
            and abs(self.roll - built[1]) < REBUILD_DEGREES
            and abs(tilt - built[2]) < REBUILD_DEGREES
            and abs(height - built[3]) < REBUILD_UNITS
        ):
            return
        self.built = (yaw, self.roll, tilt, height)
        stage = pico3d.mat4().translate(STAGE_X, STAGE_Y + height, 0)
        base = self.sized(pico3d.mat4())
        body_model = stage * base.rotate_y(yaw * BODY_FOLLOW)
        head_model = stage * (
            base.rotate_y(yaw)
            .translate(0, NECK_Y, 0)
            .rotate_z(self.roll)
            .rotate_x(tilt)
            .translate(0, -NECK_Y, 0)
        )
        geometry = self.geometry
        geometry.reset()
        for name, mesh, material, _, _ in self.parts:
            model = body_model if name == "torso" else head_model
            geometry.add(mesh, model, self.view_projection, material, self.light)
