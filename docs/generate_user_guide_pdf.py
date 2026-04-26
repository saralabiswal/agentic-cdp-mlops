from __future__ import annotations

import argparse
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SOURCE = Path("docs/USER_GUIDE.md")
DEFAULT_OUTPUT = Path("docs/USER_GUIDE.pdf")

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN_X = 54
MARGIN_TOP = 56
MARGIN_BOTTOM = 54
LINE_GAP = 4


@dataclass
class TextLine:
    text: str
    size: int
    font: str
    leading: int
    space_before: int = 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate docs/USER_GUIDE.pdf from docs/USER_GUIDE.md")
    parser.add_argument("--source", default=DEFAULT_SOURCE.as_posix())
    parser.add_argument("--output", default=DEFAULT_OUTPUT.as_posix())
    args = parser.parse_args()

    source = Path(args.source)
    output = Path(args.output)
    markdown = source.read_text(encoding="utf-8")
    lines = render_markdown(markdown)
    pdf_bytes = build_pdf(lines)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(pdf_bytes)
    return 0


def render_markdown(markdown: str) -> list[TextLine]:
    output: list[TextLine] = []
    in_code = False
    for raw in markdown.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code = not in_code
            continue

        if in_code:
            output.extend(wrap_line(line, size=9, font="F3", leading=12, width=88, prefix="  "))
            continue

        if not stripped:
            output.append(TextLine("", 10, "F1", 12, 4))
            continue

        heading = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading:
            level = len(heading.group(1))
            text = clean_inline(heading.group(2))
            if level == 1:
                output.extend(wrap_line(text, size=20, font="F2", leading=24, width=48, space_before=0))
            elif level == 2:
                output.extend(wrap_line(text, size=15, font="F2", leading=19, width=64, space_before=12))
            else:
                output.extend(wrap_line(text, size=12, font="F2", leading=16, width=74, space_before=8))
            continue

        if stripped.startswith("|"):
            cells = [clean_inline(cell.strip()) for cell in stripped.strip("|").split("|")]
            if all(set(cell) <= {"-", ":", " "} for cell in cells):
                continue
            output.extend(wrap_line(" | ".join(cells), size=9, font="F3", leading=12, width=92))
            continue

        ordered = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ordered:
            output.extend(wrap_line(f"- {clean_inline(ordered.group(1))}", size=10, font="F1", leading=14, width=86))
            continue

        if stripped.startswith("- "):
            output.extend(wrap_line(f"- {clean_inline(stripped[2:])}", size=10, font="F1", leading=14, width=86))
            continue

        output.extend(wrap_line(clean_inline(stripped), size=10, font="F1", leading=14, width=90))

    return collapse_blank_lines(output)


def wrap_line(
    text: str,
    *,
    size: int,
    font: str,
    leading: int,
    width: int,
    prefix: str = "",
    space_before: int = 0,
) -> list[TextLine]:
    wrapped = textwrap.wrap(
        text,
        width=width,
        replace_whitespace=True,
        drop_whitespace=True,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]
    result: list[TextLine] = []
    for index, row in enumerate(wrapped):
        result.append(
            TextLine(
                text=f"{prefix}{row}",
                size=size,
                font=font,
                leading=leading,
                space_before=space_before if index == 0 else 0,
            )
        )
    return result


def collapse_blank_lines(lines: list[TextLine]) -> list[TextLine]:
    collapsed: list[TextLine] = []
    previous_blank = False
    for line in lines:
        blank = not line.text
        if blank and previous_blank:
            continue
        collapsed.append(line)
        previous_blank = blank
    return collapsed


def clean_inline(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("`", "")
    text = text.replace("**", "")
    return text


def build_pdf(lines: list[TextLine]) -> bytes:
    pages: list[str] = []
    y = PAGE_HEIGHT - MARGIN_TOP
    stream: list[str] = []

    def new_page() -> None:
        nonlocal y, stream
        if stream:
            pages.append("\n".join(stream))
        stream = []
        y = PAGE_HEIGHT - MARGIN_TOP

    for line in lines:
        y -= line.space_before
        if y - line.leading < MARGIN_BOTTOM:
            new_page()
        if line.text:
            stream.append(pdf_text(line.text, MARGIN_X, y, line.font, line.size))
        y -= line.leading + LINE_GAP

    if stream:
        pages.append("\n".join(stream))

    return assemble_pdf(pages)


def pdf_text(text: str, x: int, y: int, font: str, size: int) -> str:
    escaped = (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\t", "    ")
    )
    return f"BT /{font} {size} Tf {x} {y} Td ({escaped}) Tj ET"


def assemble_pdf(page_streams: list[str]) -> bytes:
    objects: list[bytes] = []

    def add_object(body: str | bytes) -> int:
        data = body if isinstance(body, bytes) else body.encode("latin-1", errors="replace")
        objects.append(data)
        return len(objects)

    catalog_id = add_object("<< /Type /Catalog /Pages 2 0 R >>")
    pages_id = add_object("")
    font_regular_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font_bold_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    font_mono_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    page_ids: list[int] = []
    for stream in page_streams:
        stream_bytes = stream.encode("latin-1", errors="replace")
        content_id = add_object(
            b"<< /Length " + str(len(stream_bytes)).encode("ascii") + b" >>\nstream\n" + stream_bytes + b"\nendstream"
        )
        page_id = add_object(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R /F3 {font_mono_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)

    objects[pages_id - 1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] "
        f"/Count {len(page_ids)} >>"
    ).encode("latin-1")
    objects[catalog_id - 1] = b"<< /Type /Catalog /Pages 2 0 R >>"

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_start = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


if __name__ == "__main__":
    raise SystemExit(main())
