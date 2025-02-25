#!/usr/bin/env python3

import argparse
import numpy as np
import matplotlib.pyplot as plt
import re
import os

def parse_xvg(file_path):
    """parses a gromacs .xvg file and extracts metadata and data."""
    title = "gromacs data"
    x_label = "x-axis"
    y_label = "y-axis"
    legends = []
    data = []

    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith("@"):
                # extract title
                if line.startswith('@    title'):
                    title_match = re.findall(r'"(.*?)"', line)
                    title = title_match[0] if title_match else "gromacs data"
                # extract x-axis label
                elif line.startswith('@    xaxis  label'):
                    x_label_match = re.findall(r'"(.*?)"', line)
                    x_label = x_label_match[0] if x_label_match else "x-axis"
                # extract y-axis label
                elif line.startswith('@    yaxis  label'):
                    y_label_match = re.findall(r'"(.*?)"', line)
                    y_label = y_label_match[0] if y_label_match else "y-axis"
                # extract legend labels
                elif line.startswith('@ s'):
                    match = re.findall(r'@ s\d+ legend "(.*?)"', line)
                    if match:
                        legends.append(match[0])
            elif line and not line.startswith(('#', '@')):
                # data line: split and convert to floats
                values = list(map(float, line.split()))
                data.append(values)

    if not data:
        raise ValueError("no numerical data found in the .xvg file.")

    data = np.array(data)
    
    # ensure we have enough legend entries
    if len(legends) < data.shape[1] - 1:
        legends += [f"series {i}" for i in range(len(legends), data.shape[1] - 1)]

    return title, x_label, y_label, legends, data

def plot_xvg(args):
    """reads an .xvg file and plots the data."""
    title, x_label, y_label, legends, data = parse_xvg(args.input)

    # override metadata with command-line arguments if provided
    if args.xlabel is not None:
        x_label = args.xlabel
    if args.ylabel is not None:
        y_label = args.ylabel
    if args.title is not None:
        title = args.title

    plt.figure(figsize=(8, 6))
    for i in range(1, data.shape[1]):  # skip first column (x-axis)
        plt.plot(data[:, 0], data[:, i], label=legends[i - 1])
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(title)
    if data.shape[1] > 2:  # if more than one y series, add legend
        plt.legend()
    plt.grid(True)
    plt.show()

def main():
    parser = argparse.ArgumentParser(description="plot gromacs .xvg files.")
    parser.add_argument("-i", "--input", required=True, help="input .xvg file")
    parser.add_argument("-x", "--xlabel", required=False, help="custom x-axis label")
    parser.add_argument("-y", "--ylabel", required=False, help="custom y-axis label")
    parser.add_argument("-t", "--title", required=False, help="custom title")
    args = parser.parse_args()

    plot_xvg(args)

if __name__ == "__main__":
    main()
