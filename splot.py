#!/usr/bin/env python3

'''
splot: a tiny command-line plotter for XVG/CSV/DAT files.
name: Simple PLOT; splot.

Some examples
--------
  splot -i energy.xvg -o energy.png

  splot -i run1/msd.xvg run2/msd.xvg --label-from dir -o msd_compare.png

  splot -i scan.dat --xcol 1 --ycols 2 -x "Angle / deg" -y "Energy / Eh"

  splot -i data.csv --ycols 2, 4-6 --rolling 5 --logy -o quick.png
'''

from __future__ import annotations
import argparse
import os
import re
import sys
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable
import numpy as np

@dataclass
class ParsedFile:
    path: str
    title: str
    xlabel: str
    ylabel: str
    legends: list[str]
    data: np.ndarray

def _is_float(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False

def _clean_label(text: str) -> str:
    '''
    cleanup of Grace/GROMACS-ish label escapes.
    this is deliberately minimal; splot is a quick HPC plotter and not a replacement for xmgrace!
    '''
    replacements = {
        r"\S": "^", 
        r"\N": "", 
        r"\s": "_", 
    }
    for old,  new in replacements.items():
        text = text.replace(old,  new)
    return text

def parse_xvg(path: str) -> ParsedFile:
    '''
    parse a .xvg file (from GROMACS,  GRACE etc)
    uses the same logic as plt_xvg.py (more or less)
    '''
    title = Path(path).stem
    xlabel = "X-axis"
    ylabel = "Y-axis"
    legend_by_index: dict[int,  str] = {}
    rows: list[list[float]] = []

    with open(path,  "r",  encoding="utf-8",  errors="replace") as f:
        for raw in f:
            line = raw.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            if line.startswith("@"):
                m = re.search(r'@\s+title\s+"(.*?)"',  line)
                if m:
                    title = _clean_label(m.group(1))
                    continue

                m = re.search(r'@\s+xaxis\s+label\s+"(.*?)"',  line)
                if m:

                    xlabel = _clean_label(m.group(1))
                    continue

                m = re.search(r'@\s+yaxis\s+label\s+"(.*?)"',  line)
                if m:
                    ylabel = _clean_label(m.group(1))
                    continue

                m = re.search(r'@\s+s(\d+)\s+legend\s+"(.*?)"',  line)
                if m:
                    legend_by_index[int(m.group(1))] = _clean_label(m.group(2))
                    continue
                continue

            # In grace,  "&" is a multidataset separator. Nobody is trying to plot that with
            # this simple tool (would be complex to handle),  so lets just skip it and print some warning
            if line.startswith("&"):
                print("Multidataset data detected: rather than using <<splot.py>> you'd be better off using xmgrace")
                continue

            try:
                rows.append([float(x) for x in line.split()])
            except ValueError:
                print(f"<< WARNING >> skipping non-numeric line in {path!r}: {line}",  file=sys.stderr)

    if not rows:
        raise ValueError(f"<< WARNING >> i found no numerical data found in {path!r}")

    ncols = len(rows[0])
    rows = [r for r in rows if len(r) == ncols]

    data = np.asarray(rows,  dtype=float)

    ny = max(data.shape[1] - 1,  0)
    legends = [legend_by_index.get(i,  f"Series {i + 1}") for i in range(ny)]

    return ParsedFile(path,  title,  xlabel,  ylabel,  legends,  data)


def _normalise_delimiter(delimiter: str | None,  fmt: str) -> str | None:
    if delimiter is None:
        if fmt == "csv":
            return ", "
        return None  # whitespace

    mapping = {
        "comma": ", ", 
        ", ": ", ", 
        "tab": "\t", 
        "\\t": "\t", 
        "space": None, 
        "whitespace": None, 
        "none": None, 
    }
    return mapping.get(delimiter.lower(),  delimiter)


def parse_table(path, fmt="csv", delimiter=None, no_header=False):
    '''
    Parse simple CSV or whitespace-delimited DAT/TXT tables.
    '''

    if delimiter is None:
        delim = "," if fmt == "csv" else None
    else:
        if delimiter in ["space", "whitespace"]:
            delim = None
        elif delimiter in ["tab", "\\t"]:
            delim = "\t"
        elif delimiter == "comma":
            delim = ","
        else:
            delim = delimiter

    headers = []
    data_lines = []
    first_data_ncols = None

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()

            if not line or line.startswith("#"):
                continue

            if delim is None:
                tokens = line.split()
            else:
                tokens = [x.strip() for x in line.split(delim)]

            # first non-comment line may be a header (skip with --no-header)
            if not data_lines and not headers and not no_header:
                looks_like_header = any(not _is_float(t) for t in tokens)

                if looks_like_header:
                    headers = tokens
                    continue

            if first_data_ncols is None:
                first_data_ncols = len(tokens)

            data_lines.append(line)

    if not data_lines:
        raise ValueError(f"<< WARNING >> found no numerical data in {path!r}")

    data_text = "\n".join(data_lines)

    data = np.genfromtxt(
        StringIO(data_text),
        delimiter=delim,
        autostrip=True,
        invalid_raise=False,
    )

    data = np.asarray(data, dtype=float)

    if data.ndim == 0:
        data = data.reshape(1, 1)

    elif data.ndim == 1:
        if first_data_ncols == 1:
            data = data.reshape(-1, 1)
        else:
            data = data.reshape(1, first_data_ncols)

    if data.shape[1] == 1:
        xlabel = "Index"
        ylabel = headers[0] if headers else "Y-axis"
        legends = [ylabel]

    else:
        xlabel = headers[0] if len(headers) >= 1 else "X-axis"

        if len(headers) == 2:
            ylabel = headers[1]
        else:
            ylabel = "Y-axis"

        if len(headers) >= data.shape[1]:
            legends = headers[1:]
        else:
            legends = [f"Series {i}" for i in range(1, data.shape[1])]

    return ParsedFile(
        path=path,
        title=Path(path).name,
        xlabel=xlabel,
        ylabel=ylabel,
        legends=legends,
        data=data,
    )


def infer_format(path, forced="auto"):
    if forced != "auto":
        return forced

    ext = Path(path).suffix.lower()

    if ext == ".xvg":
        return "xvg"

    if ext == ".csv":
        return "csv"

    if ext in [".dat", ".txt", ".xy"]:
        return "dat"

    return "dat"


def read_any(path, fmt="auto", delimiter=None, no_header=False):
    fmt = infer_format(path, fmt)

    if fmt == "xvg":
        return parse_xvg(path)

    if fmt == "csv":
        return parse_table(path, fmt="csv", delimiter=delimiter, no_header=no_header)

    if fmt == "dat":
        return parse_table(path, fmt="dat", delimiter=delimiter, no_header=no_header)

    raise ValueError(f"Unknown format: {fmt}")


def default_label(path: str,  mode: str) -> str:
    path_obj = Path(os.path.normpath(path))

    if mode == "file":
        return path_obj.name

    if mode == "stem":
        return path_obj.stem

    parent = path_obj.parent.name
    return parent if parent else path_obj.name


def parse_column_spec(spec: str | None,  ncols: int,  default_start: int = 2) -> list[int]:
    """
    Parse one-based column specs,  returning zero-based indices.

    Examples
    --------
    "2"      -> column 2
    "2, 4"    -> columns 2 and 4
    "2-5"    -> columns 2,  3,  4,  5
    "2:"     -> columns 2 to end
    """
    if ncols <= 0:
        return []

    if spec is None:
        if ncols > 1:
            return list(range(default_start - 1,  ncols))
        return [0]

    indices: list[int] = []

    for part in spec.split(", "):
        part = part.strip()

        if not part:
            continue

        if part.endswith(":"):
            start = int(part[:-1])
            indices.extend(range(start - 1,  ncols))

        elif "-" in part:
            start,  stop = [int(x) for x in part.split("-",  1)]
            indices.extend(range(start - 1,  stop))

        else:
            indices.append(int(part) - 1)

    bad = [i + 1 for i in indices if i < 0 or i >= ncols]
    if bad:
        raise ValueError(f"Column(s) out of range for {ncols}-column file: {bad}")

    # preserve order while removing duplicates
    return list(dict.fromkeys(indices))


def moving_average(y: np.ndarray,  window: int) -> np.ndarray:
    if window <= 1:
        return y

    if window > len(y):
        raise ValueError("--rolling cannot be larger than the number of data points")

    kernel = np.ones(window,  dtype=float) / window
    return np.convolve(y,  kernel,  mode="valid")


def common_output_name(paths: Iterable[str]) -> str:
    paths = list(paths)

    if len(paths) == 1:
        return f"{Path(paths[0]).stem}.png"

    return "plot.png"


def plot_files(args) -> None:
    import matplotlib.pyplot as plt

    if args.labels and len(args.labels) != len(args.input):
        raise SystemExit(
            f"--labels count ({len(args.labels)}) must match number of inputs ({len(args.input)})"
        )

    fig,  ax = plt.subplots(figsize=(args.figsize[0],  args.figsize[1]))

    first: ParsedFile | None = None
    plotted = 0

    for file_index,  path in enumerate(args.input):
        parsed = read_any(path,  args.format,  args.delimiter,  args.no_header)

        if first is None:
            first = parsed

        data = parsed.data

        if data.shape[1] == 1:
            x = np.arange(data.shape[0],  dtype=float)
            ycols = [0]

        else:
            xcol = args.xcol - 1

            if xcol < 0 or xcol >= data.shape[1]:
                raise SystemExit(
                    f"--xcol {args.xcol} is out of range for {path!r},  "
                    f"which has {data.shape[1]} columns"
                )

            x = data[:,  xcol]
            ycols = parse_column_spec(args.ycols,  data.shape[1])
            ycols = [c for c in ycols if c != xcol]

        x = x[:: args.every] * args.xscale + args.xshift

        base_label = args.labels[file_index] if args.labels else default_label(path,  args.label_from)

        for ycol in ycols:
            y = data[:,  ycol][:: args.every] * args.yscale + args.yshift

            if args.rolling > 1:
                y = moving_average(y,  args.rolling)
                x_plot = x[args.rolling - 1 :]
            else:
                x_plot = x

            if len(ycols) == 1:
                label = base_label

            else:
                legend_index = ycol - 1 if data.shape[1] > 1 else 0
                if 0 <= legend_index < len(parsed.legends):
                    col_label = parsed.legends[legend_index]
                else:
                    col_label = f"Column {ycol + 1}"

                label = f"{base_label}: {col_label}"

            if args.style == "scatter":
                ax.scatter(x_plot,  y,  label=label,  s=args.markersize**2)

            elif args.style == "both":
                ax.plot(x_plot,  y,  label=label,  marker="o",  markersize=args.markersize)

            else:
                ax.plot(x_plot,  y,  label=label)

            plotted += 1

    if plotted == 0:
        raise SystemExit("No data plotted.")

    xlabel = args.xlabel or (first.xlabel if first else "X-axis")
    ylabel = args.ylabel or (first.ylabel if first else "Y-axis")

    if args.title is not None:
        title = args.title
    elif len(args.input) == 1 and first:
        title = first.title
    else:
        title = " / ".join(Path(p).name for p in args.input)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    if title and not args.no_title:
        ax.set_title(title)

    if args.logx:
        ax.set_xscale("log")

    if args.logy:
        ax.set_yscale("log")

    if args.xlim:
        ax.set_xlim(args.xlim)

    if args.ylim:
        ax.set_ylim(args.ylim)

    if not args.no_grid:
        ax.grid(True,  alpha=0.3)

    if not args.no_legend and plotted > 1:
        ax.legend()

    elif not args.no_legend and args.force_legend:
        ax.legend()

    fig.tight_layout()

    out = args.out

    if out is None and not os.environ.get("DISPLAY") and os.name != "nt":
        out = common_output_name(args.input)
        print(f"No DISPLAY detected; saving to {out!r}",  file=sys.stderr)

    if out:
        fig.savefig(out,  dpi=args.dpi,  bbox_inches="tight")
        print(f"Saved {out}")

    else:
        plt.show()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "a small (s) plotter (plot) for .xvg,  CSV,  and whitespace .dat/.txt files. "
            "Columns are one-based."
        ), 
        formatter_class=argparse.ArgumentDefaultsHelpFormatter, 
    )

    p.add_argument("-i", "--input", required=True, nargs="+", help="Input file(s): .xvg,  .csv,  .dat,  .txt")
    p.add_argument("-f", "-if", "--format", choices=["auto",  "xvg",  "csv",  "dat"], default="auto", help="Force input format")
    p.add_argument("--delimiter", help="Delimiter for csv/dat: comma,  tab,  space,  or a literal delimiter")
    p.add_argument("--no-header", action="store_true", help="Treat first row of csv/dat as numerical data,  not a header")
    p.add_argument("--xcol", type=int, default=1, help="One-based x column for multi-column tables")
    p.add_argument("--ycols", default=None, help="One-based y columns,  e.g. 2,  2, 4,  2-5,  or 2:")
    p.add_argument("--every", type=int, default=1, help="Plot every Nth row")
    p.add_argument("--rolling", type=int, default=1, help="Simple moving average window")
    
    p.add_argument("-x",  "--xlabel",  help="Custom x-axis label")
    p.add_argument("-y",  "--ylabel",  help="Custom y-axis label")
    p.add_argument("-t",  "--title",  help="Custom title; use --no-title to suppress")
    p.add_argument("--no-title", action="store_true", help="Suppress title")
    p.add_argument("--labels", nargs="+", help="Legend labels,  one per input file")
    p.add_argument("--label-from", choices=["dir",  "file",  "stem"], default="dir", help="How to auto-label each input")
    p.add_argument("--no-legend", action="store_true", help="Disable legend")
    p.add_argument("--force-legend", action="store_true", help="Show legend even for one plotted series")
    p.add_argument("--style", choices=["line",  "scatter",  "both"], default="line", help="Plot style")
    p.add_argument("--markersize", type=float, default=4.0, help="Marker size for scatter/both styles")
    p.add_argument("--logx",  action="store_true",  help="Use log x-axis")
    p.add_argument("--logy",  action="store_true",  help="Use log y-axis")
    p.add_argument("--xlim", type=float, nargs=2, metavar=("MIN",  "MAX"), help="X-axis limits")

    p.add_argument("--ylim", type=float, nargs=2, metavar=("MIN",  "MAX"), help="Y-axis limits")

    p.add_argument("--xscale",  type=float,  default=1.0,  help="Multiply x values by this factor")
    p.add_argument("--yscale",  type=float,  default=1.0,  help="Multiply y values by this factor")
    p.add_argument("--xshift",  type=float,  default=0.0,  help="Add this to x values after scaling")
    p.add_argument("--yshift",  type=float,  default=0.0, help="Add this to y values after scaling")
    p.add_argument("--figsize",  type=float,  nargs=2,  default=(8.0,  6.0),  metavar=("W",  "H"),  help="Figure size in inches")
    p.add_argument("--dpi",  type=int,  default=300,  help="Output DPI")
    p.add_argument("--no-grid",  action="store_true",  help="Disable grid")
    p.add_argument("-o",  "--out",  help=("Save figure instead of showing it. If no DISPLAY is found,  defaults to <input_stem>.png"), 
    )

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.every < 1:
        raise SystemExit("--every must be >= 1")

    if args.rolling < 1:
        raise SystemExit("--rolling must be >= 1")

    # deliberately use a non-interactive backend on headless HPC nodes.
    if args.out or (not os.environ.get("DISPLAY") and os.name != "nt"):
        import matplotlib

        matplotlib.use("Agg")

    plot_files(args)


if __name__ == "__main__":
    main()
