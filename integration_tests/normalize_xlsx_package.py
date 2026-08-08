"""Canonicalize OpenXML relationship IDs and ZIP metadata after authoring."""

from pathlib import Path
import os
import re
import sys
import zipfile


RELATIONSHIP_ID = re.compile(
    rb'(<Relationship\b[^>]*\bId=")([^"]+)(")'
)


def owner_for_relationships(name):
    if name == "_rels/.rels":
        return None
    marker = "/_rels/"
    if marker not in name or not name.endswith(".rels"):
        return None
    directory, filename = name.split(marker, 1)
    return f"{directory}/{filename[:-5]}"


def normalize(path):
    path = Path(path).resolve()
    temporary = path.with_suffix(path.suffix + ".normalized.tmp")
    with zipfile.ZipFile(path, "r") as source:
        infos = {item.filename: item for item in source.infolist()}
        content = {name: source.read(name) for name in infos}

    for name in sorted(item for item in content if item.endswith(".rels")):
        counter = 0
        replacements = {}

        def replace(match):
            nonlocal counter
            counter += 1
            old = match.group(2)
            new = f"rId{counter}".encode("ascii")
            replacements[old] = new
            return match.group(1) + new + match.group(3)

        content[name] = RELATIONSHIP_ID.sub(replace, content[name])
        owner = owner_for_relationships(name)
        if owner in content:
            for old, new in replacements.items():
                content[owner] = content[owner].replace(
                    b'"' + old + b'"', b'"' + new + b'"',
                )

    with zipfile.ZipFile(
        temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9,
    ) as destination:
        for name in sorted(content):
            original = infos[name]
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = original.create_system
            info.external_attr = original.external_attr
            info.flag_bits = original.flag_bits
            destination.writestr(
                info, content[name],
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    os.replace(temporary, path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: normalize_xlsx_package.py <workbook.xlsx>")
    normalize(sys.argv[1])
