# EL MOKRIF Integration Tests

This technical addon contains cross-module Odoo acceptance tests. It is intended for disposable test databases and should not be installed in a production database.

Run the complete clean-database suite from the repository root:

```powershell
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-system-tests.ps1
```

The runner installs the chantier, stock, sales, and integration-test addons; executes their post-install tests; and removes the temporary database afterward.
