#!/bin/bash
set -eu
thisdir="$(dirname "$(readlink -f "$0")")"
cd "${thisdir}"

source venv/bin/activate
python3 ./main.py
