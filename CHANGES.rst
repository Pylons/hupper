1.3 (2018-05-21)
================

- Added watchman support via ``hupper.watchman.WatchmanFileMonitor``.
  This is the new preferred file monitor on systems supporting unix sockets.
  See https://github.com/Pylons/hupper/pull/32

- The ``hupper.watchdog.WatchdogFileMonitor`` will now output some info
  when it receives ulimit or other errors from ``watchdog``.
  See https://github.com/Pylons/hupper/pull/33

- Allow ``-q`` and ``-v`` cli options to control verbosity.
  See https://github.com/Pylons/hupper/pull/33

- Pass a ``logger`` value to the ``hupper.interfaces.IFileMonitorFactory``.
  This is an instance of ``hupper.interfaces.ILogger`` and can be used by
  file monitors to output errors and debug information.
  See https://github.com/Pylons/hupper/pull/33

1.2 (2018-05-01)
================

- Track only Python source files. Previously ``hupper`` would track all pyc
  and py files. Now, if a pyc file is found then the equivalent source file
  is searched and, if found, the pyc file is ignored.
  See https://github.com/Pylons/hupper/pull/31

- Allow overriding the default monitor lookup by specifying the
  ``HUPPER_DEFAULT_MONITOR`` environment variable as a Python dotted-path
  to a monitor factory. For example,
  ``HUPPER_DEFAULT_MONITOR=hupper.polling.PollingFileMonitor``.
  See https://github.com/Pylons/hupper/pull/29

- Backward-incompatible changes to the
  ``hupper.interfaces.IFileMonitorFactory`` API to pass arbitrary kwargs
  to the factory.
  See https://github.com/Pylons/hupper/pull/29

1.1 (2018-03-29)
================

- Support ``-w`` on the CLI to watch custom file paths.
  See https://github.com/Pylons/hupper/pull/28

1.0 (2017-05-18)
================

- Copy ``sys.path`` to the worker process and ensure ``hupper`` is on the
  ``PYTHONPATH`` so that the subprocess can import it to start the worker.
  This fixes an issue with how ``zc.buildout`` injects dependencies into a
  process which is done entirely by ``sys.path`` manipulation.
  See https://github.com/Pylons/hupper/pull/27

0.5 (2017-05-10)
================

- On non-windows systems ensure an exec occurs so that the worker does not
  share the same process space as the reloader causing certain code that
  is imported in both to not ever be reloaded. Under the hood this was a
  significant rewrite to use subprocess instead of multiprocessing.
  See https://github.com/Pylons/hupper/pull/23

0.4.4 (2017-03-10)
==================

- Fix some versions of Windows which were failing to duplicate stdin to
  the subprocess and crashing.
  https://github.com/Pylons/hupper/pull/16

0.4.3 (2017-03-07)
==================

- Fix pdb and other readline-based programs to operate properly.
  See https://github.com/Pylons/hupper/pull/15

0.4.2 (2017-01-24)
==================

- Pause briefly after receiving a SIGINT to allow the worker to kill itself.
  If it does not die then it is terminated.
  See https://github.com/Pylons/hupper/issues/11

- Python 3.6 compatibility.

0.4.1 (2017-01-03)
==================

- Handle errors that may occur when using watchdog to observe non-existent
  folders.

0.4.0 (2017-01-02)
==================

- Support running any Python module via ``hupper -m <module>``. This is
  equivalent to ``python -m`` except will fully reload the process when files
  change. See https://github.com/Pylons/hupper/pull/8

0.3.6 (2016-12-18)
==================

- Read the traceback for unknown files prior to crashing. If an import
  crashes due to a module-scope exception the file that caused the crash would
  not be tracked but this should help.

0.3.5 (2016-12-17)
==================

- Attempt to send imported paths to the monitor process before crashing to
  avoid cases where the master is waiting for changes in files that it never
  started monitoring.

0.3.4 (2016-11-21)
==================

- Add support for globbing using the stdlib ``glob`` module. On Python 3.5+
  this allows recursive globs using ``**``. Prior to this, the globbing is
  more limited.

0.3.3 (2016-11-19)
==================

- Fixed a runtime failure on Windows 32-bit systems.

0.3.2 (2016-11-15)
==================

- Support triggering reloads via SIGHUP when hupper detected a crash and is
  waiting for a file to change.

- Setup the reloader proxy prior to importing the worker's module. This
  should allow some work to be done at module-scope instead of in the
  callable.

0.3.1 (2016-11-06)
==================

- Fix package long description on PyPI.

- Ensure that the stdin file handle is inheritable incase the "spawn" variant
  of multiprocessing is enabled.

0.3 (2016-11-06)
================

- Disable bytecode compiling of files imported by the worker process. This
  should not be necessary when developing and it was causing the process to
  restart twice on Windows due to how it handles pyc timestamps.

- Fix hupper's support for forwarding stdin to the worker processes on
  Python < 3.5 on Windows.

- Fix some possible file descriptor leakage.

- Simplify the ``hupper.interfaces.IFileMonitor`` interface by internalizing
  some of the hupper-specific integrations. They can now focus on just
  looking for changes.

- Add the ``hupper.interfaces.IFileMonitorFactory`` interface to improve
  the documentation for the ``callback`` argument required by
  ``hupper.interfaces.IFileMonitor``.

0.2 (2016-10-26)
================

- Windows support!

- Added support for `watchdog <https://pypi.org/project/watchdog/>`_ if it's
  installed to do inotify-style file monitoring. This is an optional dependency
  and ``hupper`` will fallback to using polling if it's not available.

0.1 (2016-10-21)
================

- Initial release.
