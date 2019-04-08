# For now, postgresql libs are required, so
# 
FROM ubuntu:18.10

RUN apt update && apt upgrade -y && apt install -y \
    curl \
    python3-pip

COPY setup.cfg setup.py /app/
COPY src /app/src

WORKDIR /app
RUN python3 setup.py install

EXPOSE 5000

CMD ["python3", "-m", "anyvar"]
