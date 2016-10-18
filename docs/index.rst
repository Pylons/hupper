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
