FROM python:3.10

WORKDIR /app

# TODO specify normalizer version with env var
RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install variation-normalizer

# TODO get seqrepo if unavailable
ENV SEQREPO_DATA_PATH=data/seqrepo/latest

RUN mkdir ~/.aws \
    && echo "[default]\naws_access_key_id=XXXXXXXXXXXXXX\naws_secret_access_key=YYYYYYYYYYYYYYYYYYYYYYYYYYY" > ~/.aws/credentials


CMD uvicorn variation.main:app --port=6999
