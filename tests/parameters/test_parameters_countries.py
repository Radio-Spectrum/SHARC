# -*- coding: utf-8 -*-
"""
Tests for sharc.parameters.imt.parameters_countries_imt module.
"""

import unittest
from sharc.parameters.imt.parameters_countries_imt import ParametersCountries


class TestParametersCountries(unittest.TestCase):
    """Tests for ParametersCountries dataclass validation."""

    def _make_valid(self):
        """Create a valid ParametersCountries instance (no file paths checked)."""
        return ParametersCountries(
            country_names=["Brazil", "Argentina"],
            num_bs_total=100,
            cell_radius=400.0,
            sector_half_bw_deg=60.0,
            countries_shapefile=None,
            population_raster=None,
            bs_per_country=None,
        )

    def test_default_values(self):
        """Instantiation with defaults should set expected field values."""
        p = ParametersCountries()
        self.assertIsInstance(p.country_names, list)
        self.assertGreater(len(p.country_names), 0)
        self.assertGreater(p.cell_radius, 0)

    def test_validate_valid_config(self):
        """Valid config should pass validation without error."""
        p = self._make_valid()
        try:
            p.validate("test")
        except ValueError:
            self.fail("validate() raised ValueError on valid config")

    def test_validate_empty_countries(self):
        """Empty country_names should raise ValueError."""
        p = self._make_valid()
        p.country_names = []
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_negative_cell_radius(self):
        """Negative cell_radius should raise ValueError."""
        p = self._make_valid()
        p.cell_radius = -100
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_zero_cell_radius(self):
        """Zero cell_radius should raise ValueError."""
        p = self._make_valid()
        p.cell_radius = 0
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_invalid_sector_half_bw(self):
        """sector_half_bw_deg > 180 should raise ValueError."""
        p = self._make_valid()
        p.sector_half_bw_deg = 200
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_zero_sector_half_bw(self):
        """sector_half_bw_deg = 0 should raise ValueError."""
        p = self._make_valid()
        p.sector_half_bw_deg = 0
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_invalid_dist_type(self):
        """Invalid dist_type should raise ValueError."""
        p = self._make_valid()
        p.dist_type = "InvalidType"
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_valid_dist_type_urban(self):
        """Valid dist_type 'Urban' should pass validation."""
        p = self._make_valid()
        p.dist_type = "Urban"
        try:
            p.validate("test")
        except ValueError:
            self.fail("validate() raised ValueError on valid Urban dist_type")

    def test_validate_bs_per_country_unknown_country(self):
        """bs_per_country with unknown country should raise ValueError."""
        p = self._make_valid()
        p.bs_per_country = {"Brazil": 50, "UnknownCountry": 50}
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_bs_per_country_negative_value(self):
        """bs_per_country with negative value should raise ValueError."""
        p = self._make_valid()
        p.bs_per_country = {"Brazil": -10}
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_num_bs_total_zero(self):
        """num_bs_total = 0 (with no bs_per_country) should raise ValueError."""
        p = self._make_valid()
        p.num_bs_total = 0
        with self.assertRaises(ValueError):
            p.validate("test")


if __name__ == "__main__":
    unittest.main()
