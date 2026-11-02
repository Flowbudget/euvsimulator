Quickstart
==========

Run your first EUV lithography simulation in one command:

.. code-block:: bash

   euv simulate

This runs a default 32 nm line / 32 nm space pattern at NA 0.33 and sigma 0.8 with a
20 mJ/cm² dose, on a 256 × 256 grid, with the thin-mask model and the default
``aerial_threshold`` resist.  ``ler_nm`` and ``lwr_nm`` stay 0 unless ``--stochastic``
is given.  ``--resist-model full_chem`` runs the Dill/PEB/Mack chain instead: it sizes
this pattern at about 1.25 mJ/cm² and clears the line completely at 20 mJ/cm² (CD 0).

Expected output (after the progress line ``[>] Running EUV lithography simulation...``):

.. code-block:: json

   {
     "cd_nm": 27.29,
     "nils": 4.8309,
     "absorber_reflectivity": 0.0112,
     "mask_mean_reflectivity": 0.3717,
     "aerial_max": 18.0329,
     "aerial_shape": [256, 256],
     "ler_nm": 0.0,
     "lwr_nm": 0.0,
     "config": {
       "period_nm": 64.0,
       "line_width_nm": 32.0,
       "dose_mj_cm2": 20.0,
       "na": 0.33,
       "sigma": 0.8
     }
   }

``absorber_reflectivity`` is the intensity reflectivity ``|r|²`` of the 60 nm Ta absorber
on the multilayer at the 6° chief ray; ``mask_mean_reflectivity`` is the line/space area
average of absorber and open multilayer (the open multilayer alone reflects about 65 %).
Until 2026-10 that area average was printed as ``absorber_reflectivity``.

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

   # Full process window: 1 mJ/cm² steps around the dose-to-size (about 13 mJ/cm²) and a
   # focus scan wider than the depth of focus; coarser scans print a warning instead of
   # a resolved EL/DoF
   euv process-window --period=64 --cd=32 --dose-start=10 --dose-end=19 --dose-steps=10 --focus-start=-150 --focus-end=150

Python API
----------

.. code-block:: python

  from euvsimulator.pipeline import SimulationConfig, run_simulation

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
