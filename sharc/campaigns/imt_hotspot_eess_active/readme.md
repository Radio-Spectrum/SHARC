# IMT Hotspot EESS Active Campaign

This campaign's objective is to try and replicate Luciano's contribution 20.

As such, the `generate_aggregate_cdf.py` and `plot_comparison.py` were made.

After running both uplink and downlink simulations,
you can generate an aggregate cdf based on the TDD and segment factors with `generate_aggregate_cdf.py`. The script also copies samples in the `comparison` folder to the `output` folder as CDF's of System INR.

You can then compare SHARC results against Luciano's results with a simple `plot_results.py`.
