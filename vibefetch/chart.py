from __future__ import annotations

import base64
import datetime as dt
import os
import shutil
import struct
import sys
import zlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from .aggregate import record_total_tokens
from .models import Record


@dataclass
class ChartData:
    mode: str
    bucket_labels: List[str]
    models: List[str]
    series: Dict[str, List[int]]
    max_stack_tokens: int
    scale_div: int
    scale_suffix: str

    @property
    def chart_title(self) -> str:
        ylabel = f"Tokens ({self.scale_suffix})" if self.scale_suffix else "Tokens"
        if self.mode == "hourly":
            return f"{ylabel} per Hour"
        return f"{ylabel} per Day"


_RGB_PALETTE = [
    (230, 92, 90),
    (72, 202, 126),
    (87, 143, 255),
    (85, 214, 227),
    (210, 107, 246),
    (244, 162, 97),
    (181, 189, 204),
    (224, 114, 125),
    (115, 229, 176),
    (118, 176, 250),
    (102, 220, 238),
    (221, 134, 247),
    (251, 191, 114),
    (208, 215, 228),
]

_PLOTEXT_COLORS = [
    "red",
    "green",
    "blue",
    "cyan",
    "magenta",
    "orange",
    "gray",
    "red+",
    "green+",
    "blue+",
    "cyan+",
    "magenta+",
    "orange+",
    "gray+",
]

_FONT_WIDTH = 3
_FONT_HEIGHT = 5
_FONT_SPACING = 1
_FONT_LINE_SPACING = 2
_BITMAP_FONT = {
    " ": ("000", "000", "000", "000", "000"),
    "-": ("000", "000", "111", "000", "000"),
    "/": ("001", "001", "010", "100", "100"),
    ":": ("000", "010", "000", "010", "000"),
    ".": ("000", "000", "000", "000", "010"),
    ",": ("000", "000", "000", "010", "100"),
    "(": ("001", "010", "010", "010", "001"),
    ")": ("100", "010", "010", "010", "100"),
    "+": ("000", "010", "111", "010", "000"),
    "?": ("110", "001", "010", "000", "010"),
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("110", "001", "010", "100", "111"),
    "3": ("110", "001", "010", "001", "110"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "110", "001", "110"),
    "6": ("011", "100", "110", "101", "011"),
    "7": ("111", "001", "010", "100", "100"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("011", "101", "011", "001", "110"),
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "101", "010"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "P": ("110", "101", "110", "100", "100"),
    "Q": ("010", "101", "101", "011", "001"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
}


def _prepare_chart_data(
    records: Iterable[Record],
    chart_models: Optional[List[str]],
    chart_top: int,
    mode: str,
) -> Optional[ChartData]:
    if mode not in {"hourly", "daily"}:
        raise ValueError(f"Unsupported chart mode: {mode}")

    buckets: Dict[Tuple[dt.datetime, str], int] = {}
    for record in records:
        if mode == "hourly":
            bucket = record.timestamp.replace(minute=0, second=0, microsecond=0)
        else:
            bucket = record.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        key = (bucket, record.model)
        buckets[key] = buckets.get(key, 0) + record_total_tokens(record)

    if not buckets:
        print(f"No {mode} stats available for chart.", file=sys.stderr)
        return None

    bucket_times = sorted({bucket for bucket, _ in buckets.keys()})
    if not bucket_times:
        print(f"No {mode} stats available for chart.", file=sys.stderr)
        return None

    start_bucket = min(bucket_times)
    end_bucket = max(bucket_times)
    all_buckets: List[dt.datetime] = []
    current = start_bucket
    step = dt.timedelta(hours=1) if mode == "hourly" else dt.timedelta(days=1)
    while current <= end_bucket:
        all_buckets.append(current)
        current += step

    if mode == "hourly":
        bucket_labels = [bucket.strftime("%m-%d/%H") for bucket in all_buckets]
    else:
        bucket_labels = [bucket.strftime("%m-%d") for bucket in all_buckets]

    model_totals: Dict[str, int] = {}
    for (_, model), tokens in buckets.items():
        model_totals[model] = model_totals.get(model, 0) + tokens

    if chart_models:
        models = [model for model in chart_models if model in model_totals]
    else:
        models = [
            model
            for model, _ in sorted(
                model_totals.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ][: max(chart_top, 1)]

    if not models:
        print("No models selected for chart.", file=sys.stderr)
        return None

    series = {model: [0 for _ in all_buckets] for model in models}
    bucket_index = {bucket: idx for idx, bucket in enumerate(all_buckets)}
    for (bucket, model), tokens in buckets.items():
        if model not in series:
            continue
        series[model][bucket_index[bucket]] += tokens

    max_stack_tokens = 0
    for idx in range(len(all_buckets)):
        total = 0
        for model in models:
            total += series[model][idx]
        max_stack_tokens = max(max_stack_tokens, total)

    if max_stack_tokens >= 1_000_000:
        scale_div = 1_000_000
        scale_suffix = "M"
    elif max_stack_tokens >= 1_000:
        scale_div = 1_000
        scale_suffix = "K"
    else:
        scale_div = 1
        scale_suffix = ""

    return ChartData(
        mode=mode,
        bucket_labels=bucket_labels,
        models=models,
        series=series,
        max_stack_tokens=max_stack_tokens,
        scale_div=scale_div,
        scale_suffix=scale_suffix,
    )


def _model_colors_rgb(models: List[str]) -> Dict[str, Tuple[int, int, int]]:
    return {model: _RGB_PALETTE[i % len(_RGB_PALETTE)] for i, model in enumerate(models)}


def _model_colors_plotext(models: List[str]) -> Dict[str, str]:
    return {
        model: _PLOTEXT_COLORS[i % len(_PLOTEXT_COLORS)] for i, model in enumerate(models)
    }


def _rgb_text(text: str, rgb: Tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"\x1b[38;2;{r};{g};{b}m{text}\x1b[0m"


def _legend_lines(models: List[str], color_map: Dict[str, Tuple[int, int, int]]) -> List[str]:
    lines = ["", "Legend:"]
    for model in models:
        color = color_map[model]
        lines.append(f"{_rgb_text('■', color)} {_rgb_text(model, color)}")
    return lines


def _sample_ticks(
    bucket_labels: List[str],
    x_positions: List[int],
    max_labels: int,
) -> Tuple[List[int], List[str]]:
    if len(bucket_labels) <= max_labels:
        return x_positions, bucket_labels

    count = max(2, max_labels)
    n = len(bucket_labels)
    idxs = [round(i * (n - 1) / (count - 1)) for i in range(count)]
    seen = set()
    idxs_unique = []
    for idx in idxs:
        if idx in seen:
            continue
        seen.add(idx)
        idxs_unique.append(idx)
    if idxs_unique[-1] != n - 1:
        idxs_unique.append(n - 1)
    tick_positions = [x_positions[i] for i in idxs_unique]
    tick_labels = [bucket_labels[i] for i in idxs_unique]
    return tick_positions, tick_labels


def _format_scaled_tokens(value: int, scale_div: int, scale_suffix: str) -> str:
    if scale_div <= 1:
        return f"{value:,}"
    scaled = value / scale_div
    if scaled >= 100:
        text = f"{scaled:,.0f}"
    elif scaled >= 10:
        text = f"{scaled:,.1f}"
    else:
        text = f"{scaled:,.2f}"
    text = text.rstrip("0").rstrip(".")
    return f"{text}{scale_suffix}"


def _glyph_for_char(ch: str) -> Tuple[str, str, str, str, str]:
    if ch in _BITMAP_FONT:
        return _BITMAP_FONT[ch]
    upper = ch.upper()
    if upper in _BITMAP_FONT:
        return _BITMAP_FONT[upper]
    return _BITMAP_FONT["?"]


def _text_dimensions(text: str, scale: int) -> Tuple[int, int]:
    if scale <= 0:
        scale = 1
    lines = text.splitlines() or [""]
    char_w = _FONT_WIDTH * scale
    char_h = _FONT_HEIGHT * scale
    spacing = _FONT_SPACING * scale
    line_spacing = _FONT_LINE_SPACING * scale
    width = 0
    for line in lines:
        if not line:
            line_width = 0
        else:
            line_width = len(line) * char_w + max(0, len(line) - 1) * spacing
        width = max(width, line_width)
    height = len(lines) * char_h + max(0, len(lines) - 1) * line_spacing
    return width, height


def _fill_rect(
    pixels: bytearray,
    width: int,
    height: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: Tuple[int, int, int],
) -> None:
    if x0 > x1 or y0 > y1:
        return
    x0 = max(0, min(width - 1, x0))
    x1 = max(0, min(width - 1, x1))
    y0 = max(0, min(height - 1, y0))
    y1 = max(0, min(height - 1, y1))
    if x0 > x1 or y0 > y1:
        return
    stride = width * 3
    row = bytes(color) * (x1 - x0 + 1)
    row_len = len(row)
    for y in range(y0, y1 + 1):
        start = y * stride + x0 * 3
        pixels[start : start + row_len] = row


def _draw_text(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    text: str,
    color: Tuple[int, int, int],
    scale: int,
) -> None:
    if not text:
        return
    if scale <= 0:
        scale = 1

    char_w = _FONT_WIDTH * scale
    char_h = _FONT_HEIGHT * scale
    spacing = _FONT_SPACING * scale
    line_spacing = _FONT_LINE_SPACING * scale
    line_y = y

    for line in text.splitlines() or [""]:
        cursor_x = x
        for ch in line:
            glyph = _glyph_for_char(ch)
            for row, bits in enumerate(glyph):
                for col, bit in enumerate(bits):
                    if bit != "1":
                        continue
                    px0 = cursor_x + col * scale
                    py0 = line_y + row * scale
                    _fill_rect(
                        pixels,
                        width,
                        height,
                        px0,
                        py0,
                        px0 + scale - 1,
                        py0 + scale - 1,
                        color,
                    )
            cursor_x += char_w + spacing
        line_y += char_h + line_spacing


def _supports_kitty_graphics() -> bool:
    if not sys.stdout.isatty():
        return False
    if os.getenv("TMUX"):
        return False
    term = os.getenv("TERM", "").lower()
    term_program = os.getenv("TERM_PROGRAM", "").lower()
    if os.getenv("KITTY_WINDOW_ID"):
        return True
    if "kitty" in term:
        return True
    if term_program in {"ghostty", "wezterm"}:
        return True
    return False


def _select_chart_backend() -> str:
    backend = os.getenv("VIBEFETCH_CHART_BACKEND", "auto").strip().lower()
    if backend not in {"auto", "kitty", "plotext"}:
        print(
            f"Unsupported VIBEFETCH_CHART_BACKEND={backend!r}; falling back to auto.",
            file=sys.stderr,
        )
        backend = "auto"
    if backend == "auto":
        if _supports_kitty_graphics():
            return "kitty"
        return "plotext"
    return backend


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)


def _encode_png_rgb(width: int, height: int, pixels: bytes) -> bytes:
    if len(pixels) != width * height * 3:
        raise ValueError("Invalid pixel buffer length for RGB image.")
    raw = bytearray()
    row_width = width * 3
    for y in range(height):
        raw.append(0)
        start = y * row_width
        raw.extend(pixels[start : start + row_width])
    compressed = zlib.compress(bytes(raw), level=6)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


def _build_kitty_chart_png(
    data: ChartData,
    color_map: Dict[str, Tuple[int, int, int]],
    width: int,
    height: int,
) -> bytes:
    background = (13, 16, 21)
    grid = (41, 48, 59)
    axis = (155, 166, 186)
    text_main = (220, 228, 241)
    text_dim = (164, 176, 197)
    pixels = bytearray(bytes(background) * (width * height))

    bucket_count = len(data.bucket_labels)
    title = data.chart_title.upper()
    x_axis_label = "TIME" if data.mode == "hourly" else "DATE"
    y_axis_label = f"TOKENS ({data.scale_suffix})" if data.scale_suffix else "TOKENS"
    y_tick_steps = 4
    y_tick_values = [
        int(round(i * data.max_stack_tokens / y_tick_steps))
        for i in range(y_tick_steps + 1)
    ]
    y_tick_labels = [
        _format_scaled_tokens(value, data.scale_div, data.scale_suffix)
        for value in y_tick_values
    ]

    if width < 1100:
        label_scale = 2
        title_scale = 2
    elif width < 1800:
        label_scale = 3
        title_scale = 3
    else:
        label_scale = 3
        title_scale = 4

    title_w, title_h = _text_dimensions(title, title_scale)
    _, y_axis_h = _text_dimensions(y_axis_label, label_scale)
    x_axis_w, x_axis_h = _text_dimensions(x_axis_label, label_scale)
    y_tick_w = max(
        (_text_dimensions(label, label_scale)[0] for label in y_tick_labels),
        default=0,
    )
    x_tick_h = _text_dimensions("00-00/00", label_scale)[1]

    left = max(24, y_tick_w + 16)
    right = max(12, width // 80)
    top = max(16, title_h + y_axis_h + 14)
    bottom = max(20, x_tick_h + x_axis_h + 16)
    plot_left = left
    plot_right = width - right - 1
    plot_top = top
    plot_bottom = height - bottom - 1
    if plot_right <= plot_left or plot_bottom <= plot_top:
        return _encode_png_rgb(width, height, bytes(pixels))

    title_x = max(2, (width - title_w) // 2)
    _draw_text(
        pixels,
        width,
        height,
        title_x,
        6,
        title,
        text_main,
        title_scale,
    )
    _draw_text(
        pixels,
        width,
        height,
        plot_left,
        title_h + 10,
        y_axis_label,
        text_dim,
        label_scale,
    )

    _fill_rect(
        pixels,
        width,
        height,
        plot_left,
        plot_bottom,
        plot_right,
        plot_bottom,
        axis,
    )
    _fill_rect(
        pixels,
        width,
        height,
        plot_left,
        plot_top,
        plot_left,
        plot_bottom,
        axis,
    )

    plot_height = max(1, plot_bottom - plot_top)
    for idx, label in enumerate(y_tick_labels):
        y = plot_bottom - int(round(idx * plot_height / y_tick_steps))
        line_color = axis if idx == 0 else grid
        _fill_rect(pixels, width, height, plot_left + 1, y, plot_right, y, line_color)
        _fill_rect(pixels, width, height, plot_left - 3, y, plot_left, y, axis)
        label_w, label_h = _text_dimensions(label, label_scale)
        label_x = max(1, plot_left - label_w - 6)
        label_y = max(1, min(height - label_h - 1, y - label_h // 2))
        _draw_text(
            pixels,
            width,
            height,
            label_x,
            label_y,
            label,
            text_dim,
            label_scale,
        )

    if bucket_count == 0 or data.max_stack_tokens <= 0:
        return _encode_png_rgb(width, height, bytes(pixels))

    plot_width = max(1, plot_right - plot_left + 1)
    slot_width = plot_width / max(1, bucket_count)
    bar_width = max(1, int(slot_width * 0.82))
    usable_height = max(1, plot_bottom - plot_top)
    for idx in range(bucket_count):
        x0 = plot_left + int(round(idx * slot_width + (slot_width - bar_width) / 2.0))
        x1 = min(plot_right, x0 + bar_width - 1)
        y_cursor = plot_bottom - 1
        for model in data.models:
            value = data.series[model][idx]
            if value <= 0:
                continue
            bar_height = max(1, int(round((value / data.max_stack_tokens) * usable_height)))
            y0 = max(plot_top, y_cursor - bar_height + 1)
            _fill_rect(pixels, width, height, x0, y0, x1, y_cursor, color_map[model])
            y_cursor = y0 - 1
            if y_cursor < plot_top:
                break

    max_x_label_width = max(
        (_text_dimensions(label, label_scale)[0] for label in data.bucket_labels),
        default=1,
    )
    max_x_labels = max(2, min(bucket_count, plot_width // max(1, max_x_label_width + 6)))
    tick_indices, tick_labels = _sample_ticks(
        data.bucket_labels,
        list(range(bucket_count)),
        max_x_labels,
    )
    tick_y = plot_bottom + 4
    for idx, label in zip(tick_indices, tick_labels):
        center_x = plot_left + int(round((idx + 0.5) * slot_width))
        _fill_rect(
            pixels,
            width,
            height,
            center_x,
            plot_bottom,
            center_x,
            min(height - 1, plot_bottom + 3),
            axis,
        )
        label_w, _ = _text_dimensions(label, label_scale)
        label_x = center_x - label_w // 2
        label_x = max(0, min(width - label_w - 1, label_x))
        _draw_text(
            pixels,
            width,
            height,
            label_x,
            tick_y,
            label,
            text_dim,
            label_scale,
        )

    x_axis_x = max(1, (width - x_axis_w) // 2)
    x_axis_y = min(height - x_axis_h - 1, tick_y + x_tick_h + 3)
    _draw_text(
        pixels,
        width,
        height,
        x_axis_x,
        x_axis_y,
        x_axis_label,
        text_main,
        label_scale,
    )
    return _encode_png_rgb(width, height, bytes(pixels))


def _send_kitty_png(png_data: bytes, columns: int, rows: int) -> None:
    payload = base64.standard_b64encode(png_data)
    chunk_size = 4096
    start = 0
    first = True
    out = sys.stdout.buffer
    while start < len(payload):
        end = min(start + chunk_size, len(payload))
        chunk = payload[start:end]
        start = end
        more = 1 if start < len(payload) else 0
        if first:
            header = f"\x1b_Ga=T,f=100,q=2,c={columns},r={rows},m={more};".encode("ascii")
            first = False
        else:
            header = f"\x1b_Gm={more};".encode("ascii")
        out.write(header)
        out.write(chunk)
        out.write(b"\x1b\\")
    out.flush()


def _render_kitty_chart(data: ChartData) -> None:
    term_size = shutil.get_terminal_size(fallback=(120, 40))
    display_cols = max(40, term_size.columns)
    display_rows = max(12, min(30, max(12, term_size.lines - 10)))
    image_width = min(3200, max(960, display_cols * 14))
    image_height = min(1800, max(420, display_rows * 30))
    color_map = _model_colors_rgb(data.models)
    png_data = _build_kitty_chart_png(data, color_map, image_width, image_height)

    print()
    sys.stdout.flush()
    _send_kitty_png(png_data, display_cols, display_rows)
    sys.stdout.flush()
    print("\n".join(_legend_lines(data.models, color_map)))


def _render_plotext_chart(data: ChartData) -> None:
    try:
        import plotext as plt
    except ImportError:
        print("plotext not installed; skipping chart.", file=sys.stderr)
        return

    color_map = _model_colors_plotext(data.models)
    legend_lines = ["", "Legend:"]
    for model in data.models:
        color = color_map[model]
        legend_lines.append(f"{plt.colorize('■', color)} {plt.colorize(model, color)}")

    plt.clear_figure()
    plt.title(data.chart_title)
    plt.xlabel("Time" if data.mode == "hourly" else "Date")
    term_width, term_height = plt.terminal_size()
    if term_width and term_height:
        target_height = max(10, min(term_height, term_width // 4))
        plt.plotsize(term_width, target_height)

    x_positions = list(range(len(data.bucket_labels)))
    stacked_values = [
        [value / data.scale_div for value in data.series[model]] for model in data.models
    ]
    plt.stacked_bar(
        x_positions,
        stacked_values,
        color=[color_map[model] for model in data.models],
    )
    if data.bucket_labels:
        if term_width:
            label_len = max(len(label) for label in data.bucket_labels)
            max_labels = max(2, term_width // max(1, label_len + 2))
        else:
            max_labels = 6
        tick_positions, tick_labels = _sample_ticks(
            data.bucket_labels,
            x_positions,
            max_labels,
        )
        plt.xticks(tick_positions, tick_labels)
    print("\n".join(legend_lines))
    plt.show()


def render_chart(
    records: Iterable[Record],
    chart_models: Optional[List[str]],
    chart_top: int,
    mode: str,
) -> None:
    data = _prepare_chart_data(records, chart_models, chart_top, mode)
    if data is None:
        return

    if os.getenv("TMUX"):
        if os.getenv("VIBEFETCH_CHART_BACKEND", "auto").strip().lower() == "kitty":
            print(
                "tmux detected: kitty high-res backend is disabled in tmux; "
                "using plotext fallback.",
                file=sys.stderr,
            )
        _render_plotext_chart(data)
        return

    backend = _select_chart_backend()
    if backend == "kitty":
        try:
            _render_kitty_chart(data)
            return
        except Exception as exc:  # noqa: BLE001
            print(
                f"High-res kitty chart renderer failed ({exc}); using plotext fallback.",
                file=sys.stderr,
            )
    _render_plotext_chart(data)
