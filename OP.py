import mdtraj as md
from mdtraj.utils import ensure_type 
import numpy as np
import argparse

def compute_Q_tensor(all_directors):
    """
    Compute the Q-tensor for each frame using the molecular directors.
    """
    all_directors = ensure_type(all_directors, dtype=np.float64, ndim=3,
                                name='directors', shape=(None, None, 3))
    Q_ab = np.zeros((all_directors.shape[0], 3, 3), dtype=np.float64)
    for n, directors in enumerate(all_directors):
        # Normalize each director vector
        normed_vectors = directors / np.linalg.norm(directors, axis=1)[:, np.newaxis]
        for vector in normed_vectors:
            Q_ab[n, 0, 0] += 3.0 * vector[0] * vector[0] - 1.0
            Q_ab[n, 0, 1] += 3.0 * vector[0] * vector[1]
            Q_ab[n, 0, 2] += 3.0 * vector[0] * vector[2]
            Q_ab[n, 1, 0] += 3.0 * vector[1] * vector[0]
            Q_ab[n, 1, 1] += 3.0 * vector[1] * vector[1] - 1.0
            Q_ab[n, 1, 2] += 3.0 * vector[1] * vector[2]
            Q_ab[n, 2, 0] += 3.0 * vector[2] * vector[0]
            Q_ab[n, 2, 1] += 3.0 * vector[2] * vector[1]
            Q_ab[n, 2, 2] += 3.0 * vector[2] * vector[2] - 1.0
    Q_ab /= (2.0 * all_directors.shape[1])
    return Q_ab

def compute_order_parameters(all_directors, Q_ab):
    """
    For each frame, determine the overall director from Q_ab (eigenvector corresponding
    to the maximum eigenvalue) and compute the order parameters P1, P2, P3, P4 by averaging
    the Legendre polynomials of the cosine of the angle between each molecular director and
    the overall director.
    """
    n_frames = all_directors.shape[0]
    n_molecules = all_directors.shape[1]
    
    P1 = np.empty(n_frames, dtype=np.float64)
    P2 = np.empty(n_frames, dtype=np.float64)
    P3 = np.empty(n_frames, dtype=np.float64)
    P4 = np.empty(n_frames, dtype=np.float64)
    
    for i in range(n_frames):
        # Compute eigen-decomposition of Q for the frame; use eigh since Q is symmetric.
        eigenvalues, eigenvectors = np.linalg.eigh(Q_ab[i])
        max_index = np.argmax(eigenvalues)
        global_director = eigenvectors[:, max_index]
        # Normalize the global director
        global_director /= np.linalg.norm(global_director)
        
        # Compute cos(theta) for each molecule in frame i:
        # (Assuming each director in all_directors is already normalized)
        cos_thetas = np.dot(all_directors[i], global_director)
        
        # Compute the Legendre polynomial averages:
        P1[i] = np.mean(cos_thetas)
        P2[i] = np.mean((3 * cos_thetas**2 - 1) / 2)
        P3[i] = np.mean((5 * cos_thetas**3 - 3 * cos_thetas) / 2)
        P4[i] = np.mean((35 * cos_thetas**4 - 30 * cos_thetas**2 + 3) / 8)
    
    return P1, P2, P3, P4

def main():
    parser = argparse.ArgumentParser(description='Calculate Liquid Crystalline Order Parameters')
    parser.add_argument('-traj', required=True, help='Input trajectory file')
    parser.add_argument('-top', required=True, help='Input topology file')
    parser.add_argument('-o', default='output', help='Output file prefix')
    args = parser.parse_args()

    # Load the trajectory
    traj = md.load(args.traj, top=args.top)

    # Determine number of atoms per molecule (assuming equal distribution among residues)
    molatms = int(traj.n_atoms / traj.n_residues)
    indices = [[n + x for x in range(molatms)] for n in range(0, traj.n_atoms, molatms)]

    # Compute the directors for each molecule in each frame
    all_directors = md.compute_directors(traj, indices)  # shape: (n_frames, n_molecules, 3)
    
    # Compute the Q-tensor for each frame
    Q_ab = compute_Q_tensor(all_directors)

    # Compute order parameters from the directors and Q-tensor
    P1, P2, P3, P4 = compute_order_parameters(all_directors, Q_ab)

    # Get simulation times (assumed stored in traj.time)
    times = traj.time  # e.g., in picoseconds

    # Save time and P2 into a CSV with a header
    data_P2 = np.column_stack((times, P2))
    header_P2 = "time,P2"
    np.savetxt(f'P2_{args.o}.csv', data_P2, delimiter=',', header=header_P2, comments='')

    # (Optional) Save the other order parameters with time stamps
    np.savetxt(f'P1_{args.o}.csv', np.column_stack((times, P1)), delimiter=',', header="time,P1", comments='')
    np.savetxt(f'P3_{args.o}.csv', np.column_stack((times, P3)), delimiter=',', header="time,P3", comments='')
    np.savetxt(f'P4_{args.o}.csv', np.column_stack((times, P4)), delimiter=',', header="time,P4", comments='')

if __name__ == '__main__':
    main()
