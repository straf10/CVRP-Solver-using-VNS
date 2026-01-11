import argparse
import os
import sys
import random
import time

try:
    from CVRP_Instance import CVRPInstance
    from vns_solver import VNSSolver
except ImportError as e:
    print(f"Critical Error: Missing modules. {e}")
    sys.exit(1)

# Optional Plotter Import (Assuming the file is named plotter.py)
try:
    from plotter import plot_solution

    HAS_PLOTTER = True
except ImportError:
    HAS_PLOTTER = False


def read_bks(filepath):
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
    parser = argparse.ArgumentParser(description="VNS Solver for CVRP")
    parser.add_argument("--instance", "-i", type=str, help="Path to the .vrp input file")
    parser.add_argument("--seed", "-s", type=int, default=42, help="Random seed")
    parser.add_argument("--time", "-t", type=int, default=600, help="Max execution time")
    parser.add_argument("--iter", type=int, default=2000, help="Max iterations")
    parser.add_argument("--plot", "-p", action="store_true", help="Visualize solution")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    target_file = args.instance
    if not target_file:
        if os.path.exists("Instances"):
            files = [f for f in os.listdir("Instances") if f.endswith(".vrp")]
            if files: target_file = os.path.join("Instances", files[0])

    if not target_file or not os.path.exists(target_file):
        print("Error: Invalid instance file.")
        sys.exit(1)

    print(f"-> Solving: {target_file}")

    try:
        inst = CVRPInstance(target_file)
        bks = read_bks(target_file)
        if bks: print(f"-> BKS: {bks}")

        solver = VNSSolver(inst, max_iterations=args.iter, max_seconds=args.time)
        solution = solver.solve()

        print("\n" + "=" * 30)
        print("       FINAL RESULTS       ")
        print("=" * 30)
        print(f"Cost:       {solution.cost:.2f}")
        print(f"Vehicles:   {len(solution.routes)}")
        if bks:
            gap = ((solution.cost - bks) / bks) * 100
            print(f"Gap:        {gap:.2f}%")
        print("=" * 30)


        if args.plot:
            if HAS_PLOTTER:
                # 1. Define the directory
                output_dir = "visualizations"

                # 2. Create it if it doesn't exist
                os.makedirs(output_dir, exist_ok=True)

                # 3. Define the full save path (e.g., visualizations/X-n101-k25.png)
                save_filename = f"{inst.name}.png"
                full_save_path = os.path.join(output_dir, save_filename)

                print(f"Generating plot -> {full_save_path}")

                # 4. Call plotter with the path
                plot_solution(
                    solution,
                    bks=bks,
                    name=inst.name,
                    save_path=full_save_path,
                    show=True
                )
            else:
                print("Warning: Plotter module not found.")

    except Exception as e:
        print(f"\nExecution Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()