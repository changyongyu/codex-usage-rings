import unittest
from decimal import Decimal

from codex_usage import parse_rate_limits


class MonthlyAllowanceTests(unittest.TestCase):
    def test_monthly_only_account_keeps_decimal_precision(self):
        snapshot = parse_rate_limits({'rateLimits': {'individualLimit': {
            'limit': '5000', 'used': '1509.9337464571', 'resetsAt': 1793491200}}})
        self.assertEqual(snapshot.monthly.remaining, Decimal('3490.0662535429'))
        self.assertEqual(snapshot.monthly.resets_at, 1793491200)
        self.assertIsNone(snapshot.primary)

    def test_exhausted_and_over_limit_accounts_have_zero_remaining(self):
        for used in ['5000', '5100']:
            with self.subTest(used=used):
                snapshot = parse_rate_limits({'rateLimits': {'individualLimit': {'limit': '5000', 'used': used}}})
                self.assertEqual(snapshot.monthly.remaining, 0)

    def test_unavailable_monthly_data_is_not_an_exhausted_allowance(self):
        for value in [None, {}, {'limit': '0', 'used': '0'}, {'limit': 'NaN', 'used': '0'}]:
            with self.subTest(value=value):
                snapshot = parse_rate_limits({'rateLimits': {'primary': {'usedPercent': 25}, 'individualLimit': value}})
                self.assertIsNone(snapshot.monthly)
                self.assertEqual(snapshot.primary.remaining_percent, 75)

    def test_codex_bucket_wins_over_legacy_and_other_buckets(self):
        snapshot = parse_rate_limits({'rateLimits': {'primary': {'usedPercent': 99}}, 'rateLimitsByLimitId': {
            'other': {'primary': {'usedPercent': 88}},
            'codex': {'primary': {'usedPercent': 12}, 'individualLimit': {'limit': '5000', 'used': '1000'}}}})
        self.assertEqual(snapshot.primary.remaining_percent, 88)
        self.assertEqual(snapshot.monthly.remaining, 4000)


if __name__ == '__main__':
    unittest.main()
