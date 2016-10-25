unreleased
==========

- Added support for `watchdog <https://pypi.org/project/watchdog/>`_ if it's
  installed to do inotify-style file monitoring. This is an optional dependency
  and ``hupper`` will fallback to using polling if it's not available.

0.1 (2016-10-21)
================

- Initial release.
