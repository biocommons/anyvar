# AnyVar UTA Setup

UTA (Universal Transcript Archive) is used to interpret variations on non-genomic sequences, such as transcript-based accessions. It is required for AnyVar operations involving transcript coordinates.

## Recommended Public Instance Usage (for small use cases)

For minimal usage scenarios, utilize the public UTA instance hosted by biocommons.org by setting the following variable in your `.env` file:

```shell
UTA_DB_URL="postgresql://anonymous:anonymous@uta.biocommons.org:5432/uta/uta_20210129b"
```

This public instance is convenient but may experience slower performance during peak usage.

## Docker Installation (Recommended for larger workloads)

A local Docker setup is recommended for consistent performance and reliability.

### Prerequisites

* Ensure Docker and Docker Compose are installed.

  * [Docker Installation](https://docs.docker.com/get-docker/)
  * [Docker Compose Installation](https://docs.docker.com/compose/install/)

### Step-by-Step Docker Installation

1. **Fetch UTA Docker Image:**

    ```shell
    uta_version=uta_20241220
    docker pull biocommons/uta:${uta_version}
    ```
    _This process will likely take 1-3 minutes._

2. **Create and Populate Docker Volume:**

    Create a persistent volume to store UTA data:

    ```shell
    docker volume create uta_vol
    ```

3. **Run the UTA Docker Container:**

    Start the container and populate the database:

    ```shell
    docker run  --platform linux/amd64 -d --rm -e POSTGRES_PASSWORD=uta \
      -v uta_vol:/var/lib/postgresql/dat  a \
      --name $uta_version -p 5432:5432 biocommons/uta:${uta_version}
    ```

4. **Monitor data population (initial run only):**

    ```shell
    docker logs -f $uta_version
    ```
    Once the log indicates readiness (`database system is ready`), your UTA installation is active.

5. **Set Environment Variable:**

    Configure AnyVar to use UTA by setting the following variable in your `.env` file:
    ```shell
    UTA_DB_URL="postgresql://anonymous@localhost:5432/uta/uta_20241220"
    ```

### Verifying UTA Installation

Check database connectivity using PostgreSQL CLI:

```shell
psql -h localhost -U anonymous -d uta -c "select * from uta_20241220.meta"
```

A successful query returns metadata indicating the version and setup details.

## Troubleshooting and Validation

* **Connection Issues:** Ensure port 5432 is available, or change the port if conflicts arise. Be sure to update your `UTA_DB_URL` environment variable if you change the port number.

  ```shell
  docker run --platform linux/amd64 -d --rm -e POSTGRES_PASSWORD=uta \
  -v uta_vol:/var/lib/postgresql/data \
  --name $uta_version -p 5433:5432 biocommons/uta:${uta_version}

  export UTA_DB_URL=postgresql://anonymous@localhost:5433/uta/uta_20241220
  ```

* **Volume Persistence:** Verify volume status:

  ```shell
  docker volume inspect uta_vol
  ```

* **Docker Container Logs:** Check logs for container issues:

  ```shell
  docker logs $uta_version
  ```

## Cheat Sheat: Environment Variables

| Variable     | Description                     | Example                                                  |
| ------------ | ------------------------------- | -------------------------------------------------------- |
| `UTA_DB_URL` | Database connection URL for UTA | `postgresql://anonymous@localhost:5432/uta/uta_20241220` |

Ensure the environment variable is set before starting AnyVar.

---

Your local UTA installation is now configured for optimal performance with AnyVar. Refer to the primary AnyVar documentation for further details on integration and usage.
