"""Original stages for Super Mona

Each factory returns a fresh Level so restarting a stage resets its blocks,
stars and enemies. Rows run 0 (top) to 14; ground tops sit on row 13.
"""

from game import Level


def scenery(level, hills=(), bushes=(), clouds=()):
    for x in hills:
        level.hill(x)
    for x in bushes:
        level.bush(x)
    for x, y in clouds:
        level.cloud(x, y)


def hello_world():
    lv = Level("1-1 HELLO WORLD", 190, "day", 300, switch=False)
    lv.ground(0, 68)
    lv.ground(71, 85)
    lv.ground(89, 150)
    lv.ground(153, 189)
    scenery(lv,
            hills=(0, 40, 92, 140, 178),
            bushes=(9, 33, 60, 104, 130, 157),
            clouds=((6, 3), (24, 2), (47, 4), (70, 3), (96, 2), (118, 4),
                    (146, 3), (166, 2)))

    lv.row(12, 9, "Q")
    lv.row(18, 9, "B-B")
    lv.block(19, 9, "chip")
    lv.star_line(18, 5, 3)
    lv.enemy(24)
    lv.pipe(28, 2)
    lv.enemy(33)
    lv.pipe(38, 3)
    lv.enemy(44)
    lv.enemy(46)
    lv.pipe(52, 4)
    lv.star_line(57, 10, 4)
    lv.enemy(63, "shellbot")

    lv.star_line(68, 9, 4)
    lv.row(74, 9, "BB-BB")
    lv.block(76, 9, "multi6", brick=True)
    lv.block(78, 5, "1up", brick=True)
    lv.enemy(81, "shellbot")

    lv.star_line(86, 8, 3)
    lv.row(92, 9, "QQQ")
    lv.enemy(96)
    lv.enemy(98)
    lv.row(100, 9, "BBBBBB")
    lv.block(103, 5, "sparkle")
    lv.star_line(100, 4, 3)
    lv.enemy(108, "shellbot")
    lv.enemy(112)
    lv.enemy(114)

    lv.stairs(120, 4)
    lv.stairs(124, 4, up=False)
    lv.enemy(132)
    lv.pipe(138, 2)
    lv.row(144, 9, "Q", "chip")
    lv.star_line(150, 8, 4)
    lv.enemy(157)
    lv.enemy(159)
    lv.stairs(161, 7)
    lv.flag(176)
    return lv


def server_room():
    lv = Level("1-2 SERVER ROOM", 165, "cave", 300, switch=True)
    lv.ground(0, 39)
    lv.ground(43, 77)
    lv.ground(81, 103)
    lv.ground(107, 164)
    lv.ceiling(0, 150)

    lv.row(10, 9, "QQQ")
    lv.block(13, 9, "chip")
    lv.enemy(18)
    lv.enemy(20)
    for y in (10, 11, 12):
        lv.row(26, y, "BB")
    lv.row(32, 8, "BBBBBB")
    lv.star_line(33, 7, 4)
    lv.star_line(40, 9, 3)

    lv.enemy(46, "shellbot")
    lv.enemy(50)
    lv.enemy(52)
    lv.row(56, 9, "BB-BB")
    lv.block(58, 9, "sparkle")
    lv.row(56, 5, "BBBBB")
    lv.pipe(66, 3)
    lv.enemy(70)
    lv.pipe(72, 2)
    lv.star_line(78, 9, 3)

    lv.row(84, 9, "BBBBBBBB")
    lv.row(84, 5, "BBBBBBBB")
    lv.block(88, 9, "multi8", brick=True)
    lv.star_line(85, 7, 6)
    lv.enemy(94)
    lv.enemy(96)
    lv.enemy(99, "shellbot")
    lv.star_line(104, 9, 3)

    lv.stairs(112, 4)
    lv.row(122, 9, "Q", "1up")
    lv.enemy(128)
    lv.enemy(130)
    lv.row(134, 9, "Q", "chip")
    lv.stairs(140, 6)
    lv.flag(152)
    return lv


def sky_bridge():
    lv = Level("1-3 SKY BRIDGE", 175, "dusk", 300, switch=True)
    lv.ground(0, 20)
    lv.ground(33, 50)
    lv.ground(72, 95)
    lv.ground(100, 120)
    lv.ground(127, 174)
    scenery(lv,
            hills=(2, 36, 76, 130, 165),
            bushes=(12, 45, 88, 110, 140),
            clouds=((8, 3), (28, 2), (52, 4), (80, 2), (108, 3), (136, 2),
                    (156, 4)))

    lv.row(10, 9, "QBQ")
    lv.enemy(15)
    lv.row(24, 10, "======")
    lv.star_line(24, 9, 6)

    lv.pipe(38, 3)
    lv.enemy(42, "shellbot")
    lv.row(44, 9, "BQB", "chip")
    lv.enemy(47)

    lv.row(54, 10, "====")
    lv.row(60, 8, "====")
    lv.row(66, 10, "====")
    lv.star_line(60, 7, 4)
    lv.enemy(62, "bug", y=7)

    lv.enemy(78)
    lv.enemy(80)
    lv.enemy(83, "shellbot")
    lv.row(86, 9, "Q", "sparkle")
    lv.stairs(90, 3)
    lv.row(97, 11, "==")

    lv.row(104, 9, "BB-BB")
    lv.block(106, 9, "multi6", brick=True)
    lv.enemy(108)
    lv.enemy(110)
    lv.pipe(114, 4)
    lv.row(122, 9, "====")
    lv.star_line(122, 8, 4)

    lv.enemy(132, "shellbot")
    lv.enemy(134)
    lv.enemy(136)
    lv.block(140, 9, "1up")
    lv.enemy(146)
    lv.stairs(150, 6)
    lv.flag(162)
    return lv


LEVELS = (hello_world, server_room, sky_bridge)
