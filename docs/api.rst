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
    :special-members:

  .. autoclass:: IFileMonitor
    :members:
    :special-members:

  .. autoclass:: IFileMonitorFactory
    :members:
    :special-members:

.. automodule:: hupper.polling

  .. autoclass:: PollingFileMonitor
     :members:

.. automodule:: hupper.watchdog

  .. autoclass:: WatchdogFileMonitor
     :members:
