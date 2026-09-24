from . import models


def post_init_hook(env):
    env["chantier.finance.readiness"].sudo()._ensure_for_companies()
