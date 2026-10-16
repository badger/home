import os
import sys

demos = {}
for file in os.listdir(__path__):
  file = file.rsplit(".", 1)[0]
  if not file.startswith(("__", ".")):
    demos[file] = __path__ + "/" + file

sys.modules[__name__].demos = demos
