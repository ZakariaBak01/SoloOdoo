# UAT-11 CSV fixtures

Use these files as U8 with the Company A bank journal.

| File | Expected result |
| --- | --- |
| `01-valid-exact-match.csv` | Imports one line. Import the same file again in a new import to verify cross-file deduplication. |
| `02-missing-reference-header.csv` | Rejected because the required `reference` header is absent. |
| `03-invalid-date.csv` | Rejected because `2026/99/99` is not a supported date. |
| `04-invalid-amount.csv` | Rejected because `NaN` is not a finite amount. |
| `05-duplicate-row.csv` | Imports one line because the identical second row is skipped. |
| `06-non-exact-review.csv` | Imports for manual review and should not suggest a payment automatically. |
| `07-native-reconciliation-retest.csv` | Fresh 2,100 MAD exact match for `UAT-PAY-002`, prepared after the native reconciliation fix. |

Before using `01-valid-exact-match.csv`, complete UAT-10 with an inbound Company A payment in the same bank journal and currency. Set its payment reference to `UAT-PAY-001` and its amount to `2,000 MAD`. If the posted payment uses another date, amount, reference, partner, or account identifier, update the CSV row to match the recorded values. The exact-match action checks journal, currency, direction, amount, and reference.

For the final reconciliation check, **Confirm Match** creates the native bank transaction and reconciles it to the payment's outstanding accounting entry. Verify the result under **Invoicing → Bank Statements**, then record the native journal entry and reconciliation reference shown on the import line.
