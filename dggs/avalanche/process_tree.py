import re
import os
from dggs.avalanche import params


thisdir = os.path.split(os.path.abspath(__file__))[0]
ptdir = os.path.join(thisdir, 'process_trees')

def list_all():
    """Lists leafname of all process trees"""
    for leaf in os.listdir(ptdir):
        if leaf.endswith('.dcp'):
            yield leaf



import re

rep = {"condition1": "", "condition2": "text"} # define desired replacements here

# --------------------------------------------------------------------
template_params = paramutil.parse([
    ('name', None, 'str', True,
        """Root name of scene; to use for filenames, plotting, etc"""),
    ('scene_dir', None, 'path', True,
        'Top-level directory of this scene / project'),
    ('return_period', 'y', 'int', True,
        "Period of expected avalanche return for this run"),
    ('forest', None, 'bool', True,
        "Is this segmentation with forests?"),
])

def get(**kwargs):

    """Loads a .dcp file as a template; does some simple
    search-and-replace to make it portable in the filesystem."""

    template_args = {k:str(v) for k,v in paramutil.validate_args(kwargs, params=template_params).items()}
    template_args['_For'] = '_For' if template_args['forest'] else '_NoFor'
    template_args['LEFT_BRACKET'] = '{'
    template_args['RIGHT_BRACKET'] = '}'

    # Intepret certain patterns in the text as template args
    return process_tree_tpl.format(**template_args)





    
# 16 process trees total

#grep 'ProcBase Name=.Process tree' *.dcp | less
#...yields a repeat only on GHK_VS_10yNoFor.dcp



# ============================================================================
# Originally from file GHK_VS_300y_For.dcp
