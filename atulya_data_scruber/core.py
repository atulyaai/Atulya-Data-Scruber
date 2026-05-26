import json
import re
from pathlib import Path

import pandas as pd


PRESETS = {
    "sap": {
        "description": "SAP export cleanup",
        "skip_rows": [0, 1, 2],
        "strip_columns": True,
        "date_columns": ["Posting Date", "Document Date", "Entry Date"],
        "date_format": "%Y-%m-%d",
        "number_columns": ["Amount", "Amount in LC", "Tax Amount"],
        "currency_symbols": ["$", "€", "£", "¥", "₹"],
        "drop_empty_threshold": 0.8,
        "remove_summary_rows": True,
    },
    "gst": {
        "description": "GST return data cleanup",
        "date_columns": ["Invoice date", "Date"],
        "date_format": "%d-%m-%Y",
        "number_columns": ["Taxable Value", "CGST", "SGST", "IGST", "Total Invoice Value"],
        "currency_symbols": ["₹", "Rs.", "INR"],
        "gstin_normalize": ["GSTIN", "GSTIN of Recipient", "GSTIN of Supplier"],
        "drop_empty_threshold": 0.5,
    },
    "bank": {
        "description": "Bank statement cleanup",
        "date_columns": ["Transaction Date", "Value Date", "Date"],
        "date_format": "%Y-%m-%d",
        "number_columns": ["Debit", "Credit", "Balance", "Amount"],
        "currency_symbols": ["$", "€", "£", "¥", "₹", "Rs."],
        "standardize_columns": {
                    "Txn Date": "Transaction Date",
                    "Value Date": "Value Date",
                    "Description": "Narration",
                    "Chq/Ref No": "Reference",
                    "Withdrawal": "Debit",
                    "Deposit": "Credit",
                    "Closing Balance": "Balance",
                },
        "drop_empty_threshold": 0.9,
    },
    "generic": {
        "description": "Generic data cleanup",
        "strip_columns": True,
        "trim_whitespace": True,
        "drop_empty_threshold": 0.95,
        "date_columns": [],
        "date_format": "%Y-%m-%d",
        "number_columns": [],
        "currency_symbols": ["$", "€", "£", "¥", "₹"],
    },
}


def apply_preset(df, preset_name):
    preset = PRESETS.get(preset_name)
    if preset is None:
        raise ValueError(f"Unknown preset: {preset_name}. Available: {list(PRESETS.keys())}")
    skip_rows = preset.get("skip_rows", [])
    if skip_rows:
        max_skip = max(skip_rows)
        if max_skip < len(df):
            df = df.iloc[max_skip + 1:].reset_index(drop=True)
    if preset.get("remove_summary_rows"):
        df = df[~df.iloc[:, 0].astype(str).str.contains(
            "Total|Subtotal|Sum|Grand Total", case=False, na=False
        )].reset_index(drop=True)
    if preset.get("strip_columns"):
        df.columns = df.columns.str.strip().str.replace(r"\s+", " ", regex=True)
    rename_map = preset.get("standardize_columns", {})
    if rename_map:
        df = df.rename(columns=rename_map)
    gstin_cols = preset.get("gstin_normalize", [])
    for col in gstin_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.upper().str.replace(r"\s+", "", regex=True)
    date_cols = preset.get("date_columns", [])
    for col in date_cols:
        if col in df.columns:
            df[col] = normalize_dates(df[col], preset.get("date_format", "%Y-%m-%d"))
    number_cols = preset.get("number_columns", [])
    currency_symbols = preset.get("currency_symbols", [])
    for col in number_cols:
        if col in df.columns:
            df[col] = clean_numbers(df[col], currency_symbols)
    drop_thresh = preset.get("drop_empty_threshold", 1.0)
    if drop_thresh < 1.0:
        min_count = int(len(df) * (1 - drop_thresh))
        df = df.dropna(thresh=min_count, axis=1).reset_index(drop=True)
    if preset.get("trim_whitespace"):
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].astype(str).str.strip().replace("", pd.NA)
    return df


def deduplicate(df, columns=None, keep="first"):
    if columns:
        cols = [c for c in columns if c in df.columns]
        if not cols:
            return df
        return df.drop_duplicates(subset=cols, keep=keep).reset_index(drop=True)
    return df.drop_duplicates(keep=keep).reset_index(drop=True)


def handle_blanks(df, strategy="drop", fill_value=None, columns=None):
    if columns:
        cols = [c for c in columns if c in df.columns]
    else:
        cols = list(df.columns)
    if strategy == "drop":
        return df.dropna(subset=cols).reset_index(drop=True)
    elif strategy == "drop_rows":
        return df.dropna(subset=cols).reset_index(drop=True)
    elif strategy == "drop_cols":
        return df.dropna(axis=1, how="all").reset_index(drop=True)
    elif strategy == "fill_value":
        df = df.copy()
        for col in cols:
            df[col] = df[col].fillna(fill_value)
        return df
    elif strategy == "fill_forward":
        return df.ffill().reset_index(drop=True)
    elif strategy == "fill_backward":
        return df.bfill().reset_index(drop=True)
    elif strategy == "fill_mean":
        df = df.copy()
        for col in cols:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].astype("float64").fillna(df[col].astype("float64").mean())
        return df
    elif strategy == "fill_median":
        df = df.copy()
        for col in cols:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].astype("float64").fillna(df[col].astype("float64").median())
        return df
    else:
        raise ValueError(f"Unknown blank strategy: {strategy}")


def normalize_dates(series, date_format="%Y-%m-%d"):
    series = pd.to_datetime(series, errors="coerce")
    return series.dt.strftime(date_format).astype(str).replace("NaT", pd.NA)


def clean_numbers(series, currency_symbols=None):
    if currency_symbols is None:
        currency_symbols = ["$", "€", "£", "¥", "₹"]
    pattern = "[" + re.escape("".join(currency_symbols)) + r",\s]"
    series = series.astype(str).str.replace(pattern, "", regex=True)
    series = series.replace(r"^[\s\-–—]*$", pd.NA, regex=True)
    series = pd.to_numeric(series, errors="coerce")
    return series


def map_columns(df, mapping, drop_unmapped=False):
    reverse_map = {}
    for k, v in mapping.items():
        if k in df.columns:
            reverse_map[k] = v
    df = df.rename(columns=reverse_map)
    if drop_unmapped:
        keep_cols = set(mapping.values())
        df = df[[c for c in df.columns if c in keep_cols]]
    return df


def load_column_mapping(filepath):
    filepath = Path(filepath)
    ext = filepath.suffix.lower()
    with open(filepath, "r", encoding="utf-8") as f:
        if ext == ".json":
            return json.load(f)
        elif ext in (".yaml", ".yml"):
            try:
                import yaml
                return yaml.safe_load(f)
            except ImportError:
                raise ImportError("PyYAML is required for YAML mapping files")
        elif ext == ".csv":
            import csv
            reader = csv.reader(f)
            return {row[0].strip(): row[1].strip() for row in reader if row and not row[0].startswith("#")}
        else:
            raise ValueError(f"Unsupported mapping file format: {ext}")


def merge_files(file_list, on, how="inner", suffixes=("_x", "_y")):
    if not file_list:
        raise ValueError("At least one file is required")
    from .utils import load_file
    dataframes = [load_file(f) for f in file_list]
    if len(dataframes) == 1:
        return dataframes[0]
    merged = dataframes[0]
    for df in dataframes[1:]:
        merged = merged.merge(df, on=on, how=how, suffixes=suffixes)
    return merged


def column_stats(df):
    stats = []
    for col in df.columns:
        nulls = int(df[col].isna().sum())
        total = len(df)
        dtype = str(df[col].dtype)
        uniques = int(df[col].nunique())
        null_pct = round(nulls / total * 100, 2) if total > 0 else 0.0
        stats.append({
            "column": col,
            "dtype": dtype,
            "non_null": total - nulls,
            "nulls": nulls,
            "null_pct": null_pct,
            "uniques": uniques,
        })
    return stats


def convert_file(input_path, output_path, **kwargs):
    from .utils import load_file
    df = load_file(input_path)
    from .utils import save_file
    ext = Path(output_path).suffix.lower()
    if ext == ".sql":
        from .utils import save_to_sql
        table_name = kwargs.pop("table_name", "data")
        save_to_sql(df, output_path, table_name=table_name, **kwargs)
    else:
        save_file(df, output_path, **kwargs)
    return df
