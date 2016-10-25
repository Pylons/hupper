==================
:mod:`hupper` API
==================

.. automodule:: hupper

  .. autofunction:: start_reloader

  .. autofunction:: is_active

  .. autofunction:: get_reloader

  .. autoclass:: Reloader
    :members:

  .. autofunction: is_watchdog_supported

.. automodule:: hupper.interfaces

  .. autoclass:: IReloaderProxy
    :members:

  .. autoclass:: IFileMonitor
    :members:

.. automodule:: hupper.polling

  .. autoclass:: PollingFileMonitor

.. automodule:: hupper.watchdog

  .. autoclass:: WatchdogFileMonitor
