"""Checks for Daywell's local spending analysis using fictional records."""

import unittest

from insights import analyze, local_answer, suggestions


def example_state():
    """Keep personal records out of this test and out of GitHub."""
    return {
        'settings': {'currency': 'CAD'},
        'transactions': [
            {'id': 'prior', 'date': '2026-10-29', 'type': 'expense', 'amount': 500, 'category': 'Food & groceries', 'note': 'Prior food'},
            {'id': 'food', 'date': '2026-11-05', 'type': 'expense', 'amount': 1500, 'category': 'Food & groceries', 'note': 'Groceries'},
            {'id': 'pay', 'date': '2026-11-06', 'type': 'income', 'amount': 50000, 'category': 'Pay', 'note': 'Payday'},
            {'id': 'later', 'date': '2026-11-20', 'type': 'expense', 'amount': 4000, 'category': 'Transport', 'note': 'Future fuel'},
        ],
        'budgets': [{'month': '2026-11', 'category': 'Food & groceries', 'amount': 2000}],
    }


class InsightsTests(unittest.TestCase):
    def test_future_expense_is_not_counted_as_spent(self):
        result = analyze(example_state(), '2026-11-01', '2026-11-30', as_of='2026-11-10')
        self.assertEqual(result['expenses'], 1500)
        self.assertEqual(result['income'], 50000)
        self.assertEqual(result['net'], 48500)
        self.assertEqual(result['future']['expenses'], 4000)
        self.assertEqual(result['categories'], [{'label': 'Food & groceries', 'amount': 1500}])
        self.assertEqual(result['budgets'][0]['remaining'], 500)

    def test_answer_labels_cash_flow_without_claiming_bank_balance(self):
        answer = local_answer(example_state(), 'What is my balance?', '2026-11-01', '2026-11-30', as_of='2026-11-10')
        self.assertIn('485.00', answer['reply'])
        self.assertIn('not a verified bank balance', answer['reply'])

    def test_category_suggestion_does_not_change_records(self):
        state = example_state()
        state['transactions'].append({'id': 'coffee', 'date': '2026-11-07', 'type': 'expense', 'amount': 450, 'category': 'Other', 'note': 'Coffee at cafe'})
        result = suggestions(state, '2026-11-01', '2026-11-30')
        self.assertEqual(result['proposals'][0]['suggested'], 'Dining out')
        self.assertEqual(state['transactions'][-1]['category'], 'Other')


if __name__ == '__main__':
    unittest.main()
