GA4GH Service-Info Configuration
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

The :ref:`service-info API endpoint <get_service_info>` values can be defined via an external YAML file referenced through an environment variable. If this variable is not set, AnyVar falls back to its built-in defaults.

It is strongly recommended to provide explicit service-info metadata in
production environments.

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Environment Variable
     - Default Value
   * - ``ANYVAR_SERVICE_INFO``
     - n/a

Example service-info YAML file
==============================

The following example shows the required and optional fields that may appear in a service-info definition file:

.. literalinclude:: ../../../.service_info_example.yaml
