#!/bin/bash
#

echo 'BEGIN runaval.sh'

AKRAMMS_DIR="$1"
source $AKRAMMS_DIR/loadenv

printenv

python $AKRAMMS_DIR/sh/runaval.py "${@:2}"
