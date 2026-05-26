# Atulya Data Scruber

One-click cleanup and transformation for SAP, GST, bank, CSV and any business spreadsheet data.

## Features

- Remove duplicates, blanks, formatting artifacts
- Standardize date formats, number formats, currencies
- Match and merge GSTIN, PAN, HSN/SAC codes
- Bank statement categorization
- Column mapping & renaming
- Output to clean Excel, CSV, JSON, SQL

## Quick Start

```bash
pip install atulya-data-scruber
atulya-scrub clean messy_data.xlsx --output clean_data.xlsx
atulya-scrub dedup --column email contacts.csv
atulya-scrub standardize --date "%d-%m-%Y" --currency INR sales.xlsx
```

## Presets

| Preset | For |
|--------|-----|
| `sap` | SAP report exports |
| `gst` | GST return data |
| `bank` | Bank statement CSVs |
| `generic` | General CSV/Excel cleanup |

## License

MIT
