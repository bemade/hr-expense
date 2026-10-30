"""Expense report form: the footer Total is read-only.

Acceptance criteria:
- In the ``hr.expense.sheet`` form view, the ``total_amount`` field shown in the
  ``expense_total`` footer group is read-only, so the web client renders it as
  plain text (no editable input whose currency overlay would overlap the
  amount in the right-aligned subtotal footer).
"""

from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestSheetFormTotal(TransactionCase):
    def test_footer_total_amount_is_readonly(self):
        views = self.env["hr.expense.sheet"].get_views([(False, "form")])
        arch = etree.fromstring(views["views"]["form"]["arch"])
        nodes = arch.xpath(
            "//group[@name='expense_total']//field[@name='total_amount']"
        )
        self.assertEqual(len(nodes), 1, "Footer Total field not found in the form")
        self.assertIn(
            nodes[0].get("readonly"),
            ("1", "True", "true"),
            "The footer Total must be read-only",
        )
