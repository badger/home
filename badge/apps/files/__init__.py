import sys
import os

sys.path.insert(0, "/system/apps/files")
os.chdir("/system/apps/files")

from file_list import FileList
from text_file import TextFileViewer

stack = []


def close_file_viewer():
    if len(stack) > 1 and isinstance(stack[-1], TextFileViewer):
        stack.pop()


def open_file_viewer(file_path):
    stack.append(TextFileViewer(file_path, on_close=close_file_viewer))


########################################################################################

stack.append(FileList(open_action=open_file_viewer))


def update():
    stack[-1].update()
