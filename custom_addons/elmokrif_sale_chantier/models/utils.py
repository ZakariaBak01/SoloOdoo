from odoo import _
from odoo.exceptions import ValidationError


def chantier_analytic_distribution(chantier):
    """Return the complete analytic allocation for a chantier."""
    if chantier.analytic_account_id:
        return {str(chantier.analytic_account_id.id): 100.0}
    return {}


def validate_chantier_link(chantier, company, partner):
    """Validate the company and customer side of any commercial chantier link."""
    if not chantier:
        return
    if not chantier.is_chantier:
        raise ValidationError(_("Only projects marked as chantiers can be linked."))
    if not company or chantier.company_id != company:
        raise ValidationError(
            _("The chantier and the commercial document must belong to the same company.")
        )
    if chantier.site_partner_id and partner:
        if chantier.site_partner_id.commercial_partner_id != partner.commercial_partner_id:
            raise ValidationError(
                _("The chantier customer must match the commercial document customer.")
            )
