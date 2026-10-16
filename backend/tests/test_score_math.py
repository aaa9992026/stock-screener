import unittest

from app.services.score_math import composite_points


class CompositeRoundingTests(unittest.TestCase):
    def test_captured_half_cent_rankings_round_once(self):
        weights = dict(technical=25, fundamental=30, ownership=15, sector=5, relative_strength=25)
        for symbol, technical, ownership, rs, expected in [
            ('FSLR', 10, 75.55, 58.93, 28.57),
            ('LI', 30, 3.5, 53.8, 21.48),
            ('HUHTAMAKI', 0, 30.5, 43.08, 15.35),
            ('GENCON', 0, 30, 12.94, 7.74),
        ]:
            with self.subTest(symbol=symbol):
                self.assertEqual(composite_points(dict(technical=technical, ownership=ownership,
                    relative_strength=rs, fundamental=None, sector=None), weights), expected)

    def test_missing_zero_and_half_up(self):
        self.assertIsNone(composite_points({'technical': None}, {'technical': 100}))
        self.assertEqual(composite_points({'technical': 0}, {'technical': 100}), 0)
        self.assertEqual(composite_points({'technical': 1.125}, {'technical': 100}), 1.13)
        self.assertEqual(composite_points({'technical': 1e-7}, {'technical': 100}), 0)
