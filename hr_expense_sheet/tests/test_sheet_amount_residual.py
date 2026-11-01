"""Expense report Amount Due with several lines on one journal entry.

Acceptance criteria:
- A posted, unpaid expense report with several expenses shows Amount Due equal
  to its journal entry's residual (= its Total), not that residual once per
  expense: all lines of a report share one move, and each expense's
  ``amount_residual`` is the whole move's residual.
"""

from odoo import Command
from odoo.tests import tagged

from .common import TestHrExpenseSheetCommon


@tagged("-at_install", "post_install")
class TestSheetAmountResidual(TestHrExpenseSheetCommon):
    def test_multi_line_report_amount_due_equals_move_residual(self):
        line = {
            "employee_id": self.expense_employee.id,
            "product_id": self.product_c.id,
            "date": self.frozen_today,
            "company_id": self.company_data["company"].id,
            "currency_id": self.company_data["currency"].id,
        }
        sheet = self.create_expense_report(
            {
                "expense_line_ids": [
                    Command.create(
                        {**line, "name": f"Line {i}", "total_amount_currency": amount}
                    )
                    for i, amount in enumerate((100.00, 110.00, 120.00))
                ]
            }
        )
        sheet.action_submit()
        self.assertEqual(sheet.state, "submitted")
        self.assertFalse(sheet.action_approve(), "No duplicate wizard expected")
        self.assertEqual(sheet.state, "approved")
        sheet.action_post()
        self.assertEqual(sheet.state, "posted")
        moves = sheet.expense_line_ids.account_move_id
        self.assertTrue(moves, "Posting must create the journal entry")
        self.assertEqual(len(moves), 1, "All lines must share one journal entry")
        self.assertAlmostEqual(sheet.amount_residual, sum(moves.mapped("amount_residual")))
        self.assertAlmostEqual(sheet.amount_residual, sheet.total_amount)
