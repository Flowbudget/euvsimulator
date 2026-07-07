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
   git clone https://github.com/Flowbudget/OpEnUV.git
   cd OpEnUV

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

*(Coming soon)*
