import random
import time
import os
import sys

# Imports
try:
    from initial_solution import CVRPSolution, solve_nearest_neighbor
    from CVRP_Instance import CVRPInstance
except ImportError:
    pass


class VNSSolver:
    def __init__(self, instance, max_iterations=2000, max_seconds=600):
        self.instance = instance
        self.max_iterations = max_iterations
        self.max_seconds = max_seconds
        self.start_time = 0
        self.best_solution = None

    def solve(self):
        self.start_time = time.time()

        # 1. Initial Solution
        print("--> Generating Initial Solution (Nearest Neighbor)...")
        current_sol = solve_nearest_neighbor(self.instance)
        # Βεβαιωνόμαστε ότι το κόστος είναι σωστό στην αρχή
        current_sol.cost = current_sol.compute_total_cost()

        self.best_solution = current_sol.clone()
        print(f"--> Initial Cost: {current_sol.cost:.2f}")

        k = 1
        k_max = 3
        iteration = 0

        while iteration < self.max_iterations:
            # Global Time Check
            if time.time() - self.start_time > self.max_seconds:
                print("\n[STOP] Time limit reached (Global).")
                break

            iteration += 1

            # --- SHAKING ---
            candidate_sol = current_sol.clone()
            self._apply_shaking(candidate_sol, k)

            # --- LOCAL SEARCH ---
            self._local_search(candidate_sol)

            # --- ACCEPTANCE ---
            # Χρησιμοποιούμε μικρό epsilon για float comparison
            if candidate_sol.cost < current_sol.cost - 0.001:
                current_sol = candidate_sol
                k = 1

                # Check Global Best
                if current_sol.cost < self.best_solution.cost - 0.001:
                    self.best_solution = current_sol.clone()  # Clone για ασφάλεια
                    print(f"Iter {iteration}: New Best Cost = {self.best_solution.cost:.2f}")
            else:
                k += 1
                if k > k_max:
                    k = 1

        print(f"\n[DONE] Finished after {iteration} iterations.")
        return self.best_solution

    def _check_time(self):
        return (time.time() - self.start_time) > self.max_seconds

    def _apply_shaking(self, solution, k):
        """
        Shaking: Τυχαίες κινήσεις για διαφυγή από τοπικά ελάχιστα.
        Δεν κάνουμε αυστηρούς ελέγχους βελτίωσης κόστους εδώ, μόνο εγκυρότητας (capacity).
        """
        routes = solution.routes
        if len(routes) < 2: return

        moves_done = 0
        attempts = 0
        # Στο shaking κάνουμε 1 ή περισσότερες κινήσεις ανάλογα το k
        required_moves = k

        while moves_done < required_moves and attempts < 50:
            attempts += 1

            if k == 1:  # Relocate
                r_from_idx = random.randint(0, len(routes) - 1)
                r_to_idx = random.randint(0, len(routes) - 1)
                if r_from_idx == r_to_idx: continue

                r_from = routes[r_from_idx]
                r_to = routes[r_to_idx]
                if not r_from: continue

                node_idx = random.randint(0, len(r_from) - 1)
                node = r_from[node_idx]

                # Fast Check Capacity
                load_to = sum(self.instance.demands[n] for n in r_to)
                if load_to + self.instance.demands[node] <= self.instance.capacity:
                    # Execute Move
                    # Incremental Cost Update logic for Shaking is optional but good practice
                    cost_from_old = CVRPSolution.calculate_route_cost(self.instance, r_from)
                    cost_to_old = CVRPSolution.calculate_route_cost(self.instance, r_to)

                    r_from.pop(node_idx)
                    insert_pos = random.randint(0, len(r_to))
                    r_to.insert(insert_pos, node)

                    cost_from_new = CVRPSolution.calculate_route_cost(self.instance, r_from)
                    cost_to_new = CVRPSolution.calculate_route_cost(self.instance, r_to)

                    solution.cost = solution.cost - (cost_from_old + cost_to_old) + (cost_from_new + cost_to_new)
                    moves_done += 1

            elif k >= 2:  # Swap (or mixed for higher k)
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

                if (load1 - self.instance.demands[u] + self.instance.demands[v] <= self.instance.capacity and
                        load2 - self.instance.demands[v] + self.instance.demands[u] <= self.instance.capacity):
                    cost1_old = CVRPSolution.calculate_route_cost(self.instance, r1)
                    cost2_old = CVRPSolution.calculate_route_cost(self.instance, r2)

                    r1[idx1] = v
                    r2[idx2] = u

                    cost1_new = CVRPSolution.calculate_route_cost(self.instance, r1)
                    cost2_new = CVRPSolution.calculate_route_cost(self.instance, r2)

                    solution.cost = solution.cost - (cost1_old + cost2_old) + (cost1_new + cost2_new)
                    moves_done += 1

        # Clean empty routes
        solution.routes = [r for r in routes if r]

    def _local_search(self, solution):
        improved = True
        while improved:
            # Time check inside loop
            if self._check_time(): return

            improved = False
            # Προτεραιότητα: 2-opt (Intra) -> Relocate (Inter) -> Swap (Inter)
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
        """
        Intra-route 2-opt.
        Optimized: Υπολογίζει μόνο το κόστος της διαδρομής που αλλάζει.
        """
        routes = solution.routes

        for r_idx, route in enumerate(routes):
            if len(route) < 3: continue

            base_route_cost = CVRPSolution.calculate_route_cost(self.instance, route)

            # Για κάθε πιθανό τμήμα (segment)
            for i in range(len(route) - 1):
                for j in range(i + 1, len(route)):

                    # --- ΓΡΗΓΟΡΟΣ ΕΛΕΓΧΟΣ (Delta Check - Προαιρετικό αλλά βέλτιστο) ---
                    # Εδώ κάνουμε την απλή εκδοχή: Route Re-computation (O(N) ανά move)
                    # Είναι πολύ πιο γρήγορο από το Solution Re-computation (O(Total N))

                    # Φτιάχνουμε το νέο route δοκιμαστικά
                    # Reverse segment [i...j]
                    new_route = route[:i] + route[i:j + 1][::-1] + route[j + 1:]
                    new_route_cost = CVRPSolution.calculate_route_cost(self.instance, new_route)

                    if new_route_cost < base_route_cost - 0.001:
                        # Βρέθηκε βελτίωση
                        diff = new_route_cost - base_route_cost
                        solution.cost += diff  # Incremental Update
                        routes[r_idx] = new_route  # Update Structure
                        return True
        return False

    def _operator_relocate(self, solution):
        """Inter-route Relocate με Caching Loads και Incremental Cost."""
        routes = solution.routes
        # Caching loads για ταχύτητα
        loads = [sum(self.instance.demands[n] for n in r) for r in routes]

        for i, source_route in enumerate(routes):
            for j, dest_route in enumerate(routes):
                if i == j: continue

                # Κόστη πριν την αλλαγή
                cost_source_old = CVRPSolution.calculate_route_cost(self.instance, source_route)
                cost_dest_old = CVRPSolution.calculate_route_cost(self.instance, dest_route)

                for node_idx, node in enumerate(source_route):
                    demand = self.instance.demands[node]

                    # Έλεγχος χωρητικότητας γρήγορα από τον πίνακα loads
                    if loads[j] + demand > self.instance.capacity:
                        continue

                    # Προσωρινή αφαίρεση
                    temp_source = source_route[:node_idx] + source_route[node_idx + 1:]
                    cost_source_new = CVRPSolution.calculate_route_cost(self.instance, temp_source)

                    # Δοκιμή εισαγωγής σε όλες τις θέσεις
                    best_dest_cost = float('inf')
                    best_new_dest_route = None

                    # Εδώ κάνουμε best-insert στον προορισμό
                    for k in range(len(dest_route) + 1):
                        temp_dest = dest_route[:k] + [node] + dest_route[k:]
                        c_new = CVRPSolution.calculate_route_cost(self.instance, temp_dest)

                        if c_new < best_dest_cost:
                            best_dest_cost = c_new
                            best_new_dest_route = temp_dest

                    # Αξιολόγηση συνολικής αλλαγής
                    old_pair_cost = cost_source_old + cost_dest_old
                    new_pair_cost = cost_source_new + best_dest_cost

                    if new_pair_cost < old_pair_cost - 0.001:
                        # Apply Move
                        routes[i] = temp_source
                        routes[j] = best_new_dest_route

                        # Update Total Cost
                        solution.cost = solution.cost - old_pair_cost + new_pair_cost

                        # Update Loads? Δεν χρειάζεται γιατί κάνουμε return True και
                        # τα loads θα ξανα-υπολογιστούν στην επόμενη κλήση του operator
                        # (Απλοποίηση για ασφάλεια κώδικα)

                        # Καθαρισμός κενών
                        solution.routes = [r for r in routes if r]
                        return True
        return False

    def _operator_swap(self, solution):
        """Inter-route Swap με Incremental Cost."""
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

                        # Capacity Check
                        if (loads[i] - du + dv > self.instance.capacity or
                                loads[j] - dv + du > self.instance.capacity):
                            continue

                        # Swap Simulation
                        r1[idx1] = v
                        r2[idx2] = u

                        cost_r1_new = CVRPSolution.calculate_route_cost(self.instance, r1)
                        cost_r2_new = CVRPSolution.calculate_route_cost(self.instance, r2)

                        if (cost_r1_new + cost_r2_new) < (cost_r1_old + cost_r2_old) - 0.001:
                            # Κρατάμε την αλλαγή (έγινε in-place)
                            diff = (cost_r1_new + cost_r2_new) - (cost_r1_old + cost_r2_old)
                            solution.cost += diff
                            return True
                        else:
                            # Revert Swap (Backtrack)
                            r1[idx1] = u
                            r2[idx2] = v
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
    files = [f for f in os.listdir(instance_folder) if f.endswith(".vrp")]

    if not files:
        print("No files found.")
        sys.exit()

    # Δοκίμασε το X-n101 αν υπάρχει, αλλιώς το πρώτο
    target = "X-n106-k14.vrp"
    if target not in files: target = files[0]

    vrp_path = os.path.join(instance_folder, target)
    print(f"Solving: {target}")

    inst = CVRPInstance(vrp_path)
    bks = read_solution_file(vrp_path.replace(".vrp", ".sol"))
    if bks: print(f"BKS: {bks}")

    # Set Max Time: 600 seconds
    solver = VNSSolver(inst, max_iterations=2000, max_seconds=600)
    sol = solver.solve()

    print(f"\nFinal Cost: {sol.cost:.2f}")
    if bks:
        gap = ((sol.cost - bks) / bks) * 100
        print(f"Gap: {gap:.2f}%")