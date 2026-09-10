from odoo import _, api, models
from odoo.exceptions import AccessError


SENSITIVE_HR_MODELS = {"hr.employee", "hr.contract", "hr.applicant"}


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _is_hr_officer(self):
        return self.env.su or self.env.user.has_group(
            "elmokrif_hr_extension.group_hr_officer"
        )

    def _sensitive_hr_attachments(self, values=None):
        attachments = self.sudo().filtered(
            lambda attachment: attachment.res_model in SENSITIVE_HR_MODELS
            and attachment.res_id
        )
        if values and values.get("res_model") in SENSITIVE_HR_MODELS and values.get("res_id"):
            attachments |= self.browse()
        return attachments

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if values.get("res_model") in SENSITIVE_HR_MODELS and values.get("res_id"):
                if not self._is_hr_officer():
                    raise AccessError(_("Only HR officers can attach confidential HR files."))
                if values.get("public") or values.get("access_token"):
                    raise AccessError(_("Confidential HR files cannot be shared publicly."))
        return super().create(values_list)

    def write(self, values):
        sensitive = self._sensitive_hr_attachments(values)
        becoming_sensitive = values.get("res_model") in SENSITIVE_HR_MODELS and values.get("res_id")
        if sensitive or becoming_sensitive:
            if not self._is_hr_officer():
                raise AccessError(_("Only HR officers can change confidential HR files."))
            if values.get("public") or values.get("access_token"):
                raise AccessError(_("Confidential HR files cannot be shared publicly."))
        return super().write(values)

    def check(self, mode, values=None):
        result = super().check(mode, values=values)
        if self.env.is_superuser() or not self._sensitive_hr_attachments(values):
            return result
        if not self._is_hr_officer():
            raise AccessError(_("You are not allowed to access confidential HR files."))
        return result
