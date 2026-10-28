import unittest


class TheaterTest(unittest.TestCase):
    def test_runs_but_checks_nothing(self):
        result = 1 + 1  # it runs, it checks nothing - pure theater


if __name__ == "__main__":
    unittest.main()
