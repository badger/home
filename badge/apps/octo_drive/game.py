"""Pure-Python driving rules for Octo Drive."""

TRACK = (
    ("COAST ROAD", 900, 0.00, 0.05),
    ("OCTO SWEEP", 800, 0.42, 0.00),
    ("PINE RIDGE", 900, -0.55, 0.18),
    ("OPEN SOURCE", 700, 0.00, -0.08),
    ("MERGE BEND", 850, 0.72, 0.04),
    ("CACHE VALLEY", 900, -0.32, -0.18),
    ("SHIP IT", 950, 0.18, 0.10),
)
TRACK_LENGTH = sum(segment[1] for segment in TRACK)
CHECKPOINTS = tuple(int(TRACK_LENGTH * part / 4) for part in range(1, 5))
QUARTER_LENGTH = TRACK_LENGTH / 4
TRAFFIC_COUNTS = (2, 4, 6, 8)
HAZARD_COUNTS = (2, 3, 5, 7)
LANES = (-0.62, 0.0, 0.62)
HAZARD_KINDS = ("cone", "oil", "barrier")

START_TIME = 28.0
CHECKPOINT_BONUS = 17.0
MAX_SPEED = 220.0
OFFROAD_MAX = 105.0
VIEW_DISTANCE = 520.0


def clamp(value, low, high):
    return low if value < low else high if value > high else value


def track_at(distance):
    """Return the name, curve and hill at a distance along the course."""
    distance = clamp(distance, 0.0, TRACK_LENGTH - 0.001)
    cursor = 0.0
    for name, length, curve, hill in TRACK:
        if distance < cursor + length:
            local = (distance - cursor) / length
            blend = min(local / 0.12, (1.0 - local) / 0.12, 1.0)
            return name, curve * max(0.25, blend), hill * max(0.25, blend)
        cursor += length
    return TRACK[-1][0], TRACK[-1][2], TRACK[-1][3]


class Controls:
    def __init__(self):
        self.left = False
        self.right = False
        self.accelerate = False
        self.brake = False


class Traffic:
    def __init__(self, distance, lane, speed, colour):
        self.distance = float(distance)
        self.lane = float(lane)
        self.speed = float(speed)
        self.colour = colour
        self.passed = False
        self.active = False
        self.collided = False


class Hazard:
    def __init__(self, distance, lane, kind):
        self.distance = float(distance)
        self.lane = float(lane)
        self.kind = kind
        self.hit = False


class Session:
    def __init__(self, high=0):
        self.score = 0
        self.high = high
        self.best_time = None

    def add_score(self, points):
        self.score += int(points)
        self.high = max(self.high, self.score)


class World:
    def __init__(self, high=0):
        self.session = Session(high)
        self.distance = 0.0
        self.speed = 0.0
        self.lane = 0.0
        self.time_left = START_TIME
        self.elapsed = 0.0
        self.state = "play"
        self.next_checkpoint = 0
        self.collision_time = 0.0
        self.score_fraction = 0.0
        self.events = []
        self.traffic = self._build_traffic()
        self.hazards = self._build_hazards()

    def _build_traffic(self):
        traffic = []
        for quarter, count in enumerate(TRAFFIC_COUNTS):
            start = quarter * QUARTER_LENGTH + 260
            span = QUARTER_LENGTH - 420
            for index in range(count):
                distance = start + span * (index + 1) / (count + 1)
                lane = LANES[(index + quarter) % len(LANES)]
                speed = 88 + ((index * 17 + quarter * 11) % 48)
                traffic.append(Traffic(distance, lane, speed, (index + quarter) % 4))
        return traffic

    def _build_hazards(self):
        hazards = []
        for quarter, count in enumerate(HAZARD_COUNTS):
            start = quarter * QUARTER_LENGTH + 520
            span = QUARTER_LENGTH - 700
            for index in range(count):
                distance = start + span * (index + 1) / (count + 1)
                lane = LANES[(index * 2 + quarter) % len(LANES)]
                kind = HAZARD_KINDS[(index + quarter) % len(HAZARD_KINDS)]
                hazards.append(Hazard(distance, lane, kind))
        return hazards

    @property
    def progress(self):
        return clamp(self.distance / TRACK_LENGTH, 0.0, 1.0)

    @property
    def section(self):
        return track_at(self.distance)[0]

    def step(self, dt, controls):
        if self.state != "play":
            return
        dt = min(max(dt, 0.0), 0.05)
        self.elapsed += dt
        self.time_left -= dt
        self.collision_time = max(0.0, self.collision_time - dt)
        if self.time_left <= 0:
            self.time_left = 0.0
            self.speed = 0.0
            self.state = "time_up"
            self.events.append(("time_up", 0))
            return

        if controls.accelerate:
            self.speed += (92.0 - self.speed * 0.12) * dt
        elif controls.brake:
            self.speed -= 175.0 * dt
        else:
            self.speed -= (28.0 + self.speed * 0.035) * dt

        steer = (1 if controls.right else 0) - (1 if controls.left else 0)
        grip = 0.38 + 0.92 * self.speed / MAX_SPEED
        self.lane += steer * grip * dt
        curve = track_at(self.distance)[1]
        self.lane -= curve * (self.speed / MAX_SPEED) * 0.34 * dt

        offroad = abs(self.lane) > 1.0
        if offroad and self.speed > OFFROAD_MAX:
            self.speed -= 115.0 * dt
        self.speed = clamp(self.speed, 0.0, MAX_SPEED)
        self.lane = clamp(self.lane, -1.36, 1.36)

        previous_distance = self.distance
        travelled = self.speed * dt
        self.distance += travelled
        self.score_fraction += travelled * (1.3 if not offroad else 0.65)
        points = int(self.score_fraction)
        if points:
            self.session.add_score(points)
            self.score_fraction -= points

        self._step_traffic(dt, previous_distance)
        self._check_hazards()
        self._check_checkpoints()

    def _step_traffic(self, dt, previous_distance):
        for car in self.traffic:
            if not car.active:
                if car.distance - self.distance > 850:
                    continue
                car.active = True
            before = car.distance - previous_distance
            car.distance += car.speed * dt
            after = car.distance - self.distance
            if before >= 0 > after and not car.passed:
                car.passed = True
                self.session.add_score(250)
                self.events.append(("pass", car.colour))
            if (
                self.collision_time <= 0
                and not car.collided
                and abs(after) < 9.0
                and abs(car.lane - self.lane) < 0.34
                and self.speed > car.speed + 8
            ):
                car.collided = True
                self.speed = max(45.0, car.speed * 0.65)
                self.lane += -0.18 if car.lane >= self.lane else 0.18
                self.collision_time = 0.8
                self.session.add_score(-100)
                self.events.append(("collision", car.colour))

    def _check_hazards(self):
        if self.collision_time > 0:
            return
        for hazard in self.hazards:
            if (
                not hazard.hit
                and abs(hazard.distance - self.distance) < 9.0
                and abs(hazard.lane - self.lane) < 0.32
            ):
                hazard.hit = True
                self.collision_time = 0.65
                if hazard.kind == "cone":
                    self.speed *= 0.68
                    penalty = 75
                elif hazard.kind == "oil":
                    self.speed *= 0.84
                    self.lane += -0.48 if int(hazard.distance / 100) & 1 else 0.48
                    penalty = 100
                else:
                    self.speed = max(25.0, self.speed * 0.42)
                    penalty = 175
                self.lane = clamp(self.lane, -1.36, 1.36)
                self.session.add_score(-penalty)
                self.events.append(("hazard", hazard.kind))
                return

    def _check_checkpoints(self):
        while (
            self.next_checkpoint < len(CHECKPOINTS)
            and self.distance >= CHECKPOINTS[self.next_checkpoint]
        ):
            number = self.next_checkpoint + 1
            self.next_checkpoint += 1
            if number == len(CHECKPOINTS):
                self.distance = TRACK_LENGTH
                self.speed = 0.0
                self.state = "finished"
                self.session.best_time = self.elapsed
                self.session.add_score(3000 + int(self.time_left * 100))
                self.events.append(("finish", number))
            else:
                self.time_left += CHECKPOINT_BONUS
                self.session.add_score(1000)
                self.events.append(("checkpoint", number))
