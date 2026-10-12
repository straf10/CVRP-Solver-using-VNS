import argparse
import random
import sys
from pathlib import Path

from CVRP_Instance import CVRPInstance
from vns_solver import VNSSolver

PLOT_DIR = Path(__file__).resolve().parent.parent / "visualizations"


def read_bks(vrp_path):
    """Best-known solution cost from the matching .sol file, or None if there is none."""
    sol_path = Path(vrp_path).with_suffix(".sol")
    if not sol_path.is_file():
        return None
    for line in sol_path.read_text().splitlines():
        if "Cost" in line:
            return float(line.split()[-1])
    return None


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="VNS solver for the CVRP")
    parser.add_argument("-i", "--instance", required=True, help="Path to the .vrp input file")
    parser.add_argument("-s", "--seed", type=int, default=42, help="Random seed")
    parser.add_argument("-t", "--time", type=int, default=600, help="Max execution time in seconds")
    parser.add_argument("--iter", type=int, default=2000, help="Max VNS iterations")
    parser.add_argument("-p", "--plot", action="store_true", help="Show the solution and save it to visualizations/")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        inst = CVRPInstance(args.instance)
    except (OSError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"-> Solving: {args.instance}")
    bks = read_bks(args.instance)
    if bks is not None:
        print(f"-> BKS: {bks}")

    solver = VNSSolver(inst, max_iterations=args.iter, max_seconds=args.time, rng=random.Random(args.seed))
    solution = solver.solve()

    print("\n" + "=" * 30)
    print("       FINAL RESULTS       ")
    print("=" * 30)
    print(f"Cost:       {solution.cost:.2f}")
    print(f"Vehicles:   {len(solution.routes)}")
    if bks is not None:
        print(f"Gap:        {(solution.cost - bks) / bks * 100:.2f}%")
    print("=" * 30)

    if args.plot:
        from visualization import plot_solution  # imported lazily so matplotlib is only needed for plots

        PLOT_DIR.mkdir(exist_ok=True)
        save_path = PLOT_DIR / f"{inst.name}.png"
        print(f"Generating plot -> {save_path}")
        plot_solution(solution, name=inst.name, bks=bks, save_path=save_path, show=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
