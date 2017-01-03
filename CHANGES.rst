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
