#!/bin/bash

# parse the argments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -i|--input)
      INPUT_FILE="$2"
      shift 2
      ;;
    -o|--output)
      OUT_FILE="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done
echo "Input file : $INPUT_FILE"

# if no -o option provided, guess that we want inpu_file.mol2 basically (losing .gjf)
if [[ -z "$INPUT_FILE" ]]; then
    echo "Usage: $0 -i input.log [-o output.mol2]"
    exit 1
fi

if [[ -z "$OUT_FILE" ]]; then
    base="${INPUT_FILE%.log}"
    OUT_FILE="${base}.mol2"
fi

echo "writing to: $OUT_FILE"

module add ambertools
echo "running Antechamber"
antechamber -i $INPUT_FILE -fi gout -o $OUT_FILE -fo mol2 -c resp -nc 0 -m 1 -rn MOL

echo "running Acpype"
acpype -i $OUT_FILE -c user

# clean up
rm ANTECHAMBER*
cd *.acpype/
rm ANTECHAMBER* *.mdp *.log posre* *_AC* *_CNS* *OPLS* *INF *pkl

# run gaff lcff script

base="${INPUT_FILE%.log}"
GMX_FILE="${base}_GMX"

python ~/py_files/gaff_lcff.py $GMX_FILE.itp
cd ..