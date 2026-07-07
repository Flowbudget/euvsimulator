Quickstart
==========

Run your first EUV lithography simulation in one command:

.. code-block:: bash

   euv simulate

This runs a default 32 nm line / 32 nm space pattern at NA 0.33 with a 20 mJ/cm² dose.

Expected output:

.. code-block:: json

   {
     "cd_nm": 29.50,
     "nils": 0.0000,
     "absorber_reflectivity": 0.0006,
     "aerial_max": 20.0000,
     "aerial_shape": [256, 256]
   }

More examples
-------------

.. code-block:: bash

   # Custom parameters
   euv simulate --period=80 --cd=40 --dose=25 --na=0.33 --sigma=0.6

   # Save results to directory
   euv simulate --period=64 --cd=32 --output=results/my_sim

   # List available materials
   euv materials

   # Query a material refractive index
   euv materials Si --energy=91.84

   # Generate a test mask
   euv make-mask --pitch=64 --cd=32 --out=mask.gds

   # Full process window
   euv process-window --period=64 --cd=32 --dose-start=10 --dose-end=40

Python API
----------

.. code-block:: python

   from euv.pipeline import SimulationConfig, run_simulation

   cfg = SimulationConfig(
       period_nm=64.0,
       line_width_nm=32.0,
       dose_mj_cm2=20.0,
       na=0.33,
       sigma=0.8,
   )
   result = run_simulation(cfg)
   print(f"CD = {result.cd_nm:.2f} nm")
   print(f"NILS = {result.nils_value:.4f}")
