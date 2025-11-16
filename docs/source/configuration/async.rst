Asynchronous Processing Configuration
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

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
     - ``7200``
   * - ``CELERY_TASK_ACKS_LATE``
     - ``true``
   * - ``CELERY_TASK_REJECT_ON_WORKER_LOST``
     - ``false``
   * - ``CELERY_WORKER_PREFETCH_MULTIPLIER``
     - ``3900``
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
