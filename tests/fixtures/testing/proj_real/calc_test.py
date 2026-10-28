import unittest

from calc import classify, net


class CalcTest(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(classify(2), "big")
        self.assertEqual(classify(1), "small")
        self.assertEqual(classify(0), "small")

    def test_net(self):
        self.assertEqual(net(5, 3), 2)
        self.assertEqual(net(0, 4), -4)


if __name__ == "__main__":
    unittest.main()
