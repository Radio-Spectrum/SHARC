from sharc.run_multiple_campaigns import run_campaign_re

# Set the campaign name
# The name of the campaign to run. This should match the name of the campaign directory.
name_campaign = "imt_ntn_to_imt_tn_co_channel"

# Run the campaign in single-thread mode
# This function will execute the campaign with the given name in a single-threaded manner.
# It will look for the campaign directory under the specified name and start the necessary processes.
run_campaign_re(name_campaign, r'^parameters_imt_ntn_to_imt_tn_no_overlap_.*_alt_500km_sep_0km.yaml')
