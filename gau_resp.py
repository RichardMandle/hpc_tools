#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

# script for making gaussian jobs for RESP charges at the 
# B3LYP/6-31G(d,p) level

HEADER_REGEX = r"^(%.*\n)*#.*\n"


def extract_chk(text):
    """Extract existing %chk file name, or default to 'job.chk'."""
    m = re.search(r"%chk\s*=\s*(.+)", text)
    return m.group(1).strip() if m else "job.chk"


def build_new_header(chkfile, cpu, mem):
    """Build the new Gaussian header."""
    return (
        f"%mem={mem}\n"
        f"%nprocshared={cpu}\n"
        f"%chk={chkfile}\n"
        "#p b3lyp/6-31G(d,p) nosymm iop(6/33=2) pop(chelpg,regular)\n"
    )


def replace_header(text, new_header):
    """Replace existing Gaussian header block with new header."""
    if not re.search(HEADER_REGEX, text, flags=re.MULTILINE):
        raise ValueError("Could not find a valid Gaussian header block.")

    return re.sub(
        HEADER_REGEX,
        new_header,
        text,
        count=1,
        flags=re.MULTILINE
    )


def main():
    parser = argparse.ArgumentParser(
        description="Replace Gaussian header (%.. and #..) with a standard one."
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Input Gaussian .gjf file"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file (default: <input>.gjf)"
    )
    parser.add_argument(
        "-cpu", "--nproc",
        required=True,
        help="Number of CPU cores, e.g. 8"
    )
    parser.add_argument(
        "-mem", "--memory",
        required=True,
        help="Memory specification, e.g. 8GB, 16000MB"
    )

    args = parser.parse_args()

    infile = Path(args.input)
    outfile = Path(args.output) if args.output else infile.with_suffix("") .with_name(infile.stem + ".gjf")

    text = infile.read_text()

    chkfile = extract_chk(text)
    new_header = build_new_header(chkfile, args.nproc, args.memory)
    new_text = replace_header(text, new_header)

    outfile.write_text(new_text)
    print(f"? Wrote updated file to {outfile}")


if __name__ == "__main__":
    main()

