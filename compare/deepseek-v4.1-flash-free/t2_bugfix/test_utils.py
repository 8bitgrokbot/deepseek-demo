import unittest
from utils import moving_average, add_tag, parse_duration, percent_change, chunk


class TestUtils(unittest.TestCase):
    def test_moving_average_basic(self):
        self.assertEqual(moving_average([1, 2, 3, 4], 2), [1.5, 2.5, 3.5])

    def test_moving_average_full_window(self):
        self.assertEqual(moving_average([2, 4, 6], 3), [4.0])

    def test_moving_average_too_big(self):
        self.assertEqual(moving_average([1, 2], 5), [])

    def test_moving_average_invalid(self):
        with self.assertRaises(ValueError):
            moving_average([1, 2, 3], 0)

    def test_add_tag_with_tags(self):
        self.assertEqual(add_tag(["a"], ["b"]), ["a", "b"])

    def test_add_tag_does_not_mutate_input(self):
        base = ["a"]
        add_tag(base, ["b"])
        self.assertEqual(base, ["a"])

    def test_add_tag_default_is_stateless(self):
        first = add_tag(["a"])
        first.append("zzz")
        self.assertEqual(add_tag(["a"]), ["a"])

    def test_parse_duration(self):
        self.assertEqual(parse_duration("1h30m"), 5400)
        self.assertEqual(parse_duration("45s"), 45)
        self.assertEqual(parse_duration("2h5m10s"), 7510)
        self.assertEqual(parse_duration("10m"), 600)

    def test_parse_duration_invalid(self):
        for bad in ["", "90", "5x", "1h 30m"]:
            with self.assertRaises(ValueError):
                parse_duration(bad)

    def test_percent_change(self):
        self.assertEqual(percent_change(200, 250), 25.0)
        self.assertEqual(percent_change(80, 60), -25.0)
        self.assertIsNone(percent_change(0, 5))

    def test_chunk(self):
        self.assertEqual(chunk([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])
        self.assertEqual(chunk([], 3), [])
        with self.assertRaises(ValueError):
            chunk([1], 0)


if __name__ == "__main__":
    unittest.main()
