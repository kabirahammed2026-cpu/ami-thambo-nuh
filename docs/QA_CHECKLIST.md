# System QA Checklist

This checklist is meant to be run in DEBUG_DIAG mode so that diagnostics can be verified without login friction.

## Prerequisites
- Set `DEBUG_DIAG=1` in the environment.
- Launch the app normally (e.g., `python render_bootstrap.py` or `streamlit run app.py`).
- Navigate to **System Diagnostics** in the sidebar.

## Phase 1 — Critical flows

### A) Customer lifecycle (CRM)
- [ ] Add a customer in **Customers**.
- [ ] Confirm the new customer appears immediately in **Quotation** and **Operations** dropdowns.
- [ ] Edit the customer and confirm all references update.
- [ ] Delete/disable the customer and confirm it no longer appears in active lists.

### B) Quotation lifecycle (CRM + Sales)
- [ ] Create a quotation in CRM **Quotation**.
- [ ] Confirm it appears in recent quotation lists and is searchable.
- [ ] Open **Operations** and confirm the quotation/customer link is visible.
- [ ] In Sales, create a quotation and confirm it appears on the dashboard and in quotation lists.

### C) Uploads and attachments
- [ ] Upload a PDF and JPG/PNG.
- [ ] Confirm previews render and downloads work.
- [ ] Confirm size/type validation blocks unsupported files.
- [ ] Confirm success/error messages appear after submission.

### D) Backup/restore
- [ ] In **System Diagnostics**, click “Create diagnostic backup”.
- [ ] Verify the archive contains database + uploads.
- [ ] Run “Dry-run restore latest backup” and confirm the restore succeeds.

### E) Dashboard counting
- [ ] Compare dashboard counts vs. raw table totals in **System Diagnostics**.
- [ ] Confirm no double counting or date range mismatch.

## Phase 2 — Diagnostics checks
- [ ] **System Diagnostics** shows valid storage paths (exists + writable).
- [ ] **Data version counters** increment after add/edit/delete actions.
- [ ] Upload diagnostics preview and download work.
- [ ] Backup diagnostics succeed.

## Phase 3 — Regression sweeps
- [ ] CRM operations (delivery orders, work done, service, maintenance) still save.
- [ ] Sales work orders + delivery orders still save.
- [ ] Notifications still render.
