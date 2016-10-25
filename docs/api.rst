==================
:mod:`hupper` API
==================

.. automodule:: hupper

  .. autofunction:: start_reloader

  .. autofunction:: is_active

  .. autofunction:: get_reloader

  .. autofunction:: is_watchdog_supported

.. automodule:: hupper.reloader

  .. autoclass:: Reloader
    :members:

.. automodule:: hupper.interfaces

  .. autoclass:: IReloaderProxy
    :members:

  .. autoclass:: IFileMonitor
    :members:

.. automodule:: hupper.polling

  .. autoclass:: PollingFileMonitor

.. automodule:: hupper.watchdog

  .. autoclass:: WatchdogFileMonitor
