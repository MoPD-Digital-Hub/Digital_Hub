"""Chart images for Word and PDF documents (PowerPoint gets native, editable charts)."""

import io
import logging

import matplotlib

matplotlib.use("Agg")
# It logs a line for every category axis drawn from strings ("2016", "2017").
logging.getLogger("matplotlib.category").setLevel(logging.WARNING)

from matplotlib import font_manager  # noqa: E402
from matplotlib import pyplot as plt  # noqa: E402

from ai.documents import design  # noqa: E402

_FONTS_READY = False
MAX_BARS = 15


def _fonts():
    """Noto Sans with Noto Sans Ethiopic as fallback, so Amharic labels render."""
    global _FONTS_READY
    if not _FONTS_READY:
        for path in design.FONTS_DIR.glob("*.ttf"):
            font_manager.fontManager.addfont(str(path))
        _FONTS_READY = True
    return ["Noto Sans", "Noto Sans Ethiopic"]


def _hex(colour):
    return "#" + colour


def series_of(chart):
    """[(name, labels, values)]: the chart's lines, or its one series."""
    if chart.get("series"):
        return [(s.get("name") or "", [str(p[0]) for p in s["points"]], [p[1] for p in s["points"]])
                for s in chart["series"] if s.get("points")]
    return [(chart.get("label") or "", [str(label) for label in chart["labels"]], list(chart["data"]))]


def png(chart, width_in=6.6, height_in=3.1):
    """The chart as PNG bytes."""
    family = _fonts()
    with plt.rc_context({
        "font.family": family, "font.size": 9, "axes.edgecolor": _hex(design.LINE),
        "axes.labelcolor": _hex(design.MUTED), "xtick.color": _hex(design.MUTED), "ytick.color": _hex(design.MUTED),
    }):
        figure, axis = plt.subplots(figsize=(width_in, height_in), dpi=200)
        lines = series_of(chart)
        numeric = [(n, lab, [v if isinstance(v, (int, float)) else None for v in val]) for n, lab, val in lines]
        if chart.get("type") == "bar" and len(numeric) == 1:
            name, labels, values = numeric[0]
            pairs = [(lab, v) for lab, v in zip(labels, values) if v is not None][:MAX_BARS]
            labels, values = [p[0] for p in pairs], [p[1] for p in pairs]
            if len(labels) > 6 or max((len(lab) for lab in labels), default=0) > 10:
                axis.barh(labels[::-1], values[::-1], color=_hex(design.TEAL), height=0.6)
                axis.grid(axis="x", color=_hex(design.LINE), linewidth=0.6)
                for y, value in enumerate(values[::-1]):
                    axis.text(value, y, f" {value:,.2f}".rstrip("0").rstrip("."), va="center", fontsize=8,
                              color=_hex(design.INK))
            else:
                axis.bar(labels, values, color=_hex(design.TEAL), width=0.6)
                axis.grid(axis="y", color=_hex(design.LINE), linewidth=0.6)
        else:
            for i, (name, labels, values) in enumerate(numeric):
                colour = _hex(design.SERIES_COLOURS[i % len(design.SERIES_COLOURS)])
                axis.plot(labels, values, color=colour, linewidth=2, marker="o", markersize=3.5, label=name)
            if len(numeric) > 1:
                axis.legend(frameon=False, fontsize=8, ncol=min(len(numeric), 4), loc="upper left")
            else:
                labels, values = numeric[0][1], numeric[0][2]
                last = next(((lab, v) for lab, v in zip(reversed(labels), reversed(values)) if v is not None), None)
                if last:
                    axis.annotate(f"{last[1]:,}", last, textcoords="offset points", xytext=(0, 7), ha="center",
                                  fontsize=8, color=_hex(design.TEAL_DARK), fontweight="bold")
            axis.grid(axis="y", color=_hex(design.LINE), linewidth=0.6)
            if len(numeric[0][1]) > 12:
                axis.tick_params(axis="x", labelrotation=45)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
        axis.set_axisbelow(True)
        figure.tight_layout()
        buffer = io.BytesIO()
        figure.savefig(buffer, format="png", facecolor="white")
        plt.close(figure)
    return buffer.getvalue()
