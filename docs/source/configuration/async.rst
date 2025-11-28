Asynchronous Processing Configuration
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. _async_work_dir_config:

Required: Work Directory Path
=============================

Designate the directory where AnyVar shares files for asynchronous data processing with ``ANYVAR_VCF_ASYNC_WORK_DIR``. This path **must refer to a shared filesystem** that is accessible to both the web API processes (which write the VCF data) and the Celery worker processes (which read and process it). It is the deployer’s responsibility to provision and mount this shared storage (e.g., via a persistent volume, NFS mount, or network filesystem) into all participating containers.

.. important::

    This value *must* be set for asynchronous processing to function. Note that it also must be set for both central AnyVar processes as well as workers.

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Environment Variable
     - Default Value
   * - ``ANYVAR_VCF_ASYNC_WORK_DIR``
     - n/a

.. _async_broker_config:

Broker/Backend Connection
=========================

These environment variables configure how Celery connects to its `broker and result backend <https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/index.html>`_. When using Redis, the broker and backend typically share the same URL.

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Environment Variable
     - Default Value
   * - ``CELERY_BROKER_URL``
     - ``"redis://localhost:6379/0"``
   * - ``CELERY_BACKEND_URL``
     - ``"redis://localhost:6379/0"``

Celery Task Settings
====================

These variables control how the Celery worker behaves at runtime, including task routing, timeouts, and result handling. See the `Celery configuration documentation <https://docs.celeryq.dev/en/latest/userguide/configuration.html>`_ for details on each setting.

.. note::

   ``CELERY_TASK_TIME_LIMIT`` and ``CELERY_SOFT_TIME_LIMIT`` designate how long a single task is permitted to run, and ``CELERY_BROKER_TRANSPORT_OPTIONS_VISIBILITY_TIMEOUT`` defines how long the task queue waits for a worker to signal that it's finished before reassigning it to another worker. These values should be revised upward in cases where long processing times are anticipated.

   Similarly, ``CELERY_RESULT_EXPIRES`` defines how long a completed task remains in the queue as acknowledged before being erased. For long-running tasks with irregular polling, this value may need to be increased as well.

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Environment Variable
     - Default Value
   * - ``CELERY_TASK_DEFAULT_QUEUE``
     - ``"anyvar_q"``
   * - ``CELERY_EVENT_QUEUE_PREFIX``
     - ``"anyvar_ev"``
   * - ``CELERY_TIMEZONE``
     - ``"UTC"``
   * - ``CELERY_RESULT_EXPIRES``
     - ``"7200"``
   * - ``CELERY_BROKER_TRANSPORT_OPTIONS_VISIBILITY_TIMEOUT``
     - ``"7200"``
   * - ``CELERY_TASK_ACKS_LATE``
     - ``true``
   * - ``CELERY_TASK_REJECT_ON_WORKER_LOST``
     - ``false``
   * - ``CELERY_WORKER_PREFETCH_MULTIPLIER``
     - ``"1"``
   * - ``CELERY_TASK_TIME_LIMIT``
     - ``3900``
   * - ``CELERY_SOFT_TIME_LIMIT``
     - ``3600``
   * - ``CELERY_WORKER_SEND_TASK_EVENTS``
     - ``false``

Misc. VCF Processing
====================

These settings apply specifically to :ref:`VCF processing <vcf_ingest>` and extend how asynchronous ingestion behaves.

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Environment Variable
     - Default Value
   * - ``ANYVAR_VCF_ASYNC_WORK_DIR``
     - n/a
   * - ``ANYVAR_VCF_ASYNC_FAILURE_STATUS_CODE``
     - ``500``

* ``ANYVAR_VCF_ASYNC_WORK_DIR`` specifies the root directory used by the API server and Celery workers to exchange intermediate files.
* ``ANYVAR_VCF_ASYNC_FAILURE_STATUS_CODE`` sets the HTTP status code returned by the run-status endpoint when an internal error occurs.
