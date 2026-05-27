from __future__ import annotations

import argparse
import re
import struct
import textwrap
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Union


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


@dataclass
class ImageBlock:
    path: Path
    alt: str
    max_height: int = 310
    space_before: int = 8


@dataclass
class PDFImage:
    name: str
    width: int
    height: int
    data: bytes


@dataclass
class PageSpec:
    stream: str
    images: list[PDFImage]


Element = Union[TextLine, ImageBlock]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate docs/USER_GUIDE.pdf from docs/USER_GUIDE.md")
    parser.add_argument("--source", default=DEFAULT_SOURCE.as_posix())
    parser.add_argument("--output", default=DEFAULT_OUTPUT.as_posix())
    args = parser.parse_args()

    source = Path(args.source)
    output = Path(args.output)
    markdown = source.read_text(encoding="utf-8")
    elements = render_markdown(markdown, source_dir=source.parent)
    pdf_bytes = build_pdf(elements)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(pdf_bytes)
    return 0


def render_markdown(markdown: str, *, source_dir: Path) -> list[Element]:
    output: list[Element] = []
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

        image = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if image:
            output.append(
                ImageBlock(
                    path=(source_dir / image.group(2)).resolve(),
                    alt=clean_inline(image.group(1) or "Screenshot"),
                )
            )
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


def collapse_blank_lines(lines: list[Element]) -> list[Element]:
    collapsed: list[Element] = []
    previous_blank = False
    for line in lines:
        blank = isinstance(line, TextLine) and not line.text
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


def build_pdf(elements: list[Element]) -> bytes:
    pages: list[PageSpec] = []
    y = PAGE_HEIGHT - MARGIN_TOP
    stream: list[str] = []
    images: list[PDFImage] = []
    image_counter = 0

    def new_page() -> None:
        nonlocal y, stream, images
        if stream:
            pages.append(PageSpec(stream="\n".join(stream), images=images))
        stream = []
        images = []
        y = PAGE_HEIGHT - MARGIN_TOP

    for element in elements:
        if isinstance(element, TextLine):
            y -= element.space_before
            if y - element.leading < MARGIN_BOTTOM:
                new_page()
            if element.text:
                stream.append(pdf_text(element.text, MARGIN_X, y, element.font, element.size))
            y -= element.leading + LINE_GAP
            continue

        y -= element.space_before
        png = read_png_as_rgb(element.path)
        display_width = PAGE_WIDTH - (MARGIN_X * 2)
        display_height = int(display_width * (png["height"] / png["width"]))
        if display_height > element.max_height:
            display_height = element.max_height
            display_width = int(display_height * (png["width"] / png["height"]))
        if y - display_height - 18 < MARGIN_BOTTOM:
            new_page()

        image_counter += 1
        image_name = f"Im{image_counter}"
        image = PDFImage(
            name=image_name,
            width=int(png["width"]),
            height=int(png["height"]),
            data=zlib.compress(png["rgb"]),
        )
        images.append(image)
        x = MARGIN_X
        image_y = y - display_height
        stream.append(pdf_text(element.alt, x, y, "F2", 10))
        y -= 14
        image_y = y - display_height
        stream.append(pdf_rect(x - 1, image_y - 1, display_width + 2, display_height + 2))
        stream.append(f"q {display_width} 0 0 {display_height} {x} {image_y} cm /{image_name} Do Q")
        y = image_y - 16

    if stream:
        pages.append(PageSpec(stream="\n".join(stream), images=images))

    return assemble_pdf(pages)


def pdf_text(text: str, x: int, y: int, font: str, size: int) -> str:
    escaped = (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\t", "    ")
    )
    return f"BT /{font} {size} Tf {x} {y} Td ({escaped}) Tj ET"


def pdf_rect(x: int, y: int, width: int, height: int) -> str:
    return f"q 0.72 0.82 0.88 RG {x} {y} {width} {height} re S Q"


def read_png_as_rgb(path: Path) -> dict[str, int | bytes]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Unsupported image format for {path}; expected PNG.")

    offset = 8
    width = height = bit_depth = color_type = None
    idat = bytearray()
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or bit_depth != 8 or color_type not in {0, 2, 6}:
        raise ValueError(f"Unsupported PNG encoding for {path}.")

    channels = {0: 1, 2: 3, 6: 4}[int(color_type)]
    bpp = channels
    stride = int(width) * channels
    raw = zlib.decompress(bytes(idat))
    rows: list[bytes] = []
    src = 0
    prev = bytearray(stride)

    for _ in range(int(height)):
        filter_type = raw[src]
        src += 1
        scanline = bytearray(raw[src : src + stride])
        src += stride
        recon = bytearray(stride)
        for i, value in enumerate(scanline):
            left = recon[i - bpp] if i >= bpp else 0
            up = prev[i]
            up_left = prev[i - bpp] if i >= bpp else 0
            if filter_type == 0:
                recon[i] = value
            elif filter_type == 1:
                recon[i] = (value + left) & 0xFF
            elif filter_type == 2:
                recon[i] = (value + up) & 0xFF
            elif filter_type == 3:
                recon[i] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                recon[i] = (value + paeth(left, up, up_left)) & 0xFF
            else:
                raise ValueError(f"Unsupported PNG filter {filter_type} for {path}.")
        rows.append(bytes(recon))
        prev = recon

    rgb = bytearray()
    if color_type == 0:
        for row in rows:
            for gray in row:
                rgb.extend([gray, gray, gray])
    elif color_type == 2:
        for row in rows:
            rgb.extend(row)
    else:
        for row in rows:
            for i in range(0, len(row), 4):
                rgb.extend(row[i : i + 3])

    return {"width": int(width), "height": int(height), "rgb": bytes(rgb)}


def paeth(left: int, up: int, up_left: int) -> int:
    p = left + up - up_left
    pa = abs(p - left)
    pb = abs(p - up)
    pc = abs(p - up_left)
    if pa <= pb and pa <= pc:
        return left
    if pb <= pc:
        return up
    return up_left


def assemble_pdf(page_streams: list[PageSpec]) -> bytes:
    objects: list[bytes] = []

    def add_object(body: str | bytes) -> int:
        data = body if isinstance(body, bytes) else body.encode("latin-1", errors="replace")
        objects.append(data)
        return len(objects)

    catalog_id = add_object("<< /Type /Catalog /Pages 2 0 R >>")
    pages_id = add_object("")
    font_regular_id = add_object(
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    font_bold_id = add_object(
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    )
    font_mono_id = add_object(
        "<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"
    )

    page_ids: list[int] = []
    for page in page_streams:
        image_resource_parts: list[str] = []
        for image in page.images:
            image_stream = (
                b"<< /Type /XObject /Subtype /Image /Width "
                + str(image.width).encode("ascii")
                + b" /Height "
                + str(image.height).encode("ascii")
                + b" /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length "
                + str(len(image.data)).encode("ascii")
                + b" >>\nstream\n"
                + image.data
                + b"\nendstream"
            )
            image_object_id = add_object(image_stream)
            image_resource_parts.append(f"/{image.name} {image_object_id} 0 R")

        stream_bytes = page.stream.encode("cp1252", errors="replace")
        content_id = add_object(
            b"<< /Length " + str(len(stream_bytes)).encode("ascii") + b" >>\nstream\n" + stream_bytes + b"\nendstream"
        )
        xobject_resources = f"/XObject << {' '.join(image_resource_parts)} >>" if image_resource_parts else ""
        page_id = add_object(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R /F3 {font_mono_id} 0 R >> {xobject_resources} >> "
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
