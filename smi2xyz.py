#!/usr/bin/env python3
''' 
smi2xyz.py
convert SMILES to 3D .xyz using RDKit; pick the minimum-energy conformer.



'''

import argparse
from pathlib import Path
import sys
from typing import List, Optional, Tuple

from rdkit import Chem
from rdkit.Chem import AllChem

def parse_args():
    p = argparse.ArgumentParser(
        description="Generate 3D geometries (.xyz) from SMILES with RDKit and write the lowest-energy conformer.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("-i", "--smiles", type=str, help="Single SMILES string.")
    g.add_argument("-f", "--smiles_file", type=Path, help="Text file with one SMILES per line. Lines starting with # are ignored.")

    p.add_argument("-o", "--output", type=str, required=True, help="Output .xyz filename (for single input) or filename prefix (for multi-input).")
    p.add_argument("-n", "--num_confs", type=int, default=50, help="Number of conformers to generate (default: 50).")
    p.add_argument("--rms", type=float, default=0.5, help="RMSD pruning threshold in ANGSTROM (default: 0.5).")
    p.add_argument("--seed", type=int, default=1, help="Random seed for embedding (default: 1).")

    p.add_argument("--embed", type=str, default="ETKDGv3", choices=["ETKDG", "ETKDGv2", "ETKDGv3"], help="Conformer embedding method (default: ETKDGv3)")
    p.add_argument("--opt", type=str, default="mmff", choices=["mmff", "uff"], help="Force field for optimization/energy (default: mmff).")

    p.add_argument("--e_thresh", type=float, default=None, help="Optional energy window (kcal/mol) relative to the minimum. Only conformers within this window are considered when picking the min. If omitted, all conformers are considered.")
    p.add_argument("--max_iter", type=int, default=200, help="Max FF optimization iterations per conformer (default: 200).")
    p.add_argument("--name", type=str, default=None, help="Optional name/comment to include in the XYZ title line for single-input mode.")
    return p.parse_args()

def read_smiles_lines(path: Path) -> List[str]:
    smiles_list = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            smiles_list.append(s.split()[0].split(",")[0])
    return smiles_list

def get_embed_params(method: str, seed: int, prune_rms: float):
    if method == "ETKDGv3" and hasattr(AllChem, "ETKDGv3"):
        params = AllChem.ETKDGv3() # we'll do this one because its the newest
    elif method == "ETKDGv2":
        params = AllChem.ETKDGv2()
    else:
        params = AllChem.ETKDG()  
    params.randomSeed = seed
    params.pruneRmsThresh = prune_rms
    params.useRandomCoords = False
    #params.maxAttempts = 1000
    return params

def optimize_and_energy(mol: Chem.Mol, opt: str, max_iter: int) -> Tuple[List[float], str]:
    """
    optimise all conformers; return energies (kcal/mol) and the FF used ("mmff" or "uff").
    falls back to UFF if MMFF props aren't available.
    
    This will fail for SF5 stuff and hypervalent things generally; use obabel for those
    """
    if opt == "mmff":
        props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94s")
        if props is not None:
            res = AllChem.MMFFOptimizeMoleculeConfs(mol, mmffVariant="MMFF94s", maxIters=max_iter)
            energies = [r[1] for r in res]  # its in kcal/mol
            return energies, "mmff"
        # fallback to UFF
        opt = "uff"

    if opt == "uff":
        res = AllChem.UFFOptimizeMoleculeConfs(mol, maxIters=max_iter)
        # UFF returns (converged(bool), energy)
        energies = [r[1] for r in res]  # again, kcal/mol
        return energies, "uff"

    raise RuntimeError("Unknown optimizer selected.")

def choose_min_conformer(energies: List[float], e_thresh: Optional[float]) -> int:
    '''
    logic here is to consider only conformers within some threshold of the minimum
    and then to return the global minimum UNLESS! there is a tie (shouldn't ever happen)
    '''
    if not energies:
        raise RuntimeError("No energies to select from.")
    emin = min(energies)
    if e_thresh is None:
        return energies.index(emin)
    candidates = [(i, e) for i, e in enumerate(energies) if (e - emin) <= e_thresh]
    i_best = min(candidates, key=lambda t: t[1])[0]
    return i_best

def mol_from_smiles(smiles: str) -> Optional[Chem.Mol]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    return mol

def embed_conformers(mol: Chem.Mol, params, num_confs: int) -> List[int]:
    ids = AllChem.EmbedMultipleConfs(mol, numConfs=num_confs, params=params)
    return list(ids)

def write_xyz(mol: Chem.Mol, conf_id: int, fname: Path, smiles: str, energy_kcal: float, ff_used: str, name: Optional[str]=None):
    conf = mol.GetConformer(conf_id)
    n = mol.GetNumAtoms()
    title_bits = [f"SMILES={smiles}", f"E={energy_kcal:.6f} kcal/mol", f"FF={ff_used}"]
    if name:
        title_bits.insert(0, name)
    title = " | ".join(title_bits)
    with fname.open("w", encoding="utf-8") as f:
        f.write(f"{n}\n{title}\n")
        for i, atom in enumerate(mol.GetAtoms()):
            pos = conf.GetAtomPosition(i)
            f.write(f"{atom.GetSymbol():<2} {pos.x: .8f} {pos.y: .8f} {pos.z: .8f}\n")

def process_one(smiles: str, out_path: Path, args, label: Optional[str]=None) -> bool:
    try:
        mol = mol_from_smiles(smiles)
        if mol is None:
            print(f"[WARN] Failed to parse SMILES: {smiles}", file=sys.stderr)
            return False

        params = get_embed_params(args.embed, args.seed, args.rms)
        conf_ids = embed_conformers(mol, params, args.num_confs)
        if not conf_ids:
            print(f"[WARN] Embedding failed for: {smiles}", file=sys.stderr)
            return False

        energies, ff_used = optimize_and_energy(mol, args.opt, args.max_iter)
        if len(energies) != len(conf_ids):
            print(f"[WARN] Energy list size mismatch for: {smiles}", file=sys.stderr)
            return False

        best_id = choose_min_conformer(energies, args.e_thresh)
        best_e = energies[best_id]

        write_xyz(mol, best_id, out_path, smiles, best_e, ff_used, name=label or args.name)
        print(f"[OK] Wrote {out_path} ({ff_used}, E={best_e:.4f} kcal/mol)")
        return True

    except Exception as e:
        print(f"[ERROR] {smiles}: {e}", file=sys.stderr)
        return False

def main():
    args = parse_args()

    # get smiles inputs in one place
    if args.smiles is not None:
        smiles_list = [args.smiles]
    else:
        smiles_list = read_smiles_lines(args.smiles_file)
        if not smiles_list:
            print("[ERROR] No SMILES found in file.", file=sys.stderr)
            sys.exit(1)

    # figure out if we are writing ONE output .xyz file, or if we need to write many (and so trigger multi...)
    out = args.output
    multi = len(smiles_list) > 1

    if not multi:
        out_path = Path(out)
        if out_path.suffix.lower() != ".xyz":
            out_path = out_path.with_suffix(".xyz")
        success = process_one(smiles_list[0], out_path, args, label=args.name)
        sys.exit(0 if success else 2)

    # so if we've got multiple files, lets set -o as a prefix and just whack numbers after it.
    prefix = out
    width = max(4, len(str(len(smiles_list))))
    successes = 0
    for idx, smi in enumerate(smiles_list, start=1):
        fname = f"{prefix}{idx:0{width}d}.xyz"
        if process_one(smi, Path(fname), args, label=None):
            successes += 1

    print(f"[DONE] {successes}/{len(smiles_list)} molecules succeeded.")
    sys.exit(0 if successes == len(smiles_list) else 3)

if __name__ == "__main__":
    main()
