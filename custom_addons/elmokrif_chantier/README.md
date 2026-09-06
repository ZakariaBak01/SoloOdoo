# EL MOKRIF Chantier

This Odoo 17 addon extends Projects so one project can be managed as a chantier.

## Delivered in phase 1

- chantier reference and business lifecycle;
- primary work type, region and site address;
- selected supplying warehouse;
- idempotent creation of the native analytic account and one internal site location;
- company and one-to-one relationship constraints;
- manager and user roles;
- closure checks for open tasks and remaining site stock;
- task-level work type;
- form, list and search view extensions.

## Installation

1. Start or refresh Odoo and PostgreSQL with `docker compose up -d --build`.
2. Enable developer mode and select **Update Apps List**.
3. Remove the default Apps filter and search for **EL MOKRIF Chantier**.
4. Install the addon.
5. Assign the **Chantier User** or **Chantier Manager** group to the relevant users.

The Docker image copies `custom_addons` to `/opt/elmokrif-addons` during its build. Rebuild the image after changing addon code.
