"""Shared CSV helpers."""

import csv
import io
from collections.abc import Iterator


def read_csv_rows(text: str) -> list[list[str]]:
    sample = text.lstrip("\ufeff")
    reader = csv.reader(io.StringIO(sample))
    return [list(cell.strip() for cell in row) for row in reader]


def find_header(rows: list[list[str]], required: set[str]) -> int:
    for index, row in enumerate(rows):
        labels = {cell.strip() for cell in row if cell.strip()}
        if required.issubset(labels):
            return index
    return -1


def iter_data(rows: list[list[str]], header_index: int) -> Iterator[tuple[int, dict[str, str]]]:
    header = rows[header_index]
    for offset, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not any(cell.strip() for cell in row):
            continue
        padded = row + [""] * (len(header) - len(row))
        yield offset, {header[i]: padded[i] for i in range(len(header))}


def row_text(data: dict[str, str]) -> str:
    return ",".join(data.values())
