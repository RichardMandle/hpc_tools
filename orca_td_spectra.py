import numpy as np
import matplotlib.pyplot as plt
import re
import sys


'''
orca_td_spectra.py

Aims to simplify reading (and plotting) of properties from orca outputs.
we might read these from <<jobname>>.properties.txt; we might read from elsewhere

Currently its quite scripty but we'll make real code when it diversifies; I've 
tried to make this quite modular to faciliate this
'''

def parse_spectrum_file(filename):
    """
    adapted from https://github.com/radi0sus/orca_uv/blob/main/orca-uv.py#L161
    read the absorbance data from the opt file block
    """
    energylist = []
    intenslist = []
    found_uv_section = False

    try:
        with open(filename, "r") as input_file:
            for line in input_file:

                if 'ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS' in line:
                    found_uv_section = True
                    for line in input_file:
                        if 'ABSORPTION SPECTRUM VIA TRANSITION VELOCITY DIPOLE MOMENTS' in line:
                            break
                        if re.search(r"\d\s+\d", line):  # line starts with "0-1 -> 1-1"
                            parts = line.strip().split()

                            try:
                                energylist.append(float(parts[3]))
                                intenslist.append(float(parts[6]))
                            except (IndexError, ValueError):
                                continue

        if not found_uv_section:
            raise ValueError("No absorption spectrum block found in file.")
        return np.array(list(zip(energylist, intenslist)))

    except IOError:
        print(f"'{filename}' not found")
        sys.exit(1)


# these microfunctions just return a lineshape for peak synthesis (do we need more?)
def gaussian(x, mu, fwhm):
    sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
    return np.exp(-0.5 * ((x - mu) / sigma) ** 2)

def lorentzian(x, mu, fwhm):
    gamma = fwhm / 2
    return 1 / (1 + ((x - mu) / gamma) ** 2)



# stuff pertaining to spectra
def build_spectrum(excitations, fwhm=1, shape='gaussian', xunit='nm', start = 2.0, end = 30.0, pts = 2500):
    """
    The actual spectrum making part:
    
    excitations: array of (energy in eV, oscillator strength)
    x_range: np.array of x values (e.g., energy or wavelength)
    shape: 'gaussian' or 'lorentzian'
    fwhm will be converted to nm if needed, or in ev as 
    """
    
    x_eV = np.linspace(start, end, pts)
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

def super_basic_plotter(x_data, y_data, x_label, y_label, osc_data = None,
    shape=None, xunit='eV', yunit='intensity / arb',
    color='r', xlim=None, ylim=None, dpi=100, figsize=(4, 2),
    title=None, legend=None, saveas=None,  show=True):
    """
    just expose and elaborate plt.plot in mpl for plotting.
    intended for this for any x/y data.

    - shape: optional label (not a function)
    - saveas: if given, save the figure to this filename (e.g., 'spectrum.png')
    - legend: optional string or list
    """
    plt.figure(figsize=figsize, dpi=dpi)
    plt.plot(x_data, y_data, color=color, label=legend)

    plt.xlabel(f"{x_label} ({xunit})" if xunit else x_label)
    plt.ylabel(f"{y_label} ({yunit})" if yunit else y_label)
    
    if osc_data is not None:
        # if --pltosc, plot the individual oscilators as a bar
        x, y = osc_data[:,0], osc_data[:,1]
        if xunit == 'nm':
            x = 1239.84 / x # convert to nm
        plt.bar(x, y, color = 'k', label = 'oscilator')
      
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
        
# parse arguments
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Plot ORCA absorption spectrum from .properties.txt")
    parser.add_argument("input", help="Path to ORCA .properties.txt file")
    parser.add_argument("--fwhm", type=float, default=1, help="FWHM in eV for lineshape broadening")
    parser.add_argument("--shape", choices=["gaussian", "lorentzian"], default="gaussian", help="Lineshape function")
    parser.add_argument("--xunit", choices=["eV", "nm"], default="nm", help="X-axis unit")
    parser.add_argument("--xlim", nargs=2, type=float, help="X-axis limits (e.g., --xlim 2.0 5.0)")
    parser.add_argument("--pltosc", action='store_true', help="plot the individual oscillators")
    parser.add_argument("--save", help="Filename to save the plot (e.g., spectrum.png)")
    
    args = parser.parse_args()

    try:
        excitations = parse_spectrum_file(args.input)
    except Exception as e:
        print(f"***ERROR***\n{e}\n")
        exit(1)
    
    # X values always in eV
    x_plot, spectrum = build_spectrum(excitations, fwhm=args.fwhm, shape=args.shape, xunit=args.xunit)

    if args.xunit == 'nm':
        x_label = "Wavelength"
    else:
        x_label = "Energy"

    super_basic_plotter(
        x_plot,
        spectrum,
        x_label=x_label,
        y_label="Absorption",
        xunit=args.xunit,
        yunit="a.u.",
        color='blue',
        xlim=args.xlim,
        title="Simulated Absorption Spectrum",
        saveas=args.save,
        show=not args.save,
        osc_data = excitations if args.pltosc else None)
        

if __name__ == "__main__":
    main()
