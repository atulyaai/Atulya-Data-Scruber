from pathlib import Path

import click
import pandas as pd
from rich.console import Console
from rich.table import Table

from .core import (
    PRESETS,
    apply_preset,
    column_stats,
    convert_file,
    deduplicate,
    handle_blanks,
    load_column_mapping,
    map_columns,
    merge_files,
    normalize_dates,
    clean_numbers,
)
from .utils import load_file, save_file

console = Console()
ERR_CONSOLE = Console(stderr=True)


@click.group()
@click.version_option(package_name="atulya-data-scruber")
def main():
    pass


@main.group()
def clean():
    """Clean data operations."""


@clean.command()
@click.argument("input", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output file path")
@click.option("-c", "--columns", multiple=True, help="Column(s) to check for duplicates")
@click.option("--keep", type=click.Choice(["first", "last", "none"]), default="first",
              help="Which duplicate to keep (default: first)")
def dedup(input, output, columns, keep):
    """Remove duplicate rows based on column(s)."""
    df = load_file(input)
    before = len(df)
    df = deduplicate(df, columns=list(columns) if columns else None, keep=keep)
    removed = before - len(df)
    out = output or input
    save_file(df, out)
    console.print(f"Removed [bold]{removed}[/] duplicate rows. Output: {out}")


@clean.command()
@click.argument("input", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output file path")
@click.option("-s", "--strategy",
              type=click.Choice(["drop", "drop_cols", "fill_value", "fill_forward",
                                 "fill_backward", "fill_mean", "fill_median"]),
              default="drop", help="Strategy for handling blanks")
@click.option("-f", "--fill-value", default=None, help="Value to fill (for fill_value strategy)")
@click.option("-c", "--columns", multiple=True, help="Columns to target (default: all)")
def blanks(input, output, strategy, fill_value, columns):
    """Remove or fill empty cells."""
    df = load_file(input)
    df = handle_blanks(df, strategy=strategy, fill_value=fill_value,
                       columns=list(columns) if columns else None)
    out = output or input
    save_file(df, out)
    console.print(f"Applied [bold]{strategy}[/] blank strategy. Output: {out}")


@clean.command()
@click.argument("input", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output file path")
@click.option("-c", "--columns", multiple=True, required=True, help="Date column(s) to standardize")
@click.option("-f", "--format", "date_format", default="%Y-%m-%d",
              help="Output date format (default: %%Y-%%m-%%d)")
def dates(input, output, columns, date_format):
    """Standardize date formats in specified columns."""
    df = load_file(input)
    for col in columns:
        if col in df.columns:
            df[col] = normalize_dates(df[col], date_format)
    out = output or input
    save_file(df, out)
    console.print(f"Standardized dates in {list(columns)}. Output: {out}")


@clean.command()
@click.argument("input", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output file path")
@click.option("-c", "--columns", multiple=True, help="Number column(s) to clean")
@click.option("--currencies", default="$€£¥₹", help="Currency symbols to strip")
def numbers(input, output, columns, currencies):
    """Fix number formats and remove currency symbols."""
    df = load_file(input)
    symbols = list(currencies)
    if columns:
        for col in columns:
            if col in df.columns:
                df[col] = clean_numbers(df[col], symbols)
    else:
        for col in df.select_dtypes(include="object").columns:
            df[col] = clean_numbers(df[col], symbols)
    out = output or input
    save_file(df, out)
    console.print(f"Cleaned numbers. Output: {out}")


@main.group()
def transform():
    """Transform data operations."""


@transform.command()
@click.argument("input", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output file path")
@click.option("-m", "--mapping", required=True, type=click.Path(exists=True),
              help="Column mapping file (JSON, YAML, or CSV)")
@click.option("--drop-unmapped", is_flag=True, default=False,
              help="Drop columns not in mapping")
def map(input, output, mapping, drop_unmapped):
    """Rename and reorder columns via a mapping file."""
    df = load_file(input)
    mapping_dict = load_column_mapping(mapping)
    df = map_columns(df, mapping_dict, drop_unmapped=drop_unmapped)
    out = output or input
    save_file(df, out)
    console.print(f"Mapped columns. Output: {out}")


@transform.command()
@click.argument("inputs", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-o", "--output", required=True, help="Output file path")
@click.option("--on", "on_col", required=True, help="Column to merge on")
@click.option("--how", type=click.Choice(["inner", "outer", "left", "right"]),
              default="inner", help="Merge method")
def merge(inputs, output, on_col, how):
    """Merge multiple files by a common column."""
    df = merge_files(list(inputs), on=on_col, how=how)
    save_file(df, output)
    console.print(f"Merged {len(inputs)} files. Output: {output}")


@main.command()
@click.argument("input", type=click.Path(exists=True))
@click.argument("output", type=click.Path())
@click.option("--table-name", default="data", help="SQL table name (for .sql output)")
@click.option("--orient", default="records", help="JSON orientation (for .json output)")
def convert(input, output, table_name, orient):
    """Convert between CSV, Excel, JSON, SQL, and other formats."""
    extra = {}
    if Path(output).suffix.lower() == ".json":
        extra["orient"] = orient
    if Path(output).suffix.lower() == ".sql":
        extra["table_name"] = table_name
    df = convert_file(input, output, **extra)
    console.print(f"Converted {input} -> {output} ({len(df)} rows)")


@main.group()
def inspect():
    """Inspect data operations."""


@inspect.command()
@click.argument("input", type=click.Path(exists=True))
def stats(input):
    """Show column statistics (nulls, types, unique values)."""
    df = load_file(input)
    stats = column_stats(df)
    table = Table(title=f"Column Statistics - {Path(input).name}")
    table.add_column("Column", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Non-Null", justify="right")
    table.add_column("Nulls", justify="right")
    table.add_column("Null %", justify="right")
    table.add_column("Uniques", justify="right")
    for s in stats:
        table.add_row(
            s["column"], s["dtype"], str(s["non_null"]),
            str(s["nulls"]), f'{s["null_pct"]:.2f}%', str(s["uniques"]),
        )
    console.print(table)


@inspect.command()
@click.argument("input", type=click.Path(exists=True))
@click.option("-n", "--rows", default=10, type=int, help="Number of rows to preview")
@click.option("-w", "--width", default=None, type=int, help="Max column width")
def preview(input, rows, width):
    """Show first N rows in a terminal table."""
    df = load_file(input)
    max_rows = min(rows, len(df))
    display_df = df.head(max_rows)
    table = Table(title=f"Preview - {Path(input).name} ({max_rows} of {len(df)} rows)")
    for col in display_df.columns:
        table.add_column(str(col)[:30], max_width=width)
    for _, row in display_df.iterrows():
        table.add_row(*[str(v)[:50] if pd.notna(v) else "" for v in row])
    console.print(table)


@main.group()
def preset():
    """Apply named cleaning presets."""


@preset.command(name="list")
def list_presets():
    """List available presets."""
    table = Table(title="Available Presets")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    for name, config in PRESETS.items():
        table.add_row(name, config.get("description", ""))
    console.print(table)


@preset.command()
@click.argument("name", type=click.Choice(list(PRESETS.keys())))
@click.argument("input", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output file path")
def run(name, input, output):
    """Apply a named preset (sap, gst, bank, generic)."""
    df = load_file(input)
    df = apply_preset(df, name)
    out = output or input
    save_file(df, out)
    console.print(f"Applied [bold]{name}[/] preset. Output: {out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
