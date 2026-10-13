# -*- coding: utf-8 -*-
"""Single earth station at a geographic location (FIXED_GEO) and its pointing."""
import unittest

import numpy as np
import numpy.testing as npt

from sharc.parameters.parameters_single_earth_station import ParametersSingleEarthStation
from sharc.station_factory import StationFactory
from sharc.support.geometry import ENUReferenceFrame, SimulatorGeometry
from sharc.support.sharc_geom import CoordinateSystem

REF_LAT, REF_LON, REF_ALT = -3.77, -38.55, 30.0


def make_param(lat, lon, altitude=30.0, height=15.0, azimuth=None, elevation=None):
    """Earth-station parameters with a FIXED_GEO location."""
    param = ParametersSingleEarthStation()
    param.antenna.pattern = "OMNI"
    param.antenna.gain = 0.0
    param.bandwidth = 10.0
    param.frequency = 4895.0
    param.tx_power_density = -200.0
    param.noise_temperature = 50.0
    geometry = param.geometry
    geometry.height = height
    geometry.location.type = "FIXED_GEO"
    geometry.location.fixed_geo.latitude = lat
    geometry.location.fixed_geo.longitude = lon
    geometry.location.fixed_geo.altitude = altitude
    geometry.azimuth.type, geometry.azimuth.fixed = azimuth or ("FIXED", 0.0)
    geometry.elevation.type, geometry.elevation.fixed = elevation or ("FIXED", 0.0)
    return param


class SingleEarthStationGeoTest(unittest.TestCase):
    """FIXED_GEO location and POINTING_AT_IMT_CENTER."""

    def setUp(self):
        """Simulator reference point."""
        self.cs = CoordinateSystem()
        self.cs.set_reference(REF_LAT, REF_LON, REF_ALT)
        self.rng = np.random.RandomState(1)

    def generate(self, param):
        """Generate the station with the reference point."""
        return StationFactory.generate_single_earth_station(
            param, self.rng, coordinate_system=self.cs,
        )

    def point(self, lat, lon, alt):
        """Global position of a geographic point, as a geometry."""
        geom = SimulatorGeometry(
            1, uses_local_coords=True, global_cs=ENUReferenceFrame.from_coordinate_system(self.cs),
        )
        geom.set_local_reference_frame(ENUReferenceFrame(lat=[lat], lon=[lon], alt=[alt]))
        geom.set_local_coords(np.zeros(1), np.zeros(1), np.zeros(1))
        return geom

    def test_position_is_ground_plus_height(self):
        """The antenna is geometry.height above the site's ground altitude."""
        es = self.generate(make_param(-3.8735, -38.42216, altitude=30.0, height=15.0))
        npt.assert_allclose(es.geom.z_local, 15.0)
        expected = self.point(-3.8735, -38.42216, 45.0)
        npt.assert_allclose(es.geom.get_3d_distance_to(expected), 0.0, atol=1e-6)

    def test_pointing_at_imt_center(self):
        """An antenna north of the center points south (azimuth -90 deg)."""
        param = make_param(REF_LAT + 0.1, REF_LON, altitude=REF_ALT, height=0.0,
                           azimuth=("POINTING_AT_IMT_CENTER", None),
                           elevation=("POINTING_AT_IMT_CENTER", None))
        es = self.generate(param)
        npt.assert_allclose(es.geom.pointn_azim_local, -90.0, atol=1e-6)
        # 11 km away on a curved Earth: the center is slightly below the horizon
        self.assertLess(es.geom.pointn_elev_local[0], 0.0)
        self.assertGreater(es.geom.pointn_elev_local[0], -0.2)
        # the antenna boresight goes through the center
        center = SimulatorGeometry(1)
        center.set_global_coords(np.zeros(1), np.zeros(1), np.zeros(1))
        npt.assert_allclose(es.geom.get_off_axis_angle(center), 0.0, atol=1e-6)

    def test_fixed_pointing_is_local(self):
        """Fixed azimuth/elevation are given in the station's own frame."""
        param = make_param(-10.0, -50.0, azimuth=("FIXED", 30.0), elevation=("FIXED", 10.0))
        es = self.generate(param)
        npt.assert_allclose(es.geom.pointn_azim_local, 30.0)
        npt.assert_allclose(es.geom.pointn_elev_local, 10.0)
        # far from the reference point, the global angles differ
        self.assertGreater(abs(es.geom.pointn_azim_global[0] - 30.0), 0.5)

    def test_reference_point_required(self):
        """FIXED_GEO without a simulator reference point is an error."""
        with self.assertRaises(ValueError):
            StationFactory.generate_single_earth_station(make_param(-3.8, -38.4), self.rng)

    def test_validation(self):
        """FIXED_GEO needs a valid latitude and longitude."""
        param = make_param(None, -38.4)
        with self.assertRaises(ValueError):
            param.geometry.location.validate("geometry.location")
        param = make_param(-95.0, -38.4)
        with self.assertRaises(ValueError):
            param.geometry.location.validate("geometry.location")
        make_param(-3.8, -38.4).geometry.location.validate("geometry.location")


if __name__ == "__main__":
    unittest.main()
