# -*- coding: utf-8 -*-
import unittest
import numpy as np
from sharc.topology.topology_ue_countries import TopologyUECountries, ParametersUECountries
from sharc.topology.topology_countries import TopologyCountries
from sharc.parameters.imt.parameters_countries_imt import ParametersCountries
from sharc.support.sharc_geom import CoordinateSystem


class TestTopologyUECountries(unittest.TestCase):
    """Unit tests for TopologyUECountries."""

    def test_calculate_coordinates(self):
        """Test coordinate calculation for UEs distributed by country."""
        # Create a mock/simplified TopologyCountries
        params_bs = ParametersCountries(
            country_names=["Brazil"],
            num_bs_total=3,
            cell_radius=400.0,
        )
        cs = CoordinateSystem()
        cs.set_reference(-15.0, -47.0, 1000.0)

        # Instantiate and mock the coordinates instead of loading a shapefile
        bs_topo = TopologyCountries(params_bs, cs)
        bs_topo.num_base_stations = 3
        bs_topo.cell_radius = 400.0
        bs_topo.lats = np.array([-15.0, -15.1, -14.9])
        bs_topo.lons = np.array([-47.0, -47.1, -46.9])
        bs_topo.height = np.array([18.0, 18.0, 18.0])
        bs_topo.azimuth = np.array([0.0, 120.0, -120.0])

        # Calculate ECEF coordinates for BS
        from sharc.satellite.utils.sat_utils import lla2ecef
        x, y, z = lla2ecef(bs_topo.lats, bs_topo.lons, bs_topo.height)
        bs_topo.x = x
        bs_topo.y = y
        bs_topo.z = z

        # Create UE topology parameters
        ue_params = ParametersUECountries(
            num_ue_per_bs=5,
            sector_half_bw_deg=60.0,
            min_dist_from_bs=10.0,
            ue_height_m=1.5,
        )

        ue_topo = TopologyUECountries(bs_topo, ue_params, np.random.RandomState(42))
        ue_topo.calculate_coordinates()

        # Verify sizes
        self.assertEqual(ue_topo.num_base_stations, 15)
        self.assertEqual(len(ue_topo.x), 15)
        self.assertEqual(len(ue_topo.y), 15)
        self.assertEqual(len(ue_topo.z), 15)
        self.assertEqual(len(ue_topo.latitude), 15)
        self.assertEqual(len(ue_topo.longitude), 15)

        # Verify distance from BS is within [min_dist_from_bs, cell_radius]
        for i in range(3):
            bs_x, bs_y, bs_z = bs_topo.x[i], bs_topo.y[i], bs_topo.z[i]
            for k in range(5):
                idx = i * 5 + k
                ue_x, ue_y, ue_z = ue_topo.x[idx], ue_topo.y[idx], ue_topo.z[idx]
                dist = np.sqrt((ue_x - bs_x)**2 + (ue_y - bs_y)**2 + (ue_z - bs_z)**2)
                # The distance should be approximately in [10, 400]
                # (since UE height is 1.5 and BS height is 18, the vertical offset is 16.5m)
                # Let's verify 3D distance is within [10, 401]
                self.assertTrue(9.9 <= dist <= 401.0, f"Distance {dist} out of bounds: {dist}")


if __name__ == "__main__":
    unittest.main()
