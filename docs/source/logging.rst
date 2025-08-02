Logging Configuration
!!!!!!!!!!!!!!!!!!!!!

AnyVar utilizes Python's built-in logging framework to provide detailed and configurable logging capabilities, which are essential for monitoring, debugging, and auditing application activities.

Importance of Logging
=====================

Logging helps:

* Diagnose issues efficiently.
* Monitor application behavior.
* Audit and maintain records of significant events.

Default Logging Behavior
========================

By default, AnyVar logs at the ``INFO`` level to standard output, providing sufficient details for general usage. The default format includes timestamps, log levels, and messages.

Customizing Logging Configuration
=================================

Logging can be customized extensively using YAML configuration files. To enable customized logging:

1. Create a YAML configuration file (e.g., ``logging.yaml``).
2. Set the environment variable ``ANYVAR_LOGGING_CONFIG`` to point to this file in your ``.env`` file: ::

    ANYVAR_LOGGING_CONFIG="/path/to/logging.yaml"

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

      anyvar.storage.sql_storage:
        level: DEBUG
        handlers: [console, file]
        propagate: no

Configuration Breakdown
=======================

* **Formatters:** Define the log message structure.
* **Handlers:** Define where logs are sent (console, file, etc.) and their severity.
* **Root Logger:** Applies settings globally.
* **Specific Loggers:** Allow specific module-level control of logging.

Applying Logging Configuration
==============================

After defining your configuration file and setting the environment variable, restart AnyVar: ::

    uvicorn anyvar.restapi.main:app --reload

Logging changes take effect immediately upon application restart.

Verifying Logging
=================

* Inspect the ``anyvar.log`` file (if file handler is configured).
* Monitor console output.

Troubleshooting Logging
=======================

* **No Logs Generated:** Verify file permissions and paths.
* **Incorrect Log Levels:** Check handler and logger configurations.
* **Environment Variable Issues:** Ensure ``ANYVAR_LOGGING_CONFIG`` correctly points to your YAML file.

## Cheat Sheet: Environment Variables

.. list-table::
   :widths: 20 40 40
   :header-rows: 1

   * - Variable
     - Description
     - Example
   * - ``ANYVAR_LOGGING_CONFIG``
     - Path to custom logging configuration YAML file
     - ``/path/to/logging.yaml``
