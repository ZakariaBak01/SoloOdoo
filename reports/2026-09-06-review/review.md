# SoloOdoo review — 6 September 2026

The Chantier foundation is a working prototype, but it is not ready for dependable daily operation yet. Both addons install and their existing tests pass. Additional execution of real stock operations and restricted-user scenarios revealed workflow, permissions and reporting defects that those tests do not cover.

This was a review: addon implementation and the business database were not changed. The only workspace additions are this report and its test evidence.

## Validation performed

- Reviewed both custom addons: models, forms/actions/menus, security, manifests, tests, README, Dockerfile and Compose setup.
- Located Docker outside PATH and used the installed Odoo 17.0-20260817 image with PostgreSQL 15.
- Copied the current local addon files into disposable containers. Tested on a separate temporary database, with a separate internal network and no published web ports. Did not install, upgrade or test against `TestData`.
- Clean installation of both modules succeeded, including Odoo's actual view validation.
- Existing test suite: **11 tests passed, zero failures/errors** (7 foundation, 4 materials).
- Ran 19 additional rollback-only diagnostic scenarios. Five scenarios met all expectations; thirteen demonstrated defects; one documented the existing current-price cost limitation. These were exploratory checks, not additions to the permanent regression suite.
- Tested the consumption form using Odoo's `Form` helper, including onchange, saving and validating. No full browser/visual regression suite was run.
- `git diff --check` passed.

Evidence: [test-results.log](test-results.log).

The actual suite invocation inside the separate test container was:

```text
odoo -d soloodoo_review_20260906 -i elmokrif_chantier,elmokrif_chantier_stock --test-enable --test-tags /elmokrif_chantier,/elmokrif_chantier_stock --stop-after-init --without-demo=all --max-cron-threads=0 --log-level=test
```

The container entrypoint supplied its isolated database connection settings. The native server explicitly starts HTTP when testing, even with `--no-http`; this explains the earlier port conflict when tests ran as a second Odoo process inside the live container. Using a separate test container avoids that conflict and avoids running module installation alongside the live server against the same database.

## Confirmed findings, ordered by impact

### P1: A chantier's stock can be reserved for another chantier

Location: `custom_addons/elmokrif_chantier/models/project_project.py:273`.

Initialization creates site locations underneath the supplying warehouse's actual Stock location. Odoo includes child locations when reserving stock. With zero units at central Stock and ten at site A, a delivery for site B became Ready and reserved all ten units from site A. Physical location separation is therefore not providing the intended operational isolation.

Recommendation: put physical site locations outside the central warehouse Stock subtree. Plan migration of existing site locations carefully, including existing reservations. Add a regression proving that stock already delivered to site A cannot satisfy a warehouse delivery for site B.

### P1: The documented Chantier Manager role lacks necessary Inventory access

Locations: `custom_addons/elmokrif_chantier/security/chantier_groups.xml:10`; foundation `models/project_project.py:270`; materials `models/project_project.py:16`.

A fresh user with only Chantier Manager received an AccessError creating the site stock location. After installing materials, the same role also received an AccessError reading the chantier material-cost summary because it reads Stock Moves. Admin testing conceals both problems.

Recommendation: define an explicit role matrix for site staff, approvers and warehouse operators. Provision the minimum appropriate Inventory permissions, or implement tightly scoped authorized location creation. Do not make every site user a full Inventory Administrator simply to suppress errors.

### P1: Start can leave a chantier uninitialized and unable to initialize

Locations: foundation `models/project_project.py:342` and `views/project_project_views.xml:68`.

Reproduction: complete master data → Approve → Start, omitting Initialize. The chantier becomes In Progress with no analytic account or stock location. Initialize subsequently fails because it requires Approved. The normal UI offers no direct way back.

Recommendation: enforce initialization in the server-side transition to In Progress and expose Start only when initialization is complete.

### P1: Approval rules can be bypassed through data writes

Locations: foundation `models/project_project.py:102`, `:123`, `:323`, `:354`; materials `models/material_request.py:25`, `:42`; materials `security/ir.model.access.csv`.

The button checks are not consistently enforced by model create/write operations. Runtime checks showed an ordinary Chantier User could write a submitted material request to Approved and change its quantity to 999. A direct foundation state write approved a chantier with no region or warehouse; another closed a completed chantier despite remaining stock. The equivalent guarded buttons correctly reject these cases.

Recommendation: centralize role, transition, required-data and closure checks at the model layer; protect approved request lines. Add API/import-style regression cases using real restricted users.

### P1: New Material Request can offer no chantier to select

Location: materials `models/material_request.py:13`.

The chantier selector filters by request company, but request company is itself derived from the chantier being selected. An Odoo Form opened without a default chantier had company=False and zero matching chantiers despite an initialized active site existing. Creating from the chantier's smart button can conceal this problem by supplying a default chantier.

Recommendation: default a request company independently, enforce company consistency and make global-menu creation work as well as creation from a chantier.

### P1: Request receipt totals include other requests

Location: materials `models/material_request.py:92`.

Two requests for the same product, one for 100 and another for 50, both displayed Received=150 after delivery. Their physical site stock was correctly 150. The computation searches all completed moves for a chantier/product, without restricting the request.

Recommendation: show receipt quantities per request; show overall site consumption, returns, missing material and balance on a separate chantier materials summary unless explicit allocation to requests is implemented.

### P1: Partial deliveries lose their request and chantier tracking

Locations: materials `models/stock_picking.py:8` and `:63`.

After delivering 4 of 10 requested units, the request was marked Delivered. Its backorder lost both custom links because they have `copy=False`. Completing the remaining six correctly brought physical site stock to ten, but the request still displayed Received=4.

Recommendation: preserve links on backorders, track all related transfers and calculate completion from quantities. Expose Partially Delivered and the outstanding delivery links.

### P1: Request access is not isolated by company

Location: materials `security/ir.model.access.csv` and absence of request/line company record rules.

A user restricted to company B could read the name and state of company A's material request. Relationship consistency checks do not replace record-access rules.

Recommendation: add allowed-company record rules to requests and lines, then test both reads and writes using users restricted to a single company.

### P2: Unit conversions are missing from quantity and cost reports

Locations: materials `models/material_request.py:99` and `models/project_project.py:23`.

Consuming one dozen correctly removed twelve physical units, but showed Consumed=1 and cost=10 instead of 120 at a unit cost of ten. Sum quantities in a consistent product/reporting unit before calculating costs.

### P2: Negative request quantities can be approved

Location: materials `models/material_request.py:35`, `:85`.

A request with quantity -10 could be submitted and approved. Add server-side positive-quantity validation, respecting the unit's rounding.

### Current-price material cost is an estimate, not historical actual cost

Location: materials `models/project_project.py:23`.

Four consumed units at a product cost of ten initially showed 40. Changing the product cost to twenty changed the past chantier amount to 80 without any new movement. This matches the README's current-cost formula, so it is a design limitation rather than a contradiction of the documented implementation. Label the amount as a current-cost estimate or retain a cost at consumption/valuation time if historical project costing is required. Company-dependent cost should also be read in the chantier's company context.

## Running instance differs from the reviewed source

Read-only inspection of the live `odoo17` container showed its `stock_picking.py` still uses the old `stock.stock_location_inventory` external identifier. The local file contains the newer database lookup. The foundation model and material-request model matched their live copies by hash, but this stock-picking file did not.

The local consumption form test now passes. The running app still needs the updated code deployed before that result applies to its Consumption screen. This review did not rebuild or restart the live app.

## Flows that worked

| Flow | Observed result |
| --- | --- |
| Complete master data → Approve → Initialize → Start | Successful under administrator permissions |
| Initialize twice while Approved | Existing regression passed; no duplicate analytic account/location |
| Hold → Start → Complete → Close → Reopen with reason | Successful with no blockers |
| Close with remaining site stock through the Close button | Correctly blocked |
| Ordinary user clicks material Approve | Correctly blocked |
| Consumption form onchange → save → Validate | Destination set to inventory location; transfer completed |
| Deliver 100 → consume 80 → return 10 → report missing 10 | Received 100, consumed 80, returned 10, missing 10; site balance zero; central balance ten |
| Same material flow at unit cost ten | Material cost 900 with the current-price formula |

## UI and UX changes worth doing next

1. **Make one normal New Chantier path.** The separate New Chantier menu fixes one entry point, but All Chantiers still uses the generic Project kanban. Its New button should open the full chantier form. Show region, work type, site address and warehouse prominently, with required-before-approval guidance.
2. **Show the next action clearly.** Guide the user through Approve → Initialize → Start. When a user cannot approve, show an Awaiting manager approval message with the responsible person instead of leaving them to discover a missing role.
3. **Open the created warehouse transfer immediately.** Create Warehouse Transfer currently returns True and leaves the user on the request. Return the transfer form, keep an Open Warehouse Transfer button and rename Picking to Warehouse Transfer.
4. **Use specific material actions.** Offer Record Consumption, Return Materials and Report Missing. Prefill operation and locations, show available site stock, and ask for product and actual quantity. The existing generic Material Operation action creates a new transfer; it does not show operation history.
5. **Add a chantier Materials tab.** Show Product, Received, Consumed, Returned, Missing, Remaining and Cost, with links to movement history. Keep site totals distinct from request-level receipts.
6. **Make lists useful.** Add state badges, filters for Awaiting Approval and Pending Delivery, grouping by chantier and visible backorder information. Display chantier reference, status, region and warehouse on cards.
7. **Use a Reopen dialog.** Show the action when closed and require a fresh reason for each reopening; the current stored reason can be reused. Display actual postal-address details inline when a site contact is selected.

## Regression coverage to add before the next feature phase

The existing four materials tests use consumable products, mostly administrator/sudo actions, and never validate a stock movement. Their consumption test manually supplies the destination rather than exercising the form. Keep the existing eleven tests and add cases for every confirmed defect above, plus successful stockable-product transfers, form creation, real roles, multiple companies, returns, losses, units and partial deliveries.

Add a documented container test runner and CI that checks Odoo's exit code and requires a nonzero executed-test count. Python compilation and XML parsing alone do not validate Odoo views, access rights, stock movements or business invariants. Host `pyproject.toml` currently declares Python >=3.14 with no Odoo dependencies; document the container as the actual application/test runtime.

Recommended order: correct stock isolation, permissions and server-side workflow invariants; correct request/backorder quantities; deploy and test the consumption fix; then simplify the user screens before adding budgets or labor features.
