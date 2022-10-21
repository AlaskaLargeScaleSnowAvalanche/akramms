#!/bin/sh
#

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

source $HOME/opt/conda/m39/etc/profile.d/conda.sh
#conda activate avalanche
source $HOME/av/akramms/loadenv
echo $PYTHONPATH
python $SCRIPT_DIR/run_ramms.py "$@"
