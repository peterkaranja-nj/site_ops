# Site Ops

Purchase requisition, multi-level approval and procurement control for ERPNext, built as a Frappe app.

A site requester raises a **Purchase Requisition**. It routes through Site Manager, Procurement and
(depending on value) Director approval. Final approval submits the requisition and raises a submitted
ERPNext **Material Request** linked back to it. Purchase Orders are checked against the Project budget,
low-stock items are reported daily, and a dashboard shows spend and the approval queue.

Targets **Frappe / ERPNext v15**.

## Contents

| Area | What it does |
|---|---|
| Purchase Requisition | Submittable DocType with item table, naming series `PREQ-.YYYY.-.#####`, cost center, warehouse, project and amount rollup |
| Approval workflow | `Draft > Pending Site Manager > Pending Procurement > [Pending Director] > Approved`, with rejection and reopen |
| Material Request hand-off | Created and submitted on final approval; cancelled automatically if the requisition is cancelled |
| Budget guard | `validate` hook on Purchase Order blocks orders that push a Project past its Estimated Cost |
| Stock alert | Daily scheduled digest of items at or below their reorder level, sent at most once per day |
| Procurement Dashboard | Desk page with period filters, summary cards, spend-by-supplier chart and the user's approval queue |
| REST API | Whitelisted endpoints for external front ends |

No core ERPNext or Frappe file is modified. ERPNext is extended through `doc_events`, a Custom Field
fixture and a client script, so the app survives `bench update`.

## Install

```bash
cd $PATH_TO_BENCH
bench get-app /path/to/site_ops          # or: bench get-app <git-url>
bench --site <site> install-app site_ops
bench --site <site> migrate
```

Installation creates the four roles, the workflow states and actions, and saves the settings defaults.
The workflow and the `custom_purchase_requisition` field on Material Request are imported as fixtures.

## Roles

| Role | Can do |
|---|---|
| Site Requester | Create requisitions, edit own drafts, submit for approval, reopen own rejections |
| Site Manager | Approve or reject at the first stage |
| Procurement Officer | Approve or reject at the second stage |
| Procurement Director | Approve or reject at the final stage, cancel approved requisitions |
| System Manager | Full access, settings |

Approval transitions disallow self-approval, so a user holding more than one role cannot approve a
requisition they raised. Restrict what each manager sees with standard User Permissions on Project,
Cost Center or Company.

## Approval flow

```
Draft --Submit for Approval--> Pending Site Manager --Approve--> Pending Procurement
                                       |                                |
                                    Reject                  requires_director?
                                       |                       yes /        \ no
                                       v                        v            v
                                   Rejected             Pending Director   Approved
                                       |                  Approve |  Reject    (submitted,
                                    Reopen                        v     |     Material Request
                                       v                       Approved  v        raised)
                                     Draft                          Rejected
```

`requires_director` is set on every save: it is true when the total estimate is at or above
**Director Approval Threshold** in *Site Ops Settings*. A threshold of `0` (default) sends every
requisition to the Director.

## Settings

*Site Ops Settings* (System Manager):

- **Enforce Project Budget on Purchase Orders**: on by default. Budget is the Project's *Estimated Cost*;
  committed spend is the sum of submitted Purchase Orders on that Project in company currency.
- **Director Approval Threshold**: see above.
- **Send Daily Low Stock Alert** and **Notify Role**: recipients are the enabled users holding the role
  (default `Purchase Manager`). Reorder levels come from the *Reorder* table on each Item.

## API

All endpoints are under `/api/method/site_ops.api.*` and use standard Frappe authentication
(session, or `Authorization: token <api_key>:<api_secret>`). Permissions of the calling user apply.

Create a requisition and route it for approval in one call:

```bash
curl -X POST https://erp.example.com/api/method/site_ops.api.create_requisition \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{
    "submit_for_approval": 1,
    "requisition": {
      "company": "Example Ltd",
      "required_by": "2026-11-01",
      "project": "PROJ-0004",
      "cost_center": "Main - EL",
      "warehouse": "Site Store - EL",
      "purpose": "Slab pour, block B",
      "items": [
        {"item_code": "CEMENT-42.5", "qty": 120, "rate": 780},
        {"item_code": "STEEL-Y12", "qty": 3, "rate": 96000}
      ]
    }
  }'
```

| Method | Verb | Purpose |
|---|---|---|
| `create_requisition` | POST | Create from JSON; `submit_for_approval=1` applies the first workflow action |
| `get_requisition_status` | GET | Workflow state, total, linked Material Request and the roles it is waiting on |
| `get_project_budget` | GET | Estimated cost, committed spend and remainder for a Project |
| `get_dashboard_data` | GET | Data behind the dashboard page |

Only the documented request fields are read; `docstatus`, `workflow_state`, `owner` and anything else in
the payload are ignored. Further workflow steps use Frappe's standard
`frappe.model.workflow.apply_workflow` method.

## Tests

```bash
bench --site <test-site> set-config allow_tests true
bench --site <test-site> run-tests --app site_ops
```

The suite covers validation rules, approval routing (with and without Director), Material Request
creation and cancellation, the budget guard, and the API contract. It uses the `_Test Company` records
that ERPNext's own test runner provides.

## Layout

```
site_ops/
├── pyproject.toml
├── license.txt
└── site_ops/
    ├── hooks.py                  doc_events, scheduler, fixtures, client script
    ├── constants.py              workflow, role and state names
    ├── install.py                roles, workflow masters, settings defaults
    ├── utils.py                  budget position, low-stock query
    ├── tasks.py                  daily low-stock alert
    ├── api.py                    whitelisted endpoints
    ├── events/purchase_order.py  budget guard
    ├── fixtures/                 custom_field.json, workflow.json
    ├── public/js/                Material Request client script
    ├── templates/emails/         low-stock email
    ├── tests/
    └── site_ops/                 module: doctypes, page, workspace
```

## License

MIT. See `license.txt`.
