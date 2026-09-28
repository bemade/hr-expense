# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tools import mute_logger

from odoo.addons.hr_expense_sheet.tests.common import TestHrExpenseSheetCommon


# Patch Durpro : comme les autres fichiers de tests du module, ces tests ont
# besoin du registre complet (plan comptable) ; sans ce tag ils tombent en -i.
@tagged("-at_install", "post_install")
class TestHrExpenseSheetApproveDuplicate(TestHrExpenseSheetCommon):
    """hr.expense.sheet.action_approve() used to hand the
    "Validate Duplicate Expenses" wizard back unchanged. Core's wizard only
    knows the duplicate lines it was given (default_expense_ids) and
    approves only those, leaving the rest of the report - and the report
    itself - stuck as "submitted".
    """

    def _create_sheet_with_duplicates(self):
        sheet = self.env["hr.expense.sheet"].create(
            {
                "name": "Sheet with duplicates",
                "employee_id": self.expense_employee.id,
                "company_id": self.company_data["company"].id,
                "expense_line_ids": [
                    Command.create(
                        {
                            "employee_id": self.expense_employee.id,
                            "product_id": self.product_a.id,
                            "total_amount_currency": 4.40,
                            "date": self.frozen_today,
                            "company_id": self.company_data["company"].id,
                            "currency_id": self.company_data["currency"].id,
                        }
                    ),
                    Command.create(
                        {
                            "employee_id": self.expense_employee.id,
                            "product_id": self.product_a.id,
                            "total_amount_currency": 4.40,
                            "date": self.frozen_today,
                            "company_id": self.company_data["company"].id,
                            "currency_id": self.company_data["currency"].id,
                        }
                    ),
                    Command.create(
                        {
                            "employee_id": self.expense_employee.id,
                            "product_id": self.product_c.id,
                            "total_amount_currency": 1000.00,
                            "date": self.frozen_today,
                            "company_id": self.company_data["company"].id,
                            "currency_id": self.company_data["currency"].id,
                        }
                    ),
                ],
            }
        )
        sheet.action_submit()
        return sheet

    def _open_duplicate_wizard(self, sheet, user):
        action = sheet.with_user(user).action_approve()
        self.assertEqual(action["res_model"], "hr.expense.approve.duplicate")
        self.assertEqual(action["context"]["hr_expense_sheet_approve_ids"], sheet.ids)
        return Form(
            self.env["hr.expense.approve.duplicate"]
            .with_user(user)
            .with_context(**action["context"])
        ).save()

    def test_wizard_approve_approves_whole_sheet(self):
        sheet = self._create_sheet_with_duplicates()
        wizard = self._open_duplicate_wizard(sheet, self.expense_user_manager)
        wizard.action_approve()

        for line in sheet.expense_line_ids:
            self.assertEqual(line.state, "approved")
        self.assertEqual(sheet.state, "approved")
        self.assertEqual(sheet.approval_state, "approved")
        self.assertTrue(sheet.approval_date)
        self.assertTrue(sheet.manager_id)
        self.assertFalse(
            sheet.activity_ids.filtered(
                lambda a: a.activity_type_id
                == self.env.ref("hr_expense_sheet.mail_act_expense_approval")
            )
        )

    def test_wizard_refuse_refuses_sheet(self):
        sheet = self._create_sheet_with_duplicates()
        wizard = self._open_duplicate_wizard(sheet, self.expense_user_manager)
        wizard.action_refuse()

        for line in sheet.expense_line_ids:
            self.assertEqual(line.state, "refused")
        self.assertEqual(sheet.state, "refused")

    def test_wizard_cancel_changes_nothing(self):
        sheet = self._create_sheet_with_duplicates()
        self._open_duplicate_wizard(sheet, self.expense_user_manager)

        for line in sheet.expense_line_ids:
            self.assertEqual(line.state, "submitted")
        self.assertEqual(sheet.state, "submitted")
        self.assertFalse(sheet.approval_date)

    def test_mixed_sheet_recovers(self):
        """Replays the sheet 69 data: two duplicate lines got approved
        directly (bypassing the wizard's sheet-wide approval), leaving the
        sheet in a mixed state that the old _compute_state could not
        resolve."""
        sheet = self._create_sheet_with_duplicates()
        dup_lines = sheet.expense_line_ids.filtered(
            lambda e: e.product_id == self.product_a
        )
        dup_lines.with_user(self.expense_user_manager)._do_approve()
        self.assertEqual(sheet.state, "submitted")

        # The only line still "submitted" (product_c) is not itself a
        # duplicate of anything, so re-approving the sheet now goes
        # straight through the direct (non-wizard) path and finishes the
        # report - it must not stay stuck.
        sheet.with_user(self.expense_user_manager).action_approve()

        for line in sheet.expense_line_ids:
            self.assertEqual(line.state, "approved")
        self.assertEqual(sheet.state, "approved")

    def test_wizard_forged_context_checks_rights(self):
        """The employee who owns the report is also, here, a team approver
        elsewhere in the company (so they pass the wizard's own ACL and the
        record rules) but core still refuses to let anyone approve their
        own expense (`_get_cannot_approve_reason`: "It is your own
        expense"). A forged `hr_expense_sheet_approve_ids` context must not
        bypass that - same guard as the direct path's `_check_can_approve`.
        """
        sheet = self._create_sheet_with_duplicates()
        dup_lines = sheet.expense_line_ids.filtered(
            lambda e: e.product_id == self.product_a
        )
        self.expense_user_employee.group_ids = [
            Command.link(self.env.ref("hr_expense.group_hr_expense_team_approver").id)
        ]
        wizard = Form(
            self.env["hr.expense.approve.duplicate"]
            .with_user(self.expense_user_employee)
            .with_context(
                hr_expense_sheet_approve_ids=sheet.ids,
                default_expense_ids=dup_lines.ids,
            )
        ).save()

        with (
            mute_logger("odoo.addons.base.models.ir_rule"),
            self.assertRaises(UserError),
        ):
            wizard.action_approve()

        for line in sheet.expense_line_ids:
            self.assertEqual(line.state, "submitted")

    def test_standalone_duplicates_unchanged(self):
        expenses = self.create_expenses(
            [
                {"product_id": self.product_a.id, "total_amount_currency": 4.40},
                {"product_id": self.product_a.id, "total_amount_currency": 4.40},
            ]
        )
        expenses.action_submit()

        action = expenses.with_user(self.expense_user_manager).action_approve()
        self.assertEqual(action["res_model"], "hr.expense.approve.duplicate")
        self.assertNotIn("hr_expense_sheet_approve_ids", action.get("context", {}))

        wizard = Form(
            self.env["hr.expense.approve.duplicate"]
            .with_user(self.expense_user_manager)
            .with_context(**action["context"])
        ).save()
        wizard.action_approve()

        for expense in expenses:
            self.assertEqual(expense.state, "approved")
