import csv
import re
from pathlib import Path


NAME_FIELD_KO = "선수의이름"


def strip_amount_suffix(name: str) -> str:
    """
    Remove trailing patterns like " 3,770조" or " 1조" from a name.
    Keeps everything before the last space-number-조 pattern.
    """
    if not name:
        return name
    s = name.strip()
    return re.sub(r"\s+[0-9,]+조$", "", s)


def strip_parentheses(name: str) -> str:
    """Remove any trailing parenthetical like " (DF/MF·FW)" from the name."""
    if not name:
        return name
    # remove any (...) parts anywhere
    return re.sub(r"\s*\([^)]*\)", "", name).strip()


def normalize_person_name(raw: str) -> str:
    """Normalize to human name only: remove amounts and parentheses."""
    return strip_parentheses(strip_amount_suffix(raw or "")).strip()


def fix_best_price(input_csv: Path, output_csv: Path) -> dict:
    """
    Read best_price CSV and add a new column '선수의이름' by normalizing player_name.
    Do not modify the original 'player_name'.
    """
    fixed = 0
    total = 0
    examples = []

    with input_csv.open("r", encoding="utf-8-sig", newline="") as f_in:
        reader = csv.DictReader(f_in)
        fieldnames = list(reader.fieldnames or [])
        if NAME_FIELD_KO not in fieldnames:
            fieldnames.append(NAME_FIELD_KO)

        rows = []
        for row in reader:
            total += 1
            old = row.get("player_name", "")
            new = normalize_person_name(old)
            row[NAME_FIELD_KO] = new
            if new != old and len(examples) < 8:
                examples.append((old, new))
            # Count rows where a change happened (suffix/paren removed)
            if new != old:
                fixed += 1
            rows.append(row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return {
        "file": str(input_csv),
        "written": str(output_csv),
        "total": total,
        "updated_names": fixed,
        "examples": examples,
    }


def add_public_name_to_top_daily(input_csv: Path, output_csv: Path) -> dict:
    """
    For top_daily_record.clean.ko.strip.csv, add '선수의이름' column derived from the
    3rd column (선수_기본정보), which typically looks like
    "로멜루 루카쿠, 5, ST 101, 19" → base name '로멜루 루카쿠'. Also remove any parentheses.
    """
    total = 0
    added = 0
    examples = []

    with input_csv.open("r", encoding="utf-8-sig", newline="") as f_in:
        reader = csv.reader(f_in)
        rows = list(reader)

    if not rows:
        raise RuntimeError(f"Empty CSV: {input_csv}")

    header = list(rows[0])
    # Append new column if not present
    if NAME_FIELD_KO not in header:
        header.append(NAME_FIELD_KO)
    name_col_index = header.index(NAME_FIELD_KO)

    out_rows = [header]
    for row in rows[1:]:
        total += 1
        # Ensure row has at least 3 columns
        if len(row) < 3:
            # pad row
            if len(row) <= name_col_index:
                row = row + [""] * (name_col_index - len(row) + 1)
            row[name_col_index] = ""
            out_rows.append(row)
            continue
        basic_info = row[2] or ""
        # Extract base name as text before the first comma in the composite field
        base_name = basic_info.split(",")[0].strip()
        base_name = normalize_person_name(base_name)
        # Ensure row length fits header length
        if len(row) <= name_col_index:
            row = row + [""] * (name_col_index - len(row) + 1)
        row[name_col_index] = base_name
        added += 1
        if len(examples) < 8:
            examples.append((basic_info, base_name))
        out_rows.append(row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as f_out:
        writer = csv.writer(f_out)
        writer.writerows(out_rows)

    return {
        "file": str(input_csv),
        "written": str(output_csv),
        "total": total,
        "names_added": added,
        "examples": examples,
    }


def main():
    base_price_in = Path("analytics/clean/best_price_daily.clean.names.strip.csv")
    base_price_out = Path("analytics/clean/best_price_daily.clean.names.strip.fixed.csv")
    top_daily_in = Path("analytics/clean/top_daily_record.clean.ko.strip.csv")
    top_daily_out = Path("analytics/clean/top_daily_record.clean.ko.strip.fixed.csv")

    results = []
    if base_price_in.exists():
        results.append(fix_best_price(base_price_in, base_price_out))
    else:
        results.append({"file": str(base_price_in), "error": "missing"})

    if top_daily_in.exists():
        results.append(add_public_name_to_top_daily(top_daily_in, top_daily_out))
    else:
        results.append({"file": str(top_daily_in), "error": "missing"})

    # Print a compact summary
    for r in results:
        print(r)


if __name__ == "__main__":
    main()

