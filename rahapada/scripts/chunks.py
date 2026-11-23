"""Split a page file into parts small enough for one database write (the dashboard accepts about 64 KB per write).

Usage:
  python3 chunks.py FILE [--size 45000]

Writes FILE.part1, FILE.part2, ... next to the file, each ending at a line break, and prints their names.
The first part is written with db_write (set files/<name> {text: part1 + MARK}); each next part replaces MARK
with db_str_replace (new_str = part + MARK, and for the last part without MARK).
"""
import argparse

MARK = "@@RAHAPADA_REST@@"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--size", type=int, default=45000)
    arguments = parser.parse_args()
    with open(arguments.file, encoding="utf-8") as file:
        text = file.read()
    if MARK in text:
        raise SystemExit(f"{arguments.file} already contains {MARK}")

    parts = []
    part = ""
    for line in text.splitlines(keepends=True):
        if part and len((part + line).encode("utf-8")) > arguments.size:
            parts.append(part)
            part = ""
        part += line
    parts.append(part)

    for number, part in enumerate(parts, 1):
        name = f"{arguments.file}.part{number}"
        with open(name, "w", encoding="utf-8") as file:
            file.write(part)
        print(name, len(part.encode("utf-8")), "B")
    print("Märk:", MARK)


if __name__ == "__main__":
    main()
