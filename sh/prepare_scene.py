import sys
from dggs.avalanche import avalanche
import os

"""Script used to prepare scene remotely on Windows host."""

# Scene directory given is relative to user's $HOME
relative_scene_dir = sys.argv[1]
scene_dir = os.path.join(os.environ['HOME'], relative_scene_dir)

avalanche.prepare_data(scene_dir)


