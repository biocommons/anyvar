FROM ubuntu:18.10

RUN apt update && apt upgrade -y && apt install -y \
    curl \
    mercurial \
    python3-pip

RUN pip3 install -U setuptools pip

COPY . /app/
WORKDIR /app
RUN python3 setup.py install

EXPOSE 5000

CMD ["python3", "-m", "anyvar"]
