from sharc.run_multiple_campaigns import run_campaign_re

# Set the campaign name
# The name of the campaign to run. This should match the name of the campaign directory.
name_campaign = "mss_d2d_to_imt_elev_study"

# Run the campaign in single-thread mode
# This function will execute the campaign with the given name in a single-threaded manner.
# It will look for the campaign directory under the specified name and start the necessary processes.
run_campaign_re(name_campaign, r'^mss_d2d_to_imt_co_channel_system_A_min_25_max_30.yaml')
