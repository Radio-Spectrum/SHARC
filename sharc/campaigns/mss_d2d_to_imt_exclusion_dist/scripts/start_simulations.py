from sharc.run_multiple_campaigns_mut_thread import run_campaign_re
import argparse
import subprocess

# Set the campaign name
# The name of the campaign to run. This should match the name of the campaign directory.
name_campaign = "mss_d2d_to_imt_exclusion_dist"


regex_pattern = r'^parameters_mss_d2d_to_imt_excl_angle_.*_km_(dl|ul).yaml'
# Run the campaign with the updated regex pattern
print("Executing campaign with regex pattern:", regex_pattern)
run_campaign_re(name_campaign, regex_pattern)