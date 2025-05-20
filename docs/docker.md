# AnyVar Docker Compose Setup

Docker Compose simplifies managing multiple Docker containers required by AnyVar, including SeqRepo and UTA services. This setup is ideal for consistent and efficient development, testing, and deployment environments.

## Benefits of Docker Compose

* Simplifies container orchestration.
* Manages interdependencies between services.
* Easily replicable environments.

## Step-by-Step Docker Compose Setup

### Prerequisites

* Ensure Docker and Docker Compose are installed.

  * [Docker Installation](https://docs.docker.com/get-docker/)
  * [Docker Compose Installation](https://docs.docker.com/compose/install/)

### 1. Preparing Docker Volumes

Create volumes to persist data for SeqRepo and UTA:

```shell
docker volume create seqrepo_vol
docker volume create uta_vol
docker volume create uta_dl_cache
```

### 2. Configuring `docker-compose.yaml`

Use this comprehensive configuration:

```yaml
version: '3.8'

services:
  seqrepo_local_populator:
    image: alpine
    volumes:
      - seqrepo_vol:/usr/local/share/seqrepo
      - $HOME/dev/data/seqrepo:/seqrepo
    command: >
      /bin/sh -c "cp -r /seqrepo/2024-12-20 /usr/local/share/seqrepo/"

  seqrepo-rest-service:
    image: biocommons/seqrepo-rest-service:0.2.2
    volumes:
      - seqrepo_vol:/usr/local/share/seqrepo
    depends_on:
      seqrepo_local_populator:
        condition: service_completed_successfully
    command: seqrepo-rest-service -w /usr/local/share/seqrepo/2024-12-20
    ports:
      - 5001:5000

  uta:
    image: biocommons/uta:uta_20241220
    environment:
      - POSTGRES_PASSWORD=your-secure-password
    volumes:
      - uta_dl_cache:/tmp
      - uta_vol:/var/lib/postgresql/data
    ports:
      - 5433:5432

volumes:
  seqrepo_vol:
    external: true
  uta_vol:
    external: true
  uta_dl_cache:
    external: true
```

Replace `$HOME/dev/data/seqrepo` with the path to your SeqRepo data directory.

### 3. Starting Docker Compose Services

Launch services:

```shell
docker-compose up -d
```

### 4. Stopping Docker Compose Services

Stop all running services:

```shell
docker-compose down
```

## Verifying Docker Compose Setup

Verify services are running:

```shell
docker-compose ps
```

Check individual service logs:

```shell
docker-compose logs seqrepo-rest-service
docker-compose logs uta
```

## Troubleshooting and Volume Management

### Persistent Data Volumes

Inspect data persistence:

```shell
docker volume inspect seqrepo_vol
docker volume inspect uta_vol
```

### Common Issues and Fixes

* **Port conflicts:** Modify port mappings in `docker-compose.yaml` if defaults (`5001`, `5433`) conflict with other services.
* **Startup issues:** Check logs to identify and resolve errors promptly.

## Environment Variables

Configure your AnyVar environment to match these Docker Compose services:

```shell
export SEQREPO_DATAPROXY_URI=seqrepo+http://localhost:5001/seqrepo
export UTA_DB_URL=postgresql://anonymous@localhost:5433/uta/uta_20241220
```

Ensure these variables are consistently set before using AnyVar.

---

Your Docker Compose environment for AnyVar is now ready. Refer to the main AnyVar documentation for integration and operational details.
