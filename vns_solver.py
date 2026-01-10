import random
import time
import os
import sys

from initial_solution import CVRPSolution, solve_nearest_neighbor
from CVRP_Instance import CVRPInstance


class VNSSolver:
    def __init__(self, instance, max_iterations=2000, max_seconds=600):
        self.instance = instance
        self.max_iterations = max_iterations
        self.max_seconds = max_seconds
        self.start_time = 0
        self.best_solution = None

    def solve(self):
        self.start_time = time.time()

        # Initial Solution
        print("--> Generating Initial Solution (Nearest Neighbor)...")
        current_sol = solve_nearest_neighbor(self.instance)
        # Recalculate cost fresh ensures correctness
        current_sol.cost = current_sol.compute_total_cost()

        self.best_solution = current_sol.clone()
        print(f"--> Initial Cost: {current_sol.cost:.2f}")

        k = 1
        k_max = 3  # 1: Relocate, 2: Swap, 3: 2-Opt
        iteration = 0

        while iteration < self.max_iterations:
            # Time Check
            if self._check_time():
                print("\n[STOP] Time limit reached.")
                break

            iteration += 1

            # --- PHASE 1: SHAKING ---
            candidate_sol = current_sol.clone()
            self._apply_shaking(candidate_sol, k)

            # --- PHASE 2: LOCAL SEARCH ---
            self._local_search(candidate_sol)

            # --- PHASE 3: ACCEPTANCE ---
            # Αν βρήκαμε καλύτερη λύση
            if candidate_sol.cost < current_sol.cost - 0.001:
                current_sol = candidate_sol
                k = 1  # Reset neighborhood

                # Check Global Best
                if current_sol.cost < self.best_solution.cost - 0.001:
                    self.best_solution = current_sol.clone()
                    print(f"Iter {iteration}: New Best Cost = {self.best_solution.cost:.2f}")
            else:
                # Αν δεν βελτιώθηκε, πήγαινε στην επόμενη γειτονιά Shaking
                k += 1
                if k > k_max:
                    k = 1

        print(f"\n[DONE] Finished after {iteration} iterations.")
        return self.best_solution

    def _check_time(self):
        return (time.time() - self.start_time) > self.max_seconds

    def _apply_shaking(self, solution, k):
        """
        Εφαρμόζει τυχαία ανατάραξη.
        k=1 -> Relocate (Inter-route)
        k=2 -> Swap (Inter-route)
        k=3 -> 2-Opt (Intra-route)
        """
        routes = solution.routes
        if not routes: return

        attempts = 0
        applied = False

        while not applied and attempts < 50:
            attempts += 1

            # --- k=1: Random Relocate ---
            if k == 1:
                if len(routes) < 2:
                    # Αν έχουμε μόνο 1 διαδρομή, δεν γίνεται inter-route relocate/swap.
                    # Αναγκαστικά πάμε σε κάτι intra (π.χ. 2-opt) ή δεν κάνουμε τίποτα.
                    break

                r_from_idx = random.randint(0, len(routes) - 1)
                r_to_idx = random.randint(0, len(routes) - 1)
                if r_from_idx == r_to_idx: continue

                r_from = routes[r_from_idx]
                r_to = routes[r_to_idx]
                if not r_from: continue

                node_idx = random.randint(0, len(r_from) - 1)
                node = r_from[node_idx]

                # Check Capacity
                load_to = sum(self.instance.demands[n] for n in r_to)
                if load_to + self.instance.demands[node] <= self.instance.capacity:
                    # Apply Relocate
                    r_from.pop(node_idx)
                    insert_pos = random.randint(0, len(r_to))
                    r_to.insert(insert_pos, node)
                    applied = True

            # --- k=2: Random Swap ---
            elif k == 2:
                if len(routes) < 2: break

                r1_idx = random.randint(0, len(routes) - 1)
                r2_idx = random.randint(0, len(routes) - 1)
                if r1_idx == r2_idx: continue

                r1 = routes[r1_idx]
                r2 = routes[r2_idx]
                if not r1 or not r2: continue

                idx1 = random.randint(0, len(r1) - 1)
                idx2 = random.randint(0, len(r2) - 1)
                u, v = r1[idx1], r2[idx2]

                load1 = sum(self.instance.demands[n] for n in r1)
                load2 = sum(self.instance.demands[n] for n in r2)

                # Check Capacity
                if (load1 - self.instance.demands[u] + self.instance.demands[v] <= self.instance.capacity and
                        load2 - self.instance.demands[v] + self.instance.demands[u] <= self.instance.capacity):
                    # Apply Swap
                    r1[idx1] = v
                    r2[idx2] = u
                    applied = True

            # --- k=3: Random 2-Opt (Intra-route) ---
            elif k == 3:
                # Αυτό δουλεύει ακόμα και με 1 route
                r_idx = random.randint(0, len(routes) - 1)
                route = routes[r_idx]
                if len(route) < 3: continue  # Θέλουμε τουλάχιστον 3 κόμβους για reverse

                i = random.randint(0, len(route) - 2)
                j = random.randint(i + 1, len(route) - 1)

                # Apply Reverse (In-place list modification not easy with slicing, so replace)
                new_route = route[:i] + route[i:j + 1][::-1] + route[j + 1:]
                routes[r_idx] = new_route
                applied = True

        # Clean empty routes & Update Cost
        solution.routes = [r for r in routes if r]
        # Στο shaking (επειδή είναι random) κάνουμε full computation μια φορά για σιγουριά
        solution.cost = solution.compute_total_cost()

    def _local_search(self, solution):
        """First Improvement Local Search"""
        improved = True
        while improved:
            if self._check_time(): return

            improved = False
            # 2-Opt (Fastest/Strongest for routing) -> Relocate -> Swap
            if self._operator_2opt(solution):
                improved = True
                continue
            if self._operator_relocate(solution):
                improved = True
                continue
            if self._operator_swap(solution):
                improved = True
                continue

    def _operator_2opt(self, solution):
        """Intra-route 2-opt. Incremental Updates."""
        routes = solution.routes

        for r_idx, route in enumerate(routes):
            if len(route) < 3: continue

            base_cost = CVRPSolution.calculate_route_cost(self.instance, route)

            for i in range(len(route) - 1):
                for j in range(i + 1, len(route)):

                    # Create candidate
                    new_route = route[:i] + route[i:j + 1][::-1] + route[j + 1:]
                    new_cost = CVRPSolution.calculate_route_cost(self.instance, new_route)

                    if new_cost < base_cost - 0.001:
                        # Found improvement
                        solution.cost += (new_cost - base_cost)
                        routes[r_idx] = new_route
                        return True
        return False

    def _operator_relocate(self, solution):
        """Inter-route Relocate."""
        routes = solution.routes
        loads = [sum(self.instance.demands[n] for n in r) for r in routes]

        for i, source_route in enumerate(routes):
            for j, dest_route in enumerate(routes):
                if i == j: continue

                # Αν είναι γεμάτο το dest, ίσως να μην χωράει τίποτα, αλλά ελέγχουμε per node
                if loads[j] >= self.instance.capacity: continue

                cost_source_old = CVRPSolution.calculate_route_cost(self.instance, source_route)
                cost_dest_old = CVRPSolution.calculate_route_cost(self.instance, dest_route)

                for node_idx, node in enumerate(source_route):
                    demand = self.instance.demands[node]

                    if loads[j] + demand > self.instance.capacity:
                        continue

                    # Simulation
                    temp_source = source_route[:node_idx] + source_route[node_idx + 1:]
                    cost_source_new = CVRPSolution.calculate_route_cost(self.instance, temp_source)

                    # Best Insert Position
                    best_dest_cost = float('inf')
                    best_new_dest_route = None

                    for k in range(len(dest_route) + 1):
                        temp_dest = dest_route[:k] + [node] + dest_route[k:]
                        c_new = CVRPSolution.calculate_route_cost(self.instance, temp_dest)

                        if c_new < best_dest_cost:
                            best_dest_cost = c_new
                            best_new_dest_route = temp_dest

                    # Check Total Delta
                    old_pair = cost_source_old + cost_dest_old
                    new_pair = cost_source_new + best_dest_cost

                    if new_pair < old_pair - 0.001:
                        routes[i] = temp_source
                        routes[j] = best_new_dest_route
                        solution.cost += (new_pair - old_pair)
                        solution.routes = [r for r in routes if r]  # Clean empty
                        return True
        return False

    def _operator_swap(self, solution):
        """Inter-route Swap."""
        routes = solution.routes
        loads = [sum(self.instance.demands[n] for n in r) for r in routes]

        for i in range(len(routes)):
            for j in range(i + 1, len(routes)):
                r1 = routes[i]
                r2 = routes[j]

                cost_r1_old = CVRPSolution.calculate_route_cost(self.instance, r1)
                cost_r2_old = CVRPSolution.calculate_route_cost(self.instance, r2)

                for idx1, u in enumerate(r1):
                    for idx2, v in enumerate(r2):
                        du = self.instance.demands[u]
                        dv = self.instance.demands[v]

                        if (loads[i] - du + dv > self.instance.capacity or
                                loads[j] - dv + du > self.instance.capacity):
                            continue

                        # Apply Swap temporarily
                        r1[idx1] = v
                        r2[idx2] = u

                        cost_r1_new = CVRPSolution.calculate_route_cost(self.instance, r1)
                        cost_r2_new = CVRPSolution.calculate_route_cost(self.instance, r2)

                        if (cost_r1_new + cost_r2_new) < (cost_r1_old + cost_r2_old) - 0.001:
                            solution.cost += ((cost_r1_new + cost_r2_new) - (cost_r1_old + cost_r2_old))
                            return True  # Swap kept
                        else:
                            # Revert
                            r1[idx1] = u
                            r2[idx2] = v

        # CRITICAL FIX: Return False here, outside loops
        return False


# --- Runner ---
def read_solution_file(sol_path):
    if not os.path.exists(sol_path): return None
    try:
        with open(sol_path, 'r') as f:
            for line in f:
                if "Cost" in line:
                    return float(line.strip().split()[-1])
    except:
        pass
    return None


if __name__ == "__main__":
    instance_folder = "Instances"
    if not os.path.exists(instance_folder):
        print(f"Error: Folder '{instance_folder}' not found.")
        sys.exit(1)

    files = [f for f in os.listdir(instance_folder) if f.endswith(".vrp")]
    if not files:
        print("No .vrp files found.")
        sys.exit(1)

    target = "X-n101-k25.vrp"
    if target not in files: target = files[0]

    vrp_path = os.path.join(instance_folder, target)
    print(f"Solving: {target}")

    inst = CVRPInstance(vrp_path)
    bks = read_solution_file(vrp_path.replace(".vrp", ".sol"))
    if bks: print(f"BKS: {bks}")

    solver = VNSSolver(inst, max_iterations=2000, max_seconds=600)
    sol = solver.solve()

    print(f"\nFinal Cost: {sol.cost:.2f}")
    if bks:
        gap = ((sol.cost - bks) / bks) * 100
        print(f"Gap: {gap:.2f}%")