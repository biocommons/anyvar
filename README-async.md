# AnyVar Asynchronous VCF Annotation
AnyVar can use an
[asynchronous request-response pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/async-request-reply)
when annotating VCF files.  This can improve reliability when serving remote clients by
eliminating long lived connections and allow AnyVar to scale horizontally instead of vertically
to serve a larger request volume.  AnyVar utilizes the [Celery](https://docs.celeryq.dev/)
distributed task queue to manage the asynchronous tasks.

## How It Works
AnyVar can be run as a FastAPI app that provides a REST API.  The REST API is run using
uvicorn or gunicorn, eg:
```shell
% uvicorn anyvar.restapi.main:app
```

AnyVar can also be run as a Celery worker app that processes tasks submitted through the REST API, eg:
```shell
% celery -A anyvar.queueing.celery_worker:celery_app worker
```

When VCF files are submitted to the `/vcf` endpoint with the `run_async=True` query parameter,
the REST API submits a task to the Celery worker via a queue and immediately returns a `202 Accepted`
response with a `Location` header indicating where the client should poll for status and results.
Once the VCF is annotated and the result is ready, the polling request will return the annotated
VCF file.  For example:
```
> PUT /vcf?run_async=True HTTP/1.1
> Content-type: multipart/form-data...

< HTTP/1.1 202 Accepted
< Location: /vcf/a1ac7850-0df7-4db6-82ab-b19bce93faf3
< Retry-After: 120

> GET /vcf/a1ac7850-0df7-4db6-82ab-b19bce93faf3 HTTP/1.1

< HTTP/1.1 202 Accepted

> GET /vcf/a1ac7850-0df7-4db6-82ab-b19bce93faf3 HTTP/1.1

> HTTP/1.1 200 OK
>
> ##fileformat=VCFv4.2...
```

The client can provide a `run_id=...` query parameter with the initial PUT request.  If one is not
provided, a random UUID will be generated (as illustrated above).

## Setting Up Asynchronous VCF Processing
Enabling asychronous VCF processing requires some additional setup.

### Install the Necessary Dependencies
Asynchronous VCF processing requires the installation of additional, optional dependencies:
```shell
% pip install .[queueing]
```
This will install the `celery[redis]` module and its dependencies.  To connect Celery to a different
message broker or backend, install the appropriate extras with Celery.

### Start an Instance of Redis
Celery relies on a message broker and result backend to manage the task queue and store results.
The simplest option is to use a single instance of [Redis](https://redis.io) for both purposes.  This
documentation and the default settings will both assume this configuration.  For other message broker
and result backend options, refer to the Celery documentation.

If a Docker engine is available, start a local instance of Redis:
```shell
% docker run -d -p 6379:6379 redis:alpine
```
Or follow the [instructions](https://redis.io/docs/latest/get-started/) to run locally.

### Create a Scratch Directory for File Storage
AnyVar does not store the actual VCF files in Redis for asynchronous processing, only paths to the file.
This allows very large VCF files to be asychronously processed.  All REST API and worker instances of AnyVar
require access to the same shared file system.

### Start the REST API
Start the REST API with environment variables to set shared resource locations:
```shell
% CELERY_BROKER_URL="redis://localhost:6379/0" \
    CELERY_BACKEND_URL="redis://localhost:6379/0" \
    ANYVAR_VCF_ASYNC_WORK_DIR="/path/to/shared/file/system" \
    uvicorn anyvar.restapi.main:app
```

### Start a Celery Worker
Start a Celery worker with environment variables to set shared resource locations:
```shell
% CELERY_BROKER_URL="redis://localhost:6379/0" \
    CELERY_BACKEND_URL="redis://localhost:6379/0" \
    ANYVAR_VCF_ASYNC_WORK_DIR="/path/to/shared/file/system" \
    celery -A anyvar.queueing.celery_worker:celery_app worker
```
To start multiple Celery workers use the `--concurrency` option.

> [!CAUTION]
> Celery supports different pool types (prefork, threads, etc.).
> AnyVar ONLY supports the `prefork` and `solo` pool types.


### Submit an Async VCF Request
Now that the REST API and Celery worker are running, submit an async VCF request with cURL:
```shell
% curl -v -X PUT -F "vcf=@test.vcf" 'https://localhost:8000/vcf?run_async=True&run_id=12345'
```
And then check its status:
```shell
% curl -v 'https://localhost:8000/vcf/12345'
```

## Additional Environment Variables
In addition to the environment variables mentioned previously, the following environment variables
are directly supported and applied by AnyVar during startup.  It is advisable to understand the underlying
Celery configuration options in more detail before making any changes.  The Celery configuration parameter
name corresponding to each environment variable can be derived by removing the leading `CELERY_` and lower
casing the remaining, e.g.: `CELERY_TASK_DEFAULT_QUEUE` -> `task_default_queue`.
| Variable | Description | Default |
| -------- | ------- | ------- |
| CELERY_TASK_DEFAULT_QUEUE | The name of the queue for tasks | anyvar_q |
| CELERY_EVENT_QUEUE_PREFIX | The prefix for event receiver queue names | anyvar_ev |
| CELERY_TIMEZONE | The timezone that Celery operates in | UTC |
| CELERY_RESULT_EXPIRES | Number of seconds after submission before a result expires from the backend | 7200 |
| CELERY_TASK_ACKS_LATE | Whether workers acknowledge tasks before (`false`) or after (`true`) they are run | true |
| CELERY_TASK_REJECT_ON_WORKER_LOST | Whether to reject (`true`) or fail (`false`) a task when a worker dies mid-task | false |
| CELERY_WORKER_PREFETCH_MULTIPLIER | How many tasks a worker should fetch from the queue at a time | 1 |
| CELERY_TASK_TIME_LIMIT | Maximum time a task may run before it is terminated | 3900 |
| CELERY_SOFT_TIME_LIMIT | Amount of time a task can run before an exception is triggered, allowing for cleanup | 3600 |
| CELERY_WORKER_SEND_TASK_EVENTS | Change to `true` to cause Celery workers to emit task events for monitoring purposes | false |
| ANYVAR_VCF_ASYNC_FAILURE_STATUS_CODE | What HTTP status code to return for failed asynchronous tasks | 500 |
