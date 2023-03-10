#!/bin/sh

if [[ ! -d data/seqrepo ]]; then
    curl -O https://nch-igm-wagner-lab-public.s3.us-east-2.amazonaws.com/seqrepo.tar.gz
    unzip seqrepo.zip
    mv seqrepo data/
fi
