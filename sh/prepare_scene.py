import sys
from dggs import config
from dggs.avalanche import avalanche
import os

"""Script used to prepare scene remotely on Windows host."""

# Scene directory given as path relative to roots
scene_dir_rel = sys.argv[1]
scene_dir = config.roots.abspath(scene_dir_rel)

avalanche.prepare_data(scene_dir)

