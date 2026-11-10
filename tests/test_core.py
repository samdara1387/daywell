"""Checks for the standalone validation rules in the first Daywell stage."""

import unittest

from core import APIError, date, money, validate


class CoreRulesTests(unittest.TestCase):
    def test_transaction_is_ready_to_store(self):
        item = validate('transactions', {
            'date': '2026-11-10',
            'type': 'expense',
            'amount': 1299,
            'category': 'Food',
            'note': 'Lunch',
        })
        self.assertEqual(item['amount'], 1299)
        self.assertEqual(item['date'], '2026-11-10')
        self.assertTrue(item['id'])

    def test_invalid_calendar_date_is_rejected(self):
        with self.assertRaises(APIError):
            date('2026-02-30')

    def test_money_requires_whole_cents(self):
        with self.assertRaises(APIError):
            money(12.99)

    def test_negative_expense_is_rejected(self):
        with self.assertRaises(APIError):
            validate('transactions', {
                'date': '2026-11-10',
                'type': 'expense',
                'amount': -500,
                'category': 'Food',
            })


if __name__ == '__main__':
    unittest.main()
