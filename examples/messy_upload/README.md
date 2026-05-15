# Messy Upload Example

This folder contains a synthetic, deliberately messy short-haul dispatch dataset for testing the LLM-assisted data ingestion path.

Use it when you want to verify that the system can handle non-standard business exports instead of only the built-in CSV/Excel templates.

## Files

- `messy_shorthaul_business_export.xlsx`: a simulated TMS/BI export with business-style sheet names and non-standard column names.
- `messy_dispatch_notes.txt`: free-text operating notes that clarify objectives, fallback rules, and the planning date.

## How To Test

1. Start the web UI.
2. Open the scheduling page.
3. Upload `messy_shorthaul_business_export.xlsx`.
4. Optionally upload `messy_dispatch_notes.txt` at the same time.
5. Configure an OpenAI-compatible provider, such as DeepSeek, with Base URL, API key, and model name.
6. Run scheduling.

Expected router result:

```text
llm_required
```

That means the deterministic adapters did not recognize the files as a standard payload, CSV bundle, standard workbook, or known raw structured attachment set, so the Data Ingestion Agent should ask the configured LLM provider to align the business fields to the solver input schema.

