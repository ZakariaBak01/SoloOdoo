# EL MOKRIF Sale Chantier

This Odoo 17 addon links quotations, sales orders, invoices, and invoice lines
to existing `elmokrif_chantier` projects.

It validates company and customer consistency, supports per-line chantier
allocation, propagates the chantier analytic account to invoices, and keeps the
origin on credit-note lines. A linked chantier is initialized only through the
explicit **Initialize Chantier(s)** action; sales confirmation never creates a
project, warehouse, or site location.

Quotation follow-up activities are created once, due after the company-configured
delay (three days by default), and removed on confirmation or cancellation.

## Local Docker startup

From the repository root, run `docker compose up -d --build`. Compose uses
local-development defaults when `.env` is absent; copy `.env.example` and
replace the password before using the stack outside local development.
