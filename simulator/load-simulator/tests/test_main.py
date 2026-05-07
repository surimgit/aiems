from __future__ import annotations

import unittest

from main import build_arg_parser


class MainEntrypointUnitTest(unittest.TestCase):
    def test_build_arg_parser_uses_expected_defaults(self) -> None:
        parser = build_arg_parser()

        args = parser.parse_args([])

        self.assertTrue(args.config.endswith("config\\devices.yaml") or args.config.endswith("config/devices.yaml"))
        self.assertTrue(args.scenario.endswith("config\\scenario.yaml") or args.scenario.endswith("config/scenario.yaml"))
        self.assertIsNone(args.cycles)


if __name__ == "__main__":
    unittest.main()
