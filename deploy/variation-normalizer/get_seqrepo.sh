#!/bin/sh
# TODO set variation normalizer version with env var

python3 -m pip install --upgrade pip
python3 -m pip install variation-normalizer
apt install -y rsync
seqrepo pull
