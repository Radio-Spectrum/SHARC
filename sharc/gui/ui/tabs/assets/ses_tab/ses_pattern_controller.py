# Constants for Single Earth Station

SUPPORTED_ANTENNA_PATTERNS = [
    "OMNI", "HibleoX", "ITU-R F.699", "ITU-R S.465", "ITU-R S.580",
    "MODIFIED ITU-R S.465", "ITU-R S.1855", "ITU-R Reg. RR. Appendice 7 Annex 3",
    "ARRAY", "ITU-R-S.1528-Taylor", "ITU-R-S.1528-Section1.2",
    "ITU-R-S.1528-LEO", "MSS Adjacent", "ITU-R S.672",
    "ITU-R F.1245_fs", "RA_M2319",
]

# Patterns that require the 'diameter' field input
DIAMETER_PATTERNS = {
    "ITU-R F.699", "ITU-R S.465", "ITU-R S.580",
    "ITU-R S.1855", "ITU-R Reg. RR. Appendice 7 Annex 3"
}

AZ_EL_TYPES = ["UNIFORM_DIST", "FIXED", "POINTING_AT_IMT_CENTER"]
LOC_TYPES = ["FIXED", "CELL", "NETWORK", "UNIFORM_DIST"]
CHANNEL_MODELS = ["FSPL", "P452"]
