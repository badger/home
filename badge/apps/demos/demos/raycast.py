from picovector import algorithm
import math


class Player:
  def __init__(self):
    self.pos = vec2(8, 8)
    self.angle = 0
    self.fov = 100

  def set_angle(self, angle):
    self.angle = angle

  def vector(self, offset=0, length=1):
    return vec2(
      math.cos((self.angle + offset) * (math.pi / 180)) * length,
      math.sin((self.angle + offset) * (math.pi / 180)) * length
    )


world_map = bytearray((
  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
  1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
  1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
  1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1,
  1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
  1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
  1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1,
  1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1,
  1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1
))


MAP_SIZE_X = 22
MAP_SIZE_Y = 16

if len(world_map) != MAP_SIZE_X * MAP_SIZE_Y:
    raise RuntimeError("Invalid map size!")


player = Player()
minimap_scale = 4 if screen.width == 320 else 2
display_minimap = True


minimap_map = image(MAP_SIZE_X * minimap_scale, MAP_SIZE_Y * minimap_scale)
minimap_map.pen = color.rgb(25, 25, 25, 200)
minimap_map.clear()
minimap_map.pen = color.rgb(100, 100, 100, 100)
for x in range(MAP_SIZE_X):
  for y in range(MAP_SIZE_Y):
    if world_map[int(y * MAP_SIZE_X + x)] == 1:
      minimap_map.rectangle(x * minimap_scale, y * minimap_scale, minimap_scale, minimap_scale)

minimap_overlay = image(MAP_SIZE_X * minimap_scale, MAP_SIZE_Y * minimap_scale)
minimap_overlay_mv = memoryview(minimap_overlay)
minimap_overlay_len = minimap_overlay.width * minimap_overlay.height


@micropython.viper
def clear(buf: ptr32, length: int):
  for i in range(length):
    buf[i] = 0


d_proj = (screen.width / 2) / math.tan(player.fov * (math.pi / 180) / 2)


@micropython.native
def update():
  player.pos = vec2(
    math.sin(badge.ticks / 2000) * 2 + 11,
    math.cos(badge.ticks / 2000) * 2 + 8
  )
  player.set_angle(badge.ticks / 30)

  if display_minimap:
    # clear the minimap overlay to 0, 0, 0, 0
    clear(minimap_overlay_mv, minimap_overlay_len)

    minimap_pos = player.pos * minimap_scale

    minimap_overlay.pen = color.rgb(255, 255, 255)
    minimap_overlay.circle(minimap_pos, 1)

    minimap_overlay.pen = color.rgb(255, 255, 255, 150)
    minimap_overlay.line(minimap_pos, minimap_pos + player.vector(offset = -player.fov / 2, length=2.5 * minimap_scale))
    minimap_overlay.line(minimap_pos, minimap_pos + player.vector(offset = player.fov / 2, length=2.5 * minimap_scale))

  # draw the sky
  screen.pen = color.rgb(128, 128, 255)
  screen.rectangle(0, 0, screen.width, screen.height / 2)

  # cast rays for player sight
  num_rays = screen.width
  result = algorithm.raycast(player.pos, math.radians(player.angle), player.fov, num_rays, 20, world_map, MAP_SIZE_X, MAP_SIZE_Y, screen.width)

  for screen_x, ray in enumerate(result):
    for (tile_id, cb_p, _cb_g, _edge, _offset, distance, _ray_angle) in ray:
      if tile_id == 1:
          height = (2 / distance) * d_proj
          b = min(255, distance * 20)
          screen.pen = color.rgb(255 - b, 255 - b, 255 - b)
          screen.rectangle(screen_x, (screen.height / 2) - (height / 2), 1, height)

          if display_minimap:
            minimap_overlay.pen = color.rgb(255, 255, 255, b)
            minimap_overlay.put(cb_p * minimap_scale)
          break

  if display_minimap:
    # draw the minimap over the top
    screen.blit(minimap_map, vec2(screen.width - minimap_map.width, screen.height - minimap_map.height))
    screen.blit(minimap_overlay, vec2(screen.width - minimap_overlay.width, screen.height - minimap_overlay.height))
