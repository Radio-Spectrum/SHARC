"""
---
"""

HAS_TOPO = True
try:
    from sharc.topology.topology_countries import TopologyCountries, ParametersCountries
    from sharc.support.sharc_geom_countries import GeometryConverter
except Exception:
    HAS_TOPO = False
    TopologyCountries = None
    ParametersCountries = None
    GeometryConverter = None