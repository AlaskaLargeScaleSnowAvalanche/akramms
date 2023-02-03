import sys
from akramms import config
from akramms import r_prepare
import os

"""Script used to prepare scene remotely on Windows host."""

# Scene directory given as path relative to roots
scene_dir_rel = sys.argv[1]
scene_dir = config.roots.abspath(scene_dir_rel)

r_prepare.prepare_data(scene_dir)

