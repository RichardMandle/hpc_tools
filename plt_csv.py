#!/usr/bin/env python3

import argparse
import numpy as np
import matplotlib.pyplot as plt
import os

def plot_csv(args):
    """Read a CSV file, extract header info, and plot the data."""
    # read the header line from the file and split it into column names.
    with open(args.input, 'r') as f:
        header_line = f.readline().strip()
        headers = [h.strip() for h in header_line.split(',')]
    
    # read the numerical data, skipping the header.
    data = np.genfromtxt(args.input, delimiter=",", skip_header=1, invalid_raise=False)

    if data.ndim == 1:  # Single-column case
        x_data = np.arange(len(data))  # Use index as X-axis
        y_data = [data]  # Treat as a single series
        # use the header if available: assume the single header is for Y.
        xlabel = "Index"
        ylabel = headers[0] if headers else "Y-axis"
        legend_labels = None
    else:
        x_data = data[:, 0]
        y_data = [data[:, i] for i in range(1, data.shape[1])]
        # if multiple columns, assume the first header is for X and the rest for Y series.
        xlabel = args.xlabel if args.xlabel is not None else (headers[0] if headers else "X-axis")
        # if only one Y series, use header[1] (if available) as ylabel;
        # otherwise, for multiple Y series, we let the legend handle their names.
        if len(y_data) == 1:
            ylabel = args.ylabel if args.ylabel is not None else (headers[1] if len(headers) > 1 else "Y-axis")
            legend_labels = None
        else:
            ylabel = args.ylabel if args.ylabel is not None else "Y-axis"
            # if the header has enough entries, use them as labels; otherwise fall back to default names.
            legend_labels = headers[1:] if len(headers) >= len(y_data) + 1 else None

    plt.figure(figsize=(8, 6))

    # Plot each Y series.
    for i, y in enumerate(y_data):
        if legend_labels and i < len(legend_labels):
            label = legend_labels[i]
        else:
            label = f"Series {i + 1}"
        plt.plot(x_data, y, label=label)

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    # use the provided title if any; otherwise, default to the file name.
    plt.title(args.title if args.title else os.path.basename(args.input))
    if len(y_data) > 1:
        plt.legend()
    plt.grid(True)
    plt.show()

def main():
    parser = argparse.ArgumentParser(description="Plot CSV data.")
    parser.add_argument("-i", "--input", required=True, help="Input CSV file")
    parser.add_argument("-x", "--xlabel", required=False, help="Custom X-axis label")
    parser.add_argument("-y", "--ylabel", required=False, help="Custom Y-axis label")
    parser.add_argument("-t", "--title", required=False, help="Custom title")
    args = parser.parse_args()

    plot_csv(args)

if __name__ == "__main__":
    main()
