import csv
import json
import io
from pathlib import Path

import chardet
import pandas as pd


def detect_encoding(filepath):
    with open(filepath, "rb") as f:
        raw = f.read(100000)
    result = chardet.detect(raw)
    return result.get("encoding", "utf-8")


def load_file(filepath):
    filepath = Path(filepath)
    ext = filepath.suffix.lower()
    if ext in (".csv", ".txt"):
        enc = detect_encoding(filepath)
        try:
            df = pd.read_csv(filepath, encoding=enc)
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding="latin1")
        if df.columns.str.contains("^Unnamed").any():
            df = pd.read_csv(filepath, encoding=enc, header=None)
        return df
    elif ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath, engine="openpyxl" if ext == ".xlsx" else "xlrd")
    elif ext == ".json":
        return pd.read_json(filepath)
    elif ext == ".parquet":
        return pd.read_parquet(filepath)
    elif ext == ".feather":
        return pd.read_feather(filepath)
    elif ext in (".sas7bdat", ".sas7bcat"):
        return pd.read_sas(filepath)
    elif ext == ".dta":
        return pd.read_stata(filepath)
    elif ext == ".ods":
        return pd.read_excel(filepath, engine="odf")
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def save_file(df, filepath, index=False, **kwargs):
    filepath = Path(filepath)
    ext = filepath.suffix.lower()
    if ext == ".csv":
        df.to_csv(filepath, index=index, **kwargs)
    elif ext == ".xlsx":
        df.to_excel(filepath, index=index, engine="xlsxwriter", **kwargs)
    elif ext == ".json":
        orient = kwargs.pop("orient", "records")
        df.to_json(filepath, orient=orient, **kwargs)
    elif ext == ".parquet":
        df.to_parquet(filepath, index=index, **kwargs)
    elif ext == ".feather":
        df.to_feather(filepath, **kwargs)
    elif ext == ".pickle":
        df.to_pickle(filepath, **kwargs)
    elif ext == ".html":
        df.to_html(filepath, index=index, **kwargs)
    elif ext == ".md":
        df.to_markdown(filepath, index=index, **kwargs)
    elif ext == ".sql":
        raise ValueError("Use save_to_sql() for SQL output")
    else:
        raise ValueError(f"Unsupported output format: {ext}")


def save_to_sql(df, filepath, table_name="data", **kwargs):
    import sqlite3
    conn = sqlite3.connect(filepath)
    df.to_sql(table_name, conn, if_exists="replace", index=False, **kwargs)
    conn.close()
