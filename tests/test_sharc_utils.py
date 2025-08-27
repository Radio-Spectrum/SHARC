import unittest

from sharc.support.sharc_utils import clip_angle


class StationTest(unittest.TestCase):
    """Unit tests for some utilities."""

    def setUp(self):
        """
        setup
        """
        pass

    def test_clip_angle(self):
        """
        Testing in range for non wrapping around angles
        """
        for a in [90, 100, 180, -180, -135.01]:
            self.assertEqual(clip_angle(a, 0, 90), 90)
        for a in [-134.99, -90, -45, 0]:
            self.assertEqual(clip_angle(a, 0, 90), 0)
        for a in [0, 45, 90]:
            self.assertEqual(clip_angle(a, 0, 90), a)

        for a in [-90, -80, 0, 44.99]:
            self.assertEqual(clip_angle(a, -180, -90), -90)
        for a in [45.01, 90, 135, 180, -180]:
            self.assertEqual(clip_angle(a, -180, -90), -180)
        for a in [-180, -135, -90]:
            self.assertEqual(clip_angle(a, -180, -90), a)

        for a in [180, -180, -135, -90.01]:
            self.assertEqual(clip_angle(a, 0, 180), 180)
        for a in [-89.99, -45, 0]:
            self.assertEqual(clip_angle(a, 0, 180), 0)
        for a in [0, 45, 90, 135, 180]:
            self.assertEqual(clip_angle(a, 0, 180), a)

        """
        Testing in range for wrapping around angles
        """
        for a in [-90, -80, 0, 44.99]:
            self.assertEqual(clip_angle(a, 180, -90), -90)
        for a in [45.01, 90, 135, 180, 180]:
            self.assertEqual(clip_angle(a, 180, -90), 180)
        for a in [-180, -135, -90]:
            self.assertEqual(clip_angle(a, 180, -90), a)

        for a in [-180, -135, -90.01]:
            self.assertEqual(clip_angle(a, 0, -180), -180)
        for a in [-89.99, -45, 0]:
            self.assertEqual(clip_angle(a, 0, -180), 0)
        for a in [0, 45, 90, 135, -180]:
            self.assertEqual(clip_angle(a, 0, -180), a)

        self.assertEqual(clip_angle(91, 180, 0), 180)
        self.assertEqual(clip_angle(89, 180, 0), 0)

        self.assertEqual(clip_angle(91, -180, 0), -180)
        self.assertEqual(clip_angle(89, -180, 0), 0)


if __name__ == '__main__':
    unittest.main()
