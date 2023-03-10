FROM python:3.10

WORKDIR /app

# RUN ["/bin/bash", "-c", "if [[ ! -d data/seqrepo ]]; then mkdir -p data; curl -O https://nch-igm-wagner-lab-public.s3.us-east-2.amazonaws.com/seqrepo.tar.gz; tar -xzf seqrepo.tar.gz ; mv seqrepo data/ ; fi"]

# TODO specify variation normalizer version
RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install variation-normalizer

ENV SEQREPO_DATA_PATH=/app/mounted-data/seqrepo/latest

RUN mkdir ~/.aws \
    && echo "[default]\naws_access_key_id=XXXXXXXXXXXXXX\naws_secret_access_key=YYYYYYYYYYYYYYYYYYYYYYYYYYY" > ~/.aws/credentials

CMD ["uvicorn", "variation.main:app"]
