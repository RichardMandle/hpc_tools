import argparse
import os
import re
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt

def extract_route_sections(filepath):
    routes = []
    with open(filepath, 'r') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        if re.match(r'^\s*-{5,}\s*$', lines[i]):
            j = i + 1
            if j < len(lines) and lines[j].strip().startswith('#'):
                route_line = lines[j].strip().lstrip('#').strip()
                routes.append(route_line)
                i = j + 1  # skip the route line
            else:
                i += 1
        else:
            i += 1

        if len(routes) == 2:
            break

    if len(routes) == 1:
        return routes[0], None
    elif len(routes) >= 2:
        return routes[0], routes[1]
    else:
        return None, None

def imag_check(file_path):
    with open(file_path, 'r') as file:
        contents = file.read()
    if "Normal termination of Gaussian" not in contents:
        return False
    if "imaginary frequencies" in contents:
        return False
    return True

def read_tddft_data(file_path):
    spectra_data = {}
    with open(file_path, 'r') as file:
        contents = file.read()
    tddft_start = contents.find('Excitation energies and oscillator strengths:')
    tddft_end = contents.find('SavETr:')
    if tddft_start != -1 and tddft_end != -1:
        tddft_wavelength = []
        tddft_strengths = []
        tddft_section = contents[tddft_start:tddft_end].strip().split('\n')[2:-2]
        for line in tddft_section:
            if 'Excited State' in line:
                floats = re.findall(r"\d+\.\d+", line)
                if len(floats) >= 3:
                    tddft_wavelength.append(floats[1])
                    tddft_strengths.append(floats[2])
        spectra_data['uv-vis'] = {
            'wavelengths': tddft_wavelength,
            'strengths': tddft_strengths
        }
        return spectra_data
    return None

def generate_uvvis_spectra(args, spectra_data):
    if 'uv-vis' not in spectra_data:
        return None, None
    uvvis_wavelength = np.array(spectra_data['uv-vis']['wavelengths'], dtype=float)
    uvvis_intensities = np.array(spectra_data['uv-vis']['strengths'], dtype=float)
    
    x = np.linspace(args.lmin, args.lmax, num=5000)
    y = np.zeros_like(x)
    
    for wavelength, intensity in zip(uvvis_wavelength, uvvis_intensities):
        gaussian = intensity * np.exp(-0.5 * ((x - wavelength) / (args.fwhm / 2.35482))**2)
        y += gaussian
    y = y / np.max(y) # normalise to zero
    return x, y

def get_lambda_max(x, y):
    max_idx = np.argmax(y)
    return x[max_idx], y[max_idx]
    
def extract_numeric_block_from_excel(args, sheet_name=0):
    df = pd.read_excel(args.exp_uvvis, sheet_name=sheet_name)
    df = df.dropna(how='all').dropna(axis=1, how='all')

    numeric_block = []

    for _, row in df.iterrows():
        try:
            floats = [float(val) for val in row if str(val).strip() != ""]
            if len(floats) == len(row):
                numeric_block.append(floats)
        except:
            continue

    return np.array(numeric_block)

def split_and_norm_spectra(numeric_array):
    # just return wavelenght and normalised absorbance
    return numeric_array[:, 0], numeric_array[:, 1] / np.max(numeric_array[:, 1])

def process_exp_uvvis_data(args, numeric_array):
    wavelengths, absorbance = split_and_norm_spectra(numeric_array)

    smoothed_absorbance = savgol_filter(absorbance, window_length=args.window, polyorder=args.porder)
    for n in [0.125, 0.1, 0.075, 0.05, 0.025]:
        smoothed_absorbance[smoothed_absorbance <= n] = 0 # remove low intensity stuff
        smoothed_absorbance = savgol_filter(smoothed_absorbance, window_length=args.window, polyorder=args.porder)

    smoothed_absorbance[smoothed_absorbance < 0] = 0 # remove low intensity stuff
    smoothed_absorbance = smoothed_absorbance / np.max(smoothed_absorbance)
    return smoothed_absorbance
    
def plot_data(args, numeric_array, smoothed_absorbance):
    wavelengths, absorbance = split_and_norm_spectra(numeric_array)
    
    plt.figure(figsize=(6, 4))
    plt.plot(wavelengths, absorbance, label='Raw', alpha=0.6)
    plt.plot(wavelengths, smoothed_absorbance, label='Smoothed (S-G)', linewidth=2)
    plt.xlabel('Wavelength (nm)')
    plt.ylabel('Absorbance')
    plt.title('UV-vis Spectrum: Raw vs Smoothed')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_overlaid_spectra(args, x, y, numeric_array, td_data, td_route):
    wavelengths, absorbance = split_and_norm_spectra(numeric_array)

    filename = f"{td_route.replace('/','_').replace('=',' ')}_overlaid_{(args.input).split('.')[0]}.png"

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(wavelengths, absorbance, label='Experimental UV-VIS', alpha=0.6)
    ax.plot(x, y, label=f"{td_route.replace(' ','\n')}", linewidth=2)

    if args.osc:
        osc_wl = np.array(td_data['uv-vis']['wavelengths'], dtype=float)
        osc_i = np.array(td_data['uv-vis']['strengths'], dtype=float)
        osc_i = osc_i / np.max(osc_i) # normalise to unity like we do for the spectra....
        
        ax.bar(osc_wl, osc_i, label="TD oscillator\nstrengths", alpha=0.3, color='green', width=5)

    ax.set_xlabel('Wavelength (nm)')
    ax.set_ylabel('Absorbance')
    ax.set_title('UV-vis Spectrum: Experiment vs TD-SCF')
    ax.legend()
    ax.grid(True)
    plt.tight_layout()

    os.makedirs("plots", exist_ok=True)
    fig.savefig(f"plots/{filename}")
    plt.close(fig)

def compare_calc_exp_spectra(args, x_tdscf, y_tdscf, numeric_array, smoothed_absorbance, td_data, td_route = None):
    wavelengths, absorbance = split_and_norm_spectra(numeric_array)
    
    exp_interp = interp1d(wavelengths, smoothed_absorbance, kind='linear', bounds_error=False, fill_value=0.0)
    exp_on_x_tdscf = exp_interp(x_tdscf) 
    
    exp_norm = exp_on_x_tdscf / np.max(exp_on_x_tdscf)
    tdscf_norm = y_tdscf / np.max(y_tdscf)
    
    mse = np.mean((exp_norm - tdscf_norm)**2)
    cos_sim = np.dot(exp_norm, tdscf_norm) / (np.linalg.norm(exp_norm) * np.linalg.norm(tdscf_norm))
    pearson_r = np.corrcoef(exp_norm, tdscf_norm)[0, 1]
    
    if args.verbose:
        print(f"MSE: {mse} \nCosine {cos_sim} \nPearson {pearson_r}")
    
    if args.plot:
        print(f"Plotting spectrum for {td_route}") if args.verbose else None
        plot_overlaid_spectra(args, x_tdscf, y_tdscf, numeric_array, td_data, td_route)
    return mse, cos_sim, pearson_r
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True, help='The input filename (or part of the file name)')
    parser.add_argument('-e', '--exp_uvvis', required=True, help='The location of the experimental UV-vis data, in xlsx format')
    parser.add_argument('-f', '--fwhm', default=25, type=float, help='The FWHM to use in peak synthesis')
    parser.add_argument('-min', '--lmin', default=150, type=float, help='minimum wavelength for TD-SCF peak synthesis')
    parser.add_argument('-max', '--lmax', default=800, type=float, help='maximum wavelength for TD-SCF peak synthesis')
    parser.add_argument('-w', '--window', default=31, type=float, help='The size of the window used in the SG-smoothing process')
    parser.add_argument('-p', '--porder', default=3, type=float, help='The polynomial order used in the SG-smoothing process)')
    parser.add_argument('-plot', '--plot', action='store_true', help='turn on printing each individual plot (will overlay calculated and experimental spectra); will save to plots\\')
    parser.add_argument('-osc', '--osc', action='store_true', help='turn on plotting the individual oscilators onto the plot (only works if -plot is called!)')      
    parser.add_argument('-v', '--verbose', action='store_true', help='Print some extra output into the terminal') 
    
    args = parser.parse_args()

    exp_spectrum = extract_numeric_block_from_excel(args)
    smth_spectrum = process_exp_uvvis_data(args, exp_spectrum)
    #plot_data(args, exp_spectrum, smth_spectrum)

    files = [f for f in os.listdir('.') if args.input in f and f.endswith('.log')]
    data = []
    rejected = []

    for file in files:
        is_minimum = imag_check(file)
        if not is_minimum:
            rejected.append([file, "FAILED or IMAGINARY frequencies"])
            continue

        route_opt, route_td = extract_route_sections(file)
        td_data = read_tddft_data(file)
        if td_data:
            x, y = generate_uvvis_spectra(args, td_data)
            if x is not None and y is not None:
                print(f"\n{file}") if args.verbose else None
                mse, cos_sim, pearson_r = compare_calc_exp_spectra(args, x, y, exp_spectrum, smth_spectrum, td_data, route_td)
                data.append([file, route_opt, route_td, True, mse, cos_sim, pearson_r])

            else:
                rejected.append([file, "Spectrum generation failed"])
        else:
            rejected.append([file, "No TD-DFT data found"])
    df = pd.DataFrame(data, columns=["filename", "opt route", "td route", "minimum geometry?", "MSE", "Cosine Similarity", "Pearson R"])
    output_file = f"uvvis_peak_shape_analysis_{args.input}.xlsx"
    df.to_excel(output_file, index=False)

    if rejected:
        df_rej = pd.DataFrame(rejected, columns=["filename", "reason"])
        reject_file = f"uvvis_rejected_{args.input}.xlsx"
        df_rej.to_excel(reject_file, index=False)
        print(f"Rejected jobs saved to {reject_file}")

    print(f"\nValid results saved to {output_file}")

if __name__ == "__main__":
    main()
