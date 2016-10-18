======
hupper
======

.. image:: https://img.shields.io/pypi/v/hupper.svg
    :target: https://pypi.python.org/pypi/hupper

.. image:: https://img.shields.io/travis/Pylons/hupper.svg
    :target: https://travis-ci.org/Pylons/hupper

.. image:: https://readthedocs.org/projects/hupper/badge/?version=latest
    :target: https://readthedocs.org/projects/hupper/?badge=latest
    :alt: Documentation Status

``hupper`` is an integrated process monitor that will track changes to
any imported Python files in ``sys.modules`` as well as custom paths. When
files are changed the process is restarted.

Usage
=====

Start by defining an entry point for your process. This must be an importable
path in string format. For example, ``myapp.scripts.serve.main``.

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
