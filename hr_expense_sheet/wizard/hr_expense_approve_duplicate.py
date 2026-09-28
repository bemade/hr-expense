# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).

from odoo import models


class HrExpenseApproveDuplicate(models.TransientModel):
    _inherit = "hr.expense.approve.duplicate"

    # Patch Durpro : le rapport de dépenses (hr.expense.sheet) enveloppe
    # ses lignes soumises dans un seul bouton Approuver/Refuser. Quand core
    # affiche cet assistant pour confirmer des doublons présumés, il ne
    # connaît que les lignes en doublon (default_expense_ids) et n'a
    # aucune idée du rapport auquel elles appartiennent : approuver
    # seulement ces lignes laissait le reste du rapport et le rapport
    # lui-même bloqués en "Soumis". `hr.expense.sheet.action_approve`
    # transmet maintenant les rapports concernés via la clé de contexte
    # `hr_expense_sheet_approve_ids` ; quand elle est présente, on
    # approuve/refuse le rapport en entier plutôt que les seules lignes en
    # doublon. Une dépense autonome (sans rapport) n'a pas cette clé et
    # retombe sur le comportement core (`super()`), inchangé.
    def _get_expense_sheets(self):
        sheet_ids = self.env.context.get("hr_expense_sheet_approve_ids")
        if not sheet_ids:
            return self.env["hr.expense.sheet"]
        sheets = self.env["hr.expense.sheet"].browse(sheet_ids).exists()
        return sheets.filtered(lambda sheet: sheet.state == "submitted")

    def action_approve(self):
        sheets = self._get_expense_sheets()
        if not sheets:
            return super().action_approve()
        lines = sheets.expense_line_ids.filtered(
            lambda expense: expense.state in ("draft", "submitted")
        )
        # Same guard as the direct approval path (hr.expense.action_approve
        # -> _check_can_approve): a forged context must not let a user
        # without approval rights bypass it.
        lines._check_can_approve()
        lines._do_approve()
        sheets._do_approve()
        return {"type": "ir.actions.act_window_close"}

    def action_refuse(self):
        sheets = self._get_expense_sheets()
        if not sheets:
            return super().action_refuse()
        lines = sheets.expense_line_ids
        lines._check_can_refuse()
        lines.filtered(lambda expense: expense.state == "submitted")._do_refuse(
            self.env._("Duplicate Expense")
        )
        return {"type": "ir.actions.act_window_close"}
