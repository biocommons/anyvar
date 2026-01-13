FROM python:3.12-slim AS build

LABEL org.opencontainers.image.source=https://github.com/biocommons/anyvar
LABEL org.opencontainers.image.description="AnyVar container image"
LABEL org.opencontainers.image.licenses=Apache-2.0

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    curl \
    git \
    libpq-dev \
    python3-pip \
    python3-venv \
    rsync \
    zlib1g-dev \
    postgresql \
    ;

WORKDIR /app
RUN python3.12 -m venv /app/venv
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
COPY .git /app/.git
ENV PATH=/app/venv/bin:$PATH
RUN pip install -e '.[dev,test,queueing,postgres]'

FROM python:3.12-slim AS anyvar

RUN apt-get update && apt-get install -y libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/venv /app/venv
COPY --from=build /app/src /app/src
COPY --from=build /app/pyproject.toml /app/pyproject.toml

ENV PATH=/app/venv/bin:$PATH

EXPOSE 8000

CMD ["uvicorn", "--host=0.0.0.0", "anyvar.restapi.main:app"]
