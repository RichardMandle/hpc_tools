import numpy as np
import matplotlib.pyplot as plt
import re
import sys
import glob
from pathlib import Path

'''
orca_td_spectra.py

Will plot a TD-SCF "uv-vis" spectra for:
- single ORCA .out file (as before)
- multiple conformer .out files, Boltzmann-weighted by SCF energy
- plotting only min-energy or first conformer

Usage examples:
    # single file (as before)
    python orca_td_spectra.py conf_000.out

    # many conformers: matches *conf*.out
    python orca_td_spectra.py conf

    # specify temperature, plot oscillators
    python orca_td_spectra.py conf --temperature 300 --pltosc

    # plot only minimum-energy conformer
    python orca_td_spectra.py conf --plt_min

    # plot only first conformer (e.g. conf_000.out)
    python orca_td_spectra.py conf --plt_first

    *** POSSIBLE WORKFLOW ***
    generate your structure with smi2xyz:
    python ~/py_files/smi2xyz.py -i "CCCCCC0CCC(C(=O)Oc1cc(F)c(c2cc(F)c(F)c(F)c2)cc1)CC0" -o wco1_22

    generate conformesr with GOAT / xyz2orca:
    python ~/py_files/xyz2orca.py -i wco1_22.xyz -o wco1_22.inp -cpu 16 -mem 4GB -m "GOAT GFN2-XTB"

    write the low energy ones to a new path (within 3 kcal mol of the minima)
    python ~/py_files/goat2orca.py -o wco1_22.out -x wco1_22.finalensemble.xyz -e 3 -w td_confs/

    setup a TD job at an appropriate level
    python ~/py_files/xyz2orca.py -all -cpu 1 -mem 4GB -m "r2scan-3c" -b "%tddft Nroots 10 end"

    Once done, get the synthesised spectra
    python orca_td_spec_multiconf.py conf_ -fwhm 0.3

'''


def parse_spectrum_and_energy(filename):
    """
    Read excitation energies / oscillator strengths and SCF energy
    from an ORCA .out file.

    Returns:
        excitations : np.array of shape (n, 2) -> (energy_eV, osc_strength)
        energy_Ha   : float, SCF energy in Hartree
    """
    energylist = []
    intenslist = []
    found_uv_section = False
    energy_Ha = None

    try:
        with open(filename, "r") as input_file:
            for line in input_file:
                # pick up final SCF energy in Ha in ORCA6.1 style
                if energy_Ha is None:
                    m = re.search(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)", line)
                    if m:
                        energy_Ha = float(m.group(1))
                    else:
                        # fallback to pattern used in older ORCA
                        m2 = re.search(r"TOTAL SCF ENERGY\s+(-?\d+\.\d+)", line)
                        if m2:
                            energy_Ha = float(m2.group(1))

                # look for TD section
                if 'ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS' in line:
                    found_uv_section = True
                    for line in input_file:
                        # ends here
                        if 'ABSORPTION SPECTRUM VIA TRANSITION VELOCITY DIPOLE MOMENTS' in line:
                            break
                        if re.search(r"\d\s+\d", line):  # line starts with "0-1 -> 1-1"
                            parts = line.strip().split()
                            try:
                                energylist.append(float(parts[3]))   # eV
                                intenslist.append(float(parts[6]))   # f
                            except (IndexError, ValueError):
                                continue

        if not found_uv_section:
            raise ValueError(f"No absorption spectrum block found in file '{filename}'.")

        if energy_Ha is None:
            raise ValueError(f"Could not find SCF energy in file '{filename}'.")

        excitations = np.array(list(zip(energylist, intenslist)))
        return excitations, energy_Ha

    except IOError:
        print(f"'{filename}' not found")
        sys.exit(1)


# lineshape functions
def gaussian(x, mu, fwhm):
    sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
    return np.exp(-0.5 * ((x - mu) / sigma) ** 2)


def lorentzian(x, mu, fwhm):
    gamma = fwhm / 2
    return 1 / (1 + ((x - mu) / gamma) ** 2)


def build_spectrum(excitations, fwhm=1, shape='gaussian', xunit='nm',
                   start=2.0, end=30.0, pts=2500, x_grid=None):
    """
    The actual spectrum making part of the code:

    excitations: array of (energy in eV, oscillator strength)
    shape: 'gaussian' or 'lorentzian'
    fwhm in eV
    xunit: 'eV' or 'nm'
    If x_grid is provided (in eV), it is used instead of start/end/pts.
    """
    if x_grid is None:
        x_eV = np.linspace(start, end, pts)
    else:
        x_eV = np.array(x_grid)

    y = np.zeros_like(x_eV)

    for energy, strength in excitations:
        if shape == 'gaussian':
            y += strength * gaussian(x_eV, energy, fwhm)
        elif shape == 'lorentzian':
            y += strength * lorentzian(x_eV, energy, fwhm)
        else:
            raise ValueError("Invalid lineshape")

    if xunit == 'nm':
        x_nm = 1239.84 / x_eV
        return x_nm[::-1], y[::-1]
    else:
        return x_eV, y


def super_basic_plotter(x_data, y_data, x_label, y_label, osc_data=None,
                        shape=None, xunit='eV', yunit='intensity / arb',
                        color='r', xlim=None, ylim=None, dpi=100, figsize=(4, 2),
                        title=None, legend=None, saveas=None, show=True):
    """
    Very simple wrapper around plt.plot for x-y data.

    - osc_data: optional (n,2) array of (energy_eV, strength) for vertical bars.
    """
    plt.figure(figsize=figsize, dpi=dpi)
    plt.plot(x_data, y_data, color=color, label=legend)

    plt.xlabel(f"{x_label} ({xunit})" if xunit else x_label)
    plt.ylabel(f"{y_label} ({yunit})" if yunit else y_label)

    if osc_data is not None:
        x, y = osc_data[:, 0], osc_data[:, 1]
        if xunit == 'nm':
            x = 1239.84 / x  # convert to nm
        plt.bar(x, y, color='k', label='oscillator', alpha=0.4)

    if title:
        plt.title(title)

    if xlim:
        plt.xlim(xlim)
    if ylim:
        plt.ylim(ylim)

    if legend:
        plt.legend()

    plt.grid(True)
    plt.tight_layout()

    if saveas:
        plt.savefig(saveas, dpi=dpi)
        print(f"Saved plot to: {saveas}")
    if show:
        plt.show()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Plot ORCA absorption spectrum from .out\n\n"
            "If the positional argument is a file, runs on that file only.\n"
            "Otherwise, treats it as a stub and matches *STUB*out."
        )
    )

    parser.add_argument("input", help="Path to ORCA .out file, or stub for multiple files")
    parser.add_argument("-fwhm", type=float, default=1.0,
                        help="FWHM in eV for lineshape broadening")
    parser.add_argument("-shape", choices=["gaussian", "lorentzian"],
                        default="gaussian", help="Lineshape function")
    parser.add_argument("-xunit", choices=["eV", "nm"], default="nm",
                        help="X-axis unit")
    parser.add_argument("-xlim", nargs=2, type=float,
                        help="X-axis limits (e.g., --xlim 2.0 5.0)")
    parser.add_argument("-pltosc", action='store_true',
                        help="Plot the individual oscillators as vertical bars")
    parser.add_argument("-save", help="Filename to save the plot (e.g., spectrum.png)")
    parser.add_argument("-temperature", type=float, default=298.15,
                        help="Temperature (K) for Boltzmann weighting of conformers")
    parser.add_argument("-no_boltz", action='store_true',
                        help="Disable Boltzmann weighting (use equal weights for all conformers)")
    parser.add_argument("-plt_min", action='store_true',
                        help="Plot the spectrum of the minimum-energy conformer")
    parser.add_argument("-plt_first", action='store_true',
                        help="Plot the spectrum of the first conformer (sorted list)")

    args = parser.parse_args()

    if args.plt_min and args.plt_first:
        print("Error: -plt_min and -plt_first are mutually exclusive.")
        sys.exit(1)

    path = Path(args.input)

    # single-file mode
    if path.is_file():
        try:
            excitations, energy_Ha = parse_spectrum_and_energy(str(path))
        except Exception as e:
            print(f"***ERROR***\n{e}\n")
            sys.exit(1)

        x_plot, spectrum = build_spectrum(
            excitations,
            fwhm=args.fwhm,
            shape=args.shape,
            xunit=args.xunit
        )

        x_label = "Wavelength" if args.xunit == 'nm' else "Energy"
        title = f"Simulated Absorption Spectrum\n{path.name}"

        super_basic_plotter(
            x_plot,
            spectrum,
            x_label=x_label,
            y_label="Absorption",
            xunit=args.xunit,
            yunit="a.u.",
            color='blue',
            xlim=args.xlim,
            title=title,
            saveas=args.save,
            show=not args.save,
            osc_data=excitations if args.pltosc else None
        )
        return
        
    # look for files with pattern, read them, multiconformer mode.
    pattern = f"*{args.input}*.out"
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"No files found matching pattern '{pattern}'")
        sys.exit(1)

    print("Found the following output files:")
    for f in files:
        print(f"  {f}")

    excitations_list = []
    energies_Ha = []

    for f in files:
        try:
            ex, eHa = parse_spectrum_and_energy(f)
            excitations_list.append(ex)
            energies_Ha.append(eHa)
        except Exception as e:
            print(f"Skipping '{f}': {e}")

    if not excitations_list:
        print("No valid excitation data found.")
        sys.exit(1)

    energies_Ha = np.array(energies_Ha)
    Ha_to_kJmol = 2625.5
    E_min = energies_Ha.min()
    dE_kJ = (energies_Ha - E_min) * Ha_to_kJmol

    if args.no_boltz:
        #if no_boltz (no Botlzmann) don't bother with weights.
        weights = np.ones_like(dE_kJ) / len(dE_kJ)
    
    else:
        R = 8.314462618 
        beta = 1000.0 / (R * args.temperature) 
        weights = np.exp(-dE_kJ * beta)
        weights /= weights.sum()

    print("\nConformer energies and weights:")
    for fname, E, dE, w in zip(files, energies_Ha, dE_kJ, weights):
        print(f"{fname:30s}  E = {E: .6f} Ha   dE = {dE:7.3f} kJ/mol   w = {w: .4f}")

    x_label = "Wavelength" if args.xunit == 'nm' else "Energy"

    # Plot only min-energy conformer
    if args.plt_min:
        idx_min = int(np.argmin(energies_Ha))
        ex_min = excitations_list[idx_min]
        fname_min = files[idx_min]

        x_plot, spectrum = build_spectrum(
            ex_min,
            fwhm=args.fwhm,
            shape=args.shape,
            xunit=args.xunit
        )

        title = f"Absorption spectrum\n(min-energy conformer: {Path(fname_min).name})"

        super_basic_plotter(
            x_plot,
            spectrum,
            x_label=x_label,
            y_label="Absorption",
            xunit=args.xunit,
            yunit="a.u.",
            color='blue',
            xlim=args.xlim,
            title=title,
            saveas=args.save,
            show=not args.save,
            osc_data=ex_min if args.pltosc else None
        )
        return

    # Plot only first conformer in list
    if args.plt_first:
        idx_first = 0
        ex_first = excitations_list[idx_first]
        fname_first = files[idx_first]

        x_plot, spectrum = build_spectrum(
            ex_first,
            fwhm=args.fwhm,
            shape=args.shape,
            xunit=args.xunit
        )

        title = f"Absorption spectrum\n(first conformer: {Path(fname_first).name})"

        super_basic_plotter(
            x_plot,
            spectrum,
            x_label=x_label,
            y_label="Absorption",
            xunit=args.xunit,
            yunit="a.u.",
            color='blue',
            xlim=args.xlim,
            title=title,
            saveas=args.save,
            show=not args.save,
            osc_data=ex_first if args.pltosc else None
        )
        return

    # Boltzmann-weighted spectrum over all conformers
    x_plot = None
    total_spectrum = None
    osc_all = []

    for ex, w in zip(excitations_list, weights):
        x_i, spec_i = build_spectrum(
            ex,
            fwhm=args.fwhm,
            shape=args.shape,
            xunit=args.xunit
        )
        if x_plot is None:
            x_plot = x_i
            total_spectrum = np.zeros_like(spec_i)
        else:
            if not np.allclose(x_plot, x_i):
                raise RuntimeError("X grids from build_spectrum do not match between conformers.")

        total_spectrum += w * spec_i

        if args.pltosc:
            ex_w = ex.copy()
            ex_w[:, 1] *= w
            osc_all.append(ex_w)

    osc_data = np.vstack(osc_all) if (args.pltosc and osc_all) else None

    title = f"Boltzmann-weighted absorption spectrum\n({len(excitations_list)} conformers)"

    super_basic_plotter(
        x_plot,
        total_spectrum,
        x_label=x_label,
        y_label="Absorption",
        xunit=args.xunit,
        yunit="a.u.",
        color='blue',
        xlim=args.xlim,
        title=title,
        saveas=args.save,
        show=not args.save,
        osc_data=osc_data
    )


if __name__ == "__main__":
    main()
