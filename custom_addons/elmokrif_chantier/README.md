# EL MOKRIF Chantier

This Odoo 17 addon extends Projects so one project can be managed as a chantier.

## Delivered in phase 1

- chantier reference and business lifecycle;
- primary work type, region and site address;
- customer, chantier manager, planned dates and selected supplying warehouse;
- approval requires a complete customer, planning, classification and site dossier;
- automatic, idempotent creation of an account in the dedicated **Chantiers**
  analytic plan and one internal site location after approval;
- company and one-to-one relationship constraints;
- assigned-project manager and user roles;
- closure checks for open tasks and remaining site stock;
- reopening audit and archive-instead-of-delete history;
- task-level work type;
- form, list and search view extensions.

## Installation

1. Start or refresh Odoo and PostgreSQL with `docker compose up -d --build`.
2. Enable developer mode and select **Update Apps List**.
3. Remove the default Apps filter and search for **EL MOKRIF Chantier**.
4. Install the addon.
5. Assign the **Chantier User** or **Chantier Manager** group to the relevant users.

## Chantier setup workflow

Create the chantier and complete its customer, chantier manager, planned dates,
region, primary work type, site address and supplying warehouse. Selecting
**Approve and Initialize** creates its analytic account and dedicated site stock
location in the same transaction. The separate **Initialize Chantier** action is
an idempotent recovery tool for approved imported or partially initialized records.

Assign a user as the native Project Manager or add them to the project's Members
before they work with the chantier. Chantier Users can run operational lifecycle
actions on assigned sites. Chantier Managers create, approve, reopen, close and
archive them.

## Materials add-on

Install **EL MOKRIF Chantier Materials** after this module. It adds a material-request
approval flow and creates internal transfers from the chantier's supplying warehouse to its
dedicated site location. Material operations on the chantier can record consumption, returns,
and missing materials; material cost is calculated from completed consumption and missing
operations using each product's current cost.

The Docker image copies `custom_addons` to `/opt/elmokrif-addons` during its build. Rebuild the image after changing addon code.

## Upgrading existing chantiers

Version 17.0.1.2.0 includes an Odoo upgrade script that moves legacy site locations
from beneath warehouse **Stock** to the warehouse root. It first releases affected
warehouse-transfer reservations and then reassigns them, so site A inventory can no
longer reserve a delivery intended for site B. Update the module in a maintenance
window and review transfers left waiting for central warehouse stock.

Version 17.0.1.3.0 adds the dedicated **Chantiers** analytic plan, moves existing
unshared chantier accounts into it, repairs reciprocal site-location links and
initializes missing resources for already approved chantiers. An account shared by
multiple projects must be separated before the upgrade can complete.
