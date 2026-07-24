from __future__ import annotations

import os
import struct
import zlib
from typing import Any

# Cache for generated ASCII logos
_LOGO_CACHE: dict[bool, list[str]] = {}


def get_colors(use_color: bool = True) -> dict[str, str]:
    if not use_color:
        return {
            "RESET": "",
            "BOLD": "",
            "DIM": "",
            "CYAN": "",
            "BOLD_CYAN": "",
            "GREEN": "",
            "BOLD_GREEN": "",
            "YELLOW": "",
            "BOLD_YELLOW": "",
            "GRAY": "",
        }
    return {
        "RESET": "\033[0m",
        "BOLD": "\033[1m",
        "DIM": "\033[2m",
        "CYAN": "\033[36m",
        "BOLD_CYAN": "\033[1;36m",
        "GREEN": "\033[32m",
        "BOLD_GREEN": "\033[1;32m",
        "YELLOW": "\033[33m",
        "BOLD_YELLOW": "\033[1;33m",
        "GRAY": "\033[90m",
    }


def generate_favicon_logo(use_color: bool = True) -> list[str]:
    """
    Parses templates/assets/img/favicon.png and renders an aspect-ratio corrected,
    shaded ASCII logo with truecolor ANSI gradients.
    """
    if use_color in _LOGO_CACHE:
        return _LOGO_CACHE[use_color]

    favicon_path = os.path.join("templates", "assets", "img", "favicon.png")
    if not os.path.exists(favicon_path):
        # Fallback if image file is not found
        return [
            "  ███▄▄▄                  ▄▄▄▄██  ",
            "  ████████              ████████  ",
            "  ████████   ▄▄████▄▄   ████████  ",
            "  ████████▄▄██████████▄▄████████  ",
            "  ██████████████████████████████  ",
            "  ████████████▀▀  ▀▀████████████  ",
            "    ▀▀▀████▀          ▀▀███▀▀▀    ",
        ]

    try:
        with open(favicon_path, "rb") as f:
            data = f.read()

        pos = 8
        width, height = 0, 0
        idat = bytearray()

        while pos < len(data):
            length, chunk_type = struct.unpack(">I4s", data[pos : pos + 8])
            pos += 8
            if chunk_type == b"IHDR":
                width, height = struct.unpack(">II", data[pos : pos + 8])
            elif chunk_type == b"IDAT":
                idat.extend(data[pos : pos + length])
            pos += length + 4

        raw = zlib.decompress(bytes(idat))
        bpp = 4
        stride = 1 + width * bpp
        pixels: list[bytearray] = []
        prev_line = bytearray(width * bpp)

        for y in range(height):
            line_start = y * stride
            filter_type = raw[line_start]
            scanline = bytearray(raw[line_start + 1 : line_start + stride])
            if filter_type == 1:
                for i in range(bpp, len(scanline)):
                    scanline[i] = (scanline[i] + scanline[i - bpp]) % 256
            elif filter_type == 2:
                for i in range(len(scanline)):
                    scanline[i] = (scanline[i] + prev_line[i]) % 256
            elif filter_type == 3:
                for i in range(len(scanline)):
                    left = scanline[i - bpp] if i >= bpp else 0
                    scanline[i] = (scanline[i] + (left + prev_line[i]) // 2) % 256
            elif filter_type == 4:
                for i in range(len(scanline)):
                    a = scanline[i - bpp] if i >= bpp else 0
                    b = prev_line[i]
                    c = prev_line[i - bpp] if i >= bpp else 0
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                    scanline[i] = (scanline[i] + pr) % 256
            prev_line = scanline
            pixels.append(scanline)

        w_out = 26
        h_out = 20  # 10 terminal lines high (correct aspect ratio)

        scale_x = width / w_out
        scale_y = height / h_out

        def get_avg_rgba(col: int, row: int) -> tuple[int, int, int, int]:
            x_start, x_end = int(col * scale_x), int((col + 1) * scale_x)
            y_start, y_end = int(row * scale_y), int((row + 1) * scale_y)
            r_sum = g_sum = b_sum = a_sum = 0
            count = 0
            for py in range(y_start, min(y_end, height)):
                for px in range(x_start, min(x_end, width)):
                    r, g, b, a = pixels[py][px * 4 : px * 4 + 4]
                    if a > 20:
                        r_sum += r
                        g_sum += g
                        b_sum += b
                        a_sum += a
                        count += 1
            if count == 0:
                return (0, 0, 0, 0)
            return (
                int(r_sum / count),
                int(g_sum / count),
                int(b_sum / count),
                int(a_sum / count),
            )

        output_lines: list[str] = []

        for y in range(0, h_out, 2):
            line_parts: list[str] = []
            for x in range(w_out):
                top_r, top_g, top_b, top_a = get_avg_rgba(x, y)
                bot_r, bot_g, bot_b, bot_a = get_avg_rgba(x, y + 1)

                top_active = top_a > 50
                bot_active = bot_a > 50

                if use_color:
                    if top_active and bot_active:
                        line_parts.append(
                            f"\033[38;2;{top_r};{top_g};{top_b}m"
                            f"\033[48;2;{bot_r};{bot_g};{bot_b}m▀\033[0m"
                        )
                    elif top_active:
                        line_parts.append(
                            f"\033[38;2;{top_r};{top_g};{top_b}m▀\033[0m"
                        )
                    elif bot_active:
                        line_parts.append(
                            f"\033[38;2;{bot_r};{bot_g};{bot_b}m▄\033[0m"
                        )
                    else:
                        line_parts.append(" ")
                else:
                    avg_b = (
                        (top_r + top_g + top_b + bot_r + bot_g + bot_b) // 6
                        if (top_active or bot_active)
                        else 0
                    )
                    if top_active and bot_active:
                        if avg_b > 170:
                            line_parts.append("█")
                        elif avg_b > 130:
                            line_parts.append("▓")
                        else:
                            line_parts.append("▒")
                    elif top_active or bot_active:
                        if avg_b > 150:
                            line_parts.append("▀" if top_active else "▄")
                        else:
                            line_parts.append("░")
                    else:
                        line_parts.append(" ")

            output_lines.append("".join(line_parts))

        _LOGO_CACHE[use_color] = output_lines
        return output_lines

    except (OSError, zlib.error, struct.error, ValueError) as e:
        print(f"Error parsing favicon.png for ASCII rendering: {e}")
        return [
            "  ███▄▄▄                  ▄▄▄▄██  ",
            "  ████████              ████████  ",
            "  ████████   ▄▄████▄▄   ████████  ",
            "  ████████▄▄██████████▄▄████████  ",
            "  ██████████████████████████████  ",
            "  ████████████▀▀  ▀▀████████████  ",
            "    ▀▀▀████▀          ▀▀███▀▀▀    ",
        ]


HEADER_TEXT = [
    r"  .  .        ..             / ",
    r"  |  | _  _  _||_ . .._.._  /  ",
    r"  |/\|(_)(_)(_][_)(_|[  [ )/   ",
]


def render_ascii_page(
    datetime_str: str,
    services: dict[str, Any],
    user: dict[str, Any] | None = None,
    use_color: bool = True,
    base_url: str = "",
    client_ip: str = "",
) -> str:
    c = get_colors(use_color)
    lines: list[str] = []
    divider = f"{c['BOLD_CYAN']}{'─' * 53}{c['RESET']}"

    # 1. Top Banner (matching nathan.woodburn.au style)
    lines.append(divider)

    # Shaded, aspect-ratio corrected logo generated directly from favicon.png
    logo_lines = generate_favicon_logo(use_color=use_color)
    for logo_line in logo_lines:
        lines.append(f"  {logo_line}")
    lines.append("")

    # Micro font "Woodburn/"
    for header_line in HEADER_TEXT:
        lines.append(f"{c['BOLD_CYAN']}{header_line}{c['RESET']}")
    lines.append(divider)
    lines.append("")

    # 2. Date & Auth Status
    lines.append(f"Date:    {c['BOLD']}{datetime_str}{c['RESET']}")

    if user:
        username = (
            user.get("preferred_username")
            or user.get("name")
            or user.get("email")
            or "User"
        )
        username_cap = username.title()
        logout_url = f"{base_url}/logout" if base_url else "/logout"
        auth_line = (
            f"User:    {c['BOLD_GREEN']}{username_cap}{c['RESET']} "
            f"[{c['BOLD_CYAN']}{logout_url}{c['RESET']}]"
        )
    else:
        auth_line = f"Status:  {c['GRAY']}Guest{c['RESET']}"

    lines.append(auth_line)
    lines.append("")

    # Helper for rendering section header matching nathan.woodburn.au
    def render_section_header(title: str) -> list[str]:
        sec_divider = f"{c['BOLD_CYAN']}{'─' * 47}{c['RESET']}"
        sec_title = f"{c['BOLD_CYAN']} {title} {c['RESET']}"
        sec_underline = f"{c['BOLD_CYAN']}{'─' * (len(title) + 2)}{c['RESET']}"
        return [sec_divider, sec_title, sec_underline, ""]

    # 3. External Services
    if services.get("external"):
        lines.extend(render_section_header("SERVICES"))
        for svc in services["external"]:
            name = svc.get("name", "")
            url = svc.get("url", "")
            desc = svc.get("description", "")
            name_padded = f"{name:<18}"
            lines.append(
                f"- {c['BOLD']}{name_padded}{c['RESET']} [{c['BOLD_CYAN']}{url}{c['RESET']}]"
            )
            if desc:
                lines.append(f"  {c['GRAY']}{desc}{c['RESET']}")
            lines.append("")

    # 4. Internal Services (Only if user is logged in)
    if user and services.get("internal"):
        lines.extend(render_section_header("INTERNAL SERVICES"))
        for svc in services["internal"]:
            name = svc.get("name", "")
            url = svc.get("url", "")
            desc = svc.get("description", "")
            name_padded = f"{name:<18}"
            lines.append(
                f"- {c['BOLD']}{name_padded}{c['RESET']} [{c['BOLD_CYAN']}{url}{c['RESET']}]"
            )
            if desc:
                lines.append(f"  {c['GRAY']}{desc}{c['RESET']}")
            lines.append("")

    # 5. Footer matching nathan.woodburn.au
    if client_ip:
        lines.append(f"Served to: {client_ip}")
        lines.append(divider)

    return "\n".join(lines)
