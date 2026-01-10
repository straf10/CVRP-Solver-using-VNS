import argparse
import os
import sys
import random
import time

try:
    from CVRP_Instance import CVRPInstance
    from vns_solver import VNSSolver

    # Προαιρετικά: Import για plotting αν θέλουμε να το καλούμε από εδώ
    try:
        from plotter import plot_solution

        HAS_PLOTTER = True
    except ImportError:
        HAS_PLOTTER = False
except ImportError as e:
    print(f"Critical Error: Missing modules. {e}")
    sys.exit(1)


def read_bks(filepath):
    """Διαβάζει το Best Known Solution από το αρχείο .sol αν υπάρχει."""
    sol_path = filepath.replace(".vrp", ".sol")
    if not os.path.exists(sol_path):
        return None
    try:
        with open(sol_path, 'r') as f:
            for line in f:
                if "Cost" in line:
                    return float(line.strip().split()[-1])
    except:
        return None


def main():
    # 1. Ρύθμιση του Argument Parser
    parser = argparse.ArgumentParser(description="VNS Solver for CVRP")

    # Ορίσματα
    parser.add_argument("--instance", "-i", type=str, help="Path to the .vrp input file")
    parser.add_argument("--seed", "-s", type=int, default=42, help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--time", "-t", type=int, default=600, help="Max execution time in seconds (default: 600)")
    parser.add_argument("--iter", type=int, default=2000, help="Max iterations (default: 2000)")
    parser.add_argument("--plot", "-p", action="store_true", help="Visualize the solution at the end")

    args = parser.parse_args()

    # 2. Ρύθμιση Random Seed (Για επαναληψιμότητα)
    # Αυτό εξασφαλίζει ότι κάθε φορά που τρέχεις με seed=42, θα παίρνεις ΤΗΝ ΙΔΙΑ λύση.
    if args.seed is not None:
        random.seed(args.seed)
        print(f"-> Using Random Seed: {args.seed}")

    # 3. Επιλογή Αρχείου
    target_file = None

    if args.instance:
        # Περίπτωση Α: Ο χρήστης έδωσε path
        if os.path.exists(args.instance):
            target_file = args.instance
        else:
            print(f"Error: The file '{args.instance}' does not exist.")
            sys.exit(1)
    else:
        # Περίπτωση Β: Default συμπεριφορά (ψάξε στον φάκελο Instance)
        instance_folder = "Instances"
        if os.path.exists(instance_folder):
            files = [f for f in os.listdir(instance_folder) if f.endswith(".vrp")]
            if files:
                # Διάλεξε το πρώτο ή ένα συγκεκριμένο (π.χ. X-n101)
                target_file = os.path.join(instance_folder, files[0])
                # Αν θέλουμε να προτιμάμε το X-n101 αν υπάρχει:
                for f in files:
                    if "X-n101" in f:
                        target_file = os.path.join(instance_folder, f)
                        break
            else:
                print(f"Error: No .vrp files found in '{instance_folder}'.")
                sys.exit(1)
        else:
            print("Error: No instance provided and 'Instance' folder not found.")
            sys.exit(1)

    print(f"-> Solving Instance: {target_file}")
    print(f"-> Max Time: {args.time}s | Max Iter: {args.iter}")

    # 4. Εκτέλεση
    try:
        # Φόρτωση Instance
        inst = CVRPInstance(target_file)

        # Έλεγχος για BKS
        bks = read_bks(target_file)
        if bks:
            print(f"-> Best Known Solution (Benchmark): {bks}")

        # Επίλυση VNS
        solver = VNSSolver(inst, max_iterations=args.iter, max_seconds=args.time)
        solution = solver.solve()

        # 5. Αποτελέσματα
        print("\n" + "=" * 30)
        print("       FINAL RESULTS       ")
        print("=" * 30)
        print(f"Instance:   {inst.name}")
        print(f"Cost:       {solution.cost:.2f}")
        print(f"Vehicles:   {len(solution.routes)}")

        if bks:
            gap = ((solution.cost - bks) / bks) * 100
            print(f"Gap:        {gap:.2f}%")

        print("=" * 30)

        # 6. Plotting (Αν ζητήθηκε)
        if args.plot:
            if HAS_PLOTTER:
                print("Generating plot...")
                plot_solution(solution, title=f"{inst.name} (Cost: {solution.cost:.2f})")
            else:
                print("Warning: Plotter module not found or failed to load.")

    except Exception as e:
        print(f"\nAn error occurred during execution:\n{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()