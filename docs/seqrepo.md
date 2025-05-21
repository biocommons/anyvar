# AnyVar SeqRepo Setup

SeqRepo is a repository system designed to store and manage biological sequence data efficiently.

## Recommended: Local Installation

The simplest and most efficient method for most users is a direct local file installation.


1. **Download the SeqRepo Archive:**

	```shell
	curl -O https://storage.googleapis.com/clingen-public/seqrepo_2024-12-20.tar.gz
	```

2. **Create a SeqRepo Directory:**

	Create a SeqRepo directory, then extract the download inside of it

	```shell
	mkdir seqrepo
	tar -xzvf seqrepo_2024-12-20.tar.gz -C seqrepo
	```

3. **Set the Environment Variable:**

	Configure your environment to point to this SeqRepo location:

	```shell
	export SEQREPO_DATAPROXY_URI=seqrepo+file:///full_path_to_seqrepo/2024-12-20
	```

	Replace `full_path_to_seqrepo` with your absolute path.

## Docker-based Installation

Docker is suitable for containerized environments or users preferring isolation.


1. **Create and Populate Docker Volume:**

	```shell
	docker volume create seqrepo-vol
	docker run -it --rm -v seqrepo-vol:/usr/local/share/seqrepo docker.io/biocommons/seqrepo:2024-12-20
	```

2. **Start SeqRepo REST Service:**

	Run the REST service to provide access through HTTP:

	```shell
	docker run -d --name seqrepo-rest \
	-v seqrepo-vol:/usr/local/share/seqrepo \
	-p 5001:5000 biocommons/seqrepo-rest-service \
	seqrepo-rest-service /usr/local/share/seqrepo/2024-12-20
	```

	Set your environment variable to the REST API:

	```shell
	export SEQREPO_DATAPROXY_URI=seqrepo+http://localhost:5001/seqrepo
	```

## Native Installation (Rrsync Method)

Useful when direct file or Docker setups are not feasible.

1. **Install SeqRepo:**

	```shell
	pip install seqrepo
	```

2. **Prepare Directories:**

	```shell
	export SEQREPO_VERSION=2024-12-20
	sudo mkdir -p /usr/local/share/seqrepo
	sudo chown $USER /usr/local/share/seqrepo
	```

3. **Fetch Data with Rsync:**

	```shell
	seqrepo pull -i $SEQREPO_VERSION
	seqrepo update-latest
	```

4. Set the environment variable accordingly:

	```shell
	export SEQREPO_DATAPROXY_URI=seqrepo+file:///usr/local/share/seqrepo/$SEQREPO_VERSION
	```

### Troubleshooting Rsync Issues

* If your institution blocks rsync, consider using the direct download method or Docker.
* Ensure you have the correct `rsync` CLI (GNU Rsync, not OpenRsync).

Check Rsync version:

```shell
rsync --version
```

## Verifying SeqRepo Installation

Verify local setup with Python:

```python
from ga4gh.vrs.dataproxy import create_dataproxy
uri = "seqrepo+file:///full_path_to_seqrepo/2024-12-20"
seqrepo_dataproxy = create_dataproxy(uri=uri)
sequence = seqrepo_dataproxy.get_sequence("refseq:NM_000551.3")
print(sequence[:100])  # prints first 100 bases
```

For REST API verification:

```shell
curl http://localhost:5001/seqrepo/1/sequence/refseq:NM_000551.3
```

Successful completion of these steps confirms a working SeqRepo installation.

## Additional Environment Variables

| Variable                | Description                             | Example                                              |
| ----------------------- | --------------------------------------- | ---------------------------------------------------- |
| `SEQREPO_VERSION`       | Specifies the SeqRepo snapshot version. | `2024-12-20`                                         |
| `SEQREPO_ROOT_DIR`      | Sets the root directory of SeqRepo.     | `/usr/local/share/seqrepo`                           |
| `SEQREPO_DATAPROXY_URI` | URI for SeqRepo DataProxy interface.    | `seqrepo+file:///usr/local/share/seqrepo/2024-12-20` |

Ensure these environment variables are correctly set before using AnyVar.

---

Your SeqRepo installation is now ready to be used with AnyVar. Refer to the main AnyVar documentation for integration and usage details.
