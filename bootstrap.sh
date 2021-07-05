#!/bin/sh

set -e

# OBS is built with Python 3.9
PYTHON_VERSION=3.9
PYTHON=python${PYTHON_VERSION}

DEST=$(dirname $0)
# obs-touchosc.py is expecting `venv`
VENV=${DEST}/venv

# download virtualenv zipapp
curl -sL -o ${DEST}/virtualenv.pyz https://bootstrap.pypa.io/virtualenv.pyz
# create virtual environment
${PYTHON} ${DEST}/virtualenv.pyz ${VENV}
# install dependencies
${VENV}/bin/pip install -r ${DEST}/requirements.txt
# clean up
rm ${DEST}/virtualenv.pyz
