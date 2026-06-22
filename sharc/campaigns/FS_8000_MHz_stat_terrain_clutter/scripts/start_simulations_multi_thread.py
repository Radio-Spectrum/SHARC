"""
Start the FS 8000 MHz / Campinas-SP simulation (ITU-R P.1812 with statistical
terrain and statistical clutter-over-terrain) in multi-threaded mode.

Runs every parameter file found under
``sharc/campaigns/FS_8000_MHz_stat_terrain_clutter/input/``.
"""
from sharc.run_multiple_campaigns_mut_thread import run_campaign

# Name of the campaign directory under sharc/campaigns/
name_campaign = "FS_8000_MHz_stat_terrain_clutter"

# Run the campaign in multi-thread mode
run_campaign(name_campaign)
