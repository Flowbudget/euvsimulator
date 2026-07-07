.. OpEnUV documentation master file

Welcome to OpEnUV — Open Source EUV Lithography Simulator
===========================================================

OpEnUV is a GPU-accelerated, modular simulator for extreme ultraviolet (EUV)
lithography at 13.5 nm.  It is released under the Apache-2.0 license.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   overview
   install
   quickstart

Tutorials
---------

Runnable Jupyter notebooks live in ``docs/tutorials/``:

* ``basic_simulation.ipynb`` — end-to-end 32 nm line/space simulation
* ``process_window.ipynb`` — dose-focus Bossung plot and process window
* ``materials.ipynb`` — querying the CXRO material database

Launch them with ``jupyter lab docs/tutorials/``.

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/modules

.. toctree::
   :maxdepth: 2
   :caption: Developer Guide

   architecture
   contributing
   license

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
