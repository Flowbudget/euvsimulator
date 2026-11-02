Installation
============

Requirements
------------

- Python ≥ 3.10
- PyTorch ≥ 2.1
- macOS (tested) or Linux (Debian 12+)

Quick install
-------------

.. code-block:: bash

  # Clone the repository
  git clone https://github.com/Flowbudget/euvsimulator.git
  cd euvsimulator

  # Install in editable mode
  pip install -e .

  # Install dev dependencies (optional)
  pip install -e ".[dev]"

  # Verify
  euv info

CUDA / GPU support
------------------

If you have an NVIDIA GPU, install PyTorch with CUDA support:

.. code-block:: bash

   pip install torch --index-url https://download.pytorch.org/whl/cu121

Docker
------

``Dockerfile`` builds the REST API and browser GUI (port 8000), ``Dockerfile.cli``
the ``euv`` command line.  Both install CPU-only PyTorch.

.. code-block:: bash

   docker compose up --build                     # API on http://127.0.0.1:8000
   docker compose -f docker-compose.cli.yml run --rm cli euv simulate

The API has no authentication, so ``docker-compose.yml`` publishes the port on the
host's loopback interface only (see ``SECURITY.md``).

On arm64 hosts (Apple Silicon, Raspberry Pi) pip has to build gdstk from source,
because gdstk publishes Linux wheels for x86_64 only, and ``python:3.11-slim`` has
no C++ compiler.  Build the amd64 images under emulation instead (Docker Desktop
emulates amd64; on a plain Linux host register QEMU binfmt first):

.. code-block:: bash

   DOCKER_DEFAULT_PLATFORM=linux/amd64 docker compose up --build
