from odoo import _
from odoo.exceptions import ValidationError


def chantier_analytic_distribution(chantier, existing_distribution=None):
    """Merge the chantier account without erasing other analytic dimensions."""
    distribution = dict(existing_distribution or {})
    target_account = chantier.analytic_account_id
    if not target_account:
        return distribution

    account_ids = set()
    for key in distribution:
        account_ids.update(
            int(account_id)
            for account_id in str(key).split(",")
            if account_id.isdigit()
        )
    accounts_by_id = {
        account.id: account
        for account in chantier.env["account.analytic.account"].browse(account_ids).exists()
    }

    merged = {}
    for key, percentage in distribution.items():
        preserved_ids = [
            account_id
            for account_id in str(key).split(",")
            if not account_id.isdigit()
            or not accounts_by_id.get(int(account_id))
            or accounts_by_id[int(account_id)].plan_id != target_account.plan_id
        ]
        if preserved_ids:
            merged[",".join(preserved_ids)] = percentage
    merged[str(target_account.id)] = 100.0
    return merged


def validate_chantier_link(chantier, company, partner):
    """Validate the company and customer side of any commercial chantier link."""
    if not chantier:
        return
    # The caller's access to the commercial document is checked separately.
    # Read the stored chantier link as the system so accountants can validate
    # and post invoices without joining the operational chantier team.
    chantier = chantier.sudo()
    if not chantier.is_chantier:
        raise ValidationError(_("Only projects marked as chantiers can be linked."))
    if not company or chantier.company_id != company:
        raise ValidationError(
            _("The chantier and the commercial document must belong to the same company.")
        )
    if chantier.partner_id and partner:
        if chantier.partner_id.commercial_partner_id != partner.commercial_partner_id:
            raise ValidationError(
                _("The chantier customer must match the commercial document customer.")
            )
