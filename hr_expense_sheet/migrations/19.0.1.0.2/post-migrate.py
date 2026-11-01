from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Recompute Amount Due of reports with journal entries: it was summed once
    per expense line instead of once per entry."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    sheets = env["hr.expense.sheet"].search([("expense_line_ids.account_move_id", "!=", False)])
    env.add_to_compute(sheets._fields["amount_residual"], sheets)
    sheets.flush_recordset(["amount_residual"])
