Logging Configuration
!!!!!!!!!!!!!!!!!!!!!

Default Behavior
========================

By default, AnyVar logs at the ``INFO`` level to standard output, providing sufficient details for general usage. The default format includes timestamps, log levels, and messages.

Customizing Logging Configuration
=================================

AnyVar can load a configuration dictionary from a YAML file for more granular control over logging behavior. To enable customized logging:

1. Create a YAML configuration file (e.g., ``logging.yaml``).
2. Set the environment variable ``ANYVAR_LOGGING_CONFIG`` to point to this file in your ``.env`` file: ::

    ANYVAR_LOGGING_CONFIG="/path/to/logging.yaml"

See the official Python documentation on `configuration dictionary schema <https://docs.python.org/3/library/logging.config.html#configuration-dictionary-schema>`_ for more details.

Applying Logging Configuration
==============================

Note that a service environment (e.g. a Python console, ``uvicorn`` server instance, or Celery worker) must be restarted for configuration changes to take effect.

Example YAML Configuration
==========================

Here's a comprehensive logging configuration example: ::

    version: 1
    disable_existing_loggers: true

    formatters:
      standard:
        format: "%(threadName)s %(asctime)s - %(name)s - %(levelname)s - %(message)s"

    handlers:
      console:
        class: logging.StreamHandler
        level: DEBUG
        formatter: standard
        stream: ext://sys.stdout

      file:
        class: logging.FileHandler
        level: INFO
        formatter: standard
        filename: "anyvar.log"
        mode: "a"

    root:
      level: INFO
      handlers: [console, file]
      propagate: yes

    loggers:
      anyvar.restapi.main:
        level: INFO
        handlers: [console, file]
        propagate: no

      anyvar.storage
        level: DEBUG
        handlers: [console, file]
        propagate: no
