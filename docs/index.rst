======
hupper
======

``hupper`` is a loader interface around arbitrary config file formats. It
exists to define a common API for applications to use when they wish to load
configuration settings. The library itself does not aim to handle anything
except a basic API that applications may use to find and load configuration
settings. Any specific constraints should be implemented in a pluggable loader
which can be registered via an entrypoint.

Installation
============

Stable release
--------------

To install hupper, run this command in your terminal:

.. code-block:: console

    $ pip install hupper

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.

.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/


From sources
------------

The sources for hupper can be downloaded from the `Github repo`_.

.. code-block:: console

    $ git clone https://github.com/Pylons/hupper.git

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ pip install -e .

.. _Github repo: https://github.com/Pylons/hupper

Usage
=====

The reloading mechanism is implemented by forking worker processes from a
parent monitor. Start by defining an entry point for your process. This must
be an importable path in string format. For example,
``myapp.scripts.serve.main``:

.. code-block:: python

    # myapp/scripts/serve.py

    import os
    import sys
    import hupper
    import waitress

    def wsgi_app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain'])
        yield [b'hello']

    def main(args=sys.argv[1:]):
        if '--reload' in args:
            # start_reloader will only return in a monitored subprocess
            reloader = hupper.start_reloader('myapp.scripts.serve.main')

            # monitor an extra file
            reloader.watch_files(['foo.ini'])

        waitress.serve(wsgi_app)

Many applications will tend to re-use the same startup code for both the
monitor and the worker. As a convenience to support this use case, the
:func:`hupper.start_reloader` function can be invoked both from the parent
process as well as the worker. When called initially from the parent process,
it will fork a new worker, then start the monitor and never return. When
called from the worker process it will return a proxy object that can be used
to communicate back to the monitor.

Checking if the reloader is active
----------------------------------

:func:`hupper.is_active` will return ``True`` if the reloader is active and
the current process may be reloaded.

Controlling the monitor
-----------------------

The worker processes may communicate back to the monitor and notify it of
new files to watch. This can be done by acquiring a reference to the
:class:`hupper.IReloaderProxy` instance living in the worker process.
The :func:`hupper.start_reloader` function will return the instance or
:func:`hupper.get_reloader` can be used as well.

More Information
================

.. toctree::
   :maxdepth: 1

   api
   contributing
   changes

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
