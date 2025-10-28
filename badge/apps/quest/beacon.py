from aye_arr.nec.remotes.descriptor import RemoteDescriptor

# nec remote descriptor
class GithubUniverseBeacon(RemoteDescriptor):
  NAME = "GithubUniverseBeacon"

  ADDRESS = 0x45

  BUTTON_CODES = {
    1: 0x11,
    2: 0x22,
    3: 0x33,
    4: 0x44,
    5: 0x55,
    6: 0x66,
    7: 0x77,
    8: 0x88,
    9: 0x99
  }

  def __init__(self):
      super().__init__()