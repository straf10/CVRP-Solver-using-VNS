import random
import time
from initial_solution import solve_nearest_neighbor


class VNSSolver:
    def __init__(self, instance, max_iterations=2000, max_seconds=600):
        self.instance = instance
        self.max_iterations = max_iterations
        self.max_seconds = max_seconds
        self.start_time = 0
        self.best_solution = None

    def solve(self):
        self.start_time = time.time()
        print("--> Generating Initial Solution...")
        current_sol = solve_nearest_neighbor(self.instance)
        # Ensure cost is fresh
        current_sol.cost = current_sol.compute_total_cost()

        self.best_solution = current_sol.clone()
        print(f"--> Initial Cost: {current_sol.cost:.2f}")

        iteration = 0
        no_improv_iter = 0

        # Base percentage for Ruin
        pct_remove_base = 0.10

        while iteration < self.max_iterations:
            if self._check_time():
                print("\n[STOP] Time limit reached.")
                break

            iteration += 1

            # Clone for the new iteration
            candidate_sol = current_sol.clone()

            # --- SHAKING: Ruin & Recreate ---
            # Increase ruin severity if we are stuck (Adaptive)
            current_pct = 0.30 if no_improv_iter > 50 else pct_remove_base

            # Robustness: Use len(nodes) - 1 (assuming 1 depot) for safe count
            num_customers = len(self.instance.nodes) - 1
            num_to_remove = int(max(4, num_customers * current_pct))

            self._shaking_ruin_recreate(candidate_sol, num_to_remove)

            # --- LOCAL SEARCH (VND) ---
            self._local_search(candidate_sol)

            # --- SAFETY RECOMPUTE ---
            # Periodically fix float drift or logic gaps
            candidate_sol.cost = candidate_sol.compute_total_cost()

            # --- ACCEPTANCE ---
            # Standard Descent
            if candidate_sol.cost < current_sol.cost - 0.001:
                current_sol = candidate_sol
                no_improv_iter = 0

                if current_sol.cost < self.best_solution.cost - 0.001:
                    self.best_solution = current_sol.clone()
                    print(f"Iter {iteration}: New Best Cost = {self.best_solution.cost:.2f}")
            else:
                no_improv_iter += 1

        return self.best_solution

    def _check_time(self):
        return (time.time() - self.start_time) > self.max_seconds

    # =========================================================================
    #  RUIN AND RECREATE
    # =========================================================================
    def _shaking_ruin_recreate(self, solution, num_to_remove):
        routes = solution.routes

        # Gather all customers (flatten routes)
        all_customers = []
        for r in routes:
            all_customers.extend(r)

        # Safety Guard: Empty solution or too small
        if not all_customers:
            return

        # Limit removal to available customers
        actual_remove = min(len(all_customers), num_to_remove)

        # RUIN: Random Removal
        nodes_to_remove = set(random.sample(all_customers, actual_remove))

        # Filter routes
        for r in routes:
            r[:] = [n for n in r if n not in nodes_to_remove]

        # Clean empty routes
        solution.routes = [r for r in routes if r]

        # RECREATE: Best Insertion
        # Shuffle to avoid deterministic insertion order
        removed_list = list(nodes_to_remove)
        random.shuffle(removed_list)

        for node in removed_list:
            self._best_insertion(solution, node)

        # CRITICAL FIX: Recompute cost after Shaking modifications.
        # Local search relies on incremental updates, so the base cost must be correct here.
        solution.cost = solution.compute_total_cost()

    def _best_insertion(self, solution, node):
        best_delta = float('inf')
        best_r_idx = -1
        best_pos_idx = -1

        demand = self.instance.demands[node]
        dist = self.instance.distance
        depot = self.instance.depot
        capacity = self.instance.capacity

        # Robustness: Impossible to insert if single node > capacity
        if demand > capacity:
            # In a strict solver, this should crash.
            # For a heuristic, we might skip, but let's raise to warn the user.
            raise ValueError(f"Node {node} demand ({demand}) exceeds vehicle capacity ({capacity}).")

        # 1. Try existing routes
        for r_idx, route in enumerate(solution.routes):
            load = sum(self.instance.demands[n] for n in route)
            if load + demand > capacity: continue

            for k in range(len(route) + 1):
                prev_n = route[k - 1] if k > 0 else depot
                next_n = route[k] if k < len(route) else depot

                delta = dist(prev_n, node) + dist(node, next_n) - dist(prev_n, next_n)

                if delta < best_delta:
                    best_delta = delta
                    best_r_idx = r_idx
                    best_pos_idx = k

        # 2. Try new route
        delta_new = dist(depot, node) + dist(node, depot)
        if delta_new < best_delta:
            best_delta = delta_new
            best_r_idx = len(solution.routes)
            best_pos_idx = 0

        # Apply Best Move
        if best_r_idx == len(solution.routes):
            solution.routes.append([node])
        else:
            solution.routes[best_r_idx].insert(best_pos_idx, node)

        # Note: We do NOT update solution.cost here.
        # We recompute it globally at the end of _shaking_ruin_recreate.

    # =========================================================================
    #  LOCAL SEARCH (VND)
    # =========================================================================
    def _local_search(self, solution):
        improved = True
        while improved:
            improved = False
            # Strategy: Cheapest/Fastest moves first
            if self._2opt_intra_fast(solution): improved = True; continue
            if self._2opt_star_fast(solution): improved = True; continue
            if self._relocate_chain(solution, 2): improved = True; continue
            if self._relocate_chain(solution, 1): improved = True; continue
            if self._swap_fast(solution): improved = True; continue

    # --- OPERATORS (Delta O(1)) ---

    def _2opt_intra_fast(self, solution):
        dist = self.instance.distance
        depot = self.instance.depot

        for r_idx, route in enumerate(solution.routes):
            n = len(route)
            if n < 2: continue

            for i in range(-1, n - 2):
                u = depot if i == -1 else route[i]
                v = route[i + 1]
                for j in range(i + 1, n):
                    if j == n - 1 and i == -1: continue

                    x = route[j]
                    y = depot if j == n - 1 else route[j + 1]

                    delta = (dist(u, x) + dist(v, y)) - (dist(u, v) + dist(x, y))

                    if delta < -0.001:
                        solution.routes[r_idx][i + 1:j + 1] = reversed(solution.routes[r_idx][i + 1:j + 1])
                        solution.cost += delta
                        return True
        return False

    def _2opt_star_fast(self, solution):
        routes = solution.routes
        dist = self.instance.distance
        depot = self.instance.depot
        demands = self.instance.demands
        capacity = self.instance.capacity

        # Precompute loads helps slightly with speed
        loads = [sum(demands[n] for n in r) for r in routes]

        for r1_idx in range(len(routes)):
            for r2_idx in range(r1_idx + 1, len(routes)):
                r1, r2 = routes[r1_idx], routes[r2_idx]

                # Split R1 after i
                for i in range(-1, len(r1)):
                    load_r1_head = sum(demands[r1[x]] for x in range(i + 1)) if i >= 0 else 0
                    load_r1_tail = loads[r1_idx] - load_r1_head

                    u = r1[i] if i >= 0 else depot
                    u_next = r1[i + 1] if i < len(r1) - 1 else depot

                    # Split R2 after j
                    for j in range(-1, len(r2)):
                        if i == -1 and j == -1: continue

                        load_r2_head = sum(demands[r2[x]] for x in range(j + 1)) if j >= 0 else 0
                        load_r2_tail = loads[r2_idx] - load_r2_head

                        if load_r1_head + load_r2_tail > capacity: continue
                        if load_r2_head + load_r1_tail > capacity: continue

                        v = r2[j] if j >= 0 else depot
                        v_next = r2[j + 1] if j < len(r2) - 1 else depot

                        old_cost = dist(u, u_next) + dist(v, v_next)
                        new_cost = dist(u, v_next) + dist(v, u_next)
                        delta = new_cost - old_cost

                        if delta < -0.001:
                            new_r1 = r1[:i + 1] + r2[j + 1:]
                            new_r2 = r2[:j + 1] + r1[i + 1:]
                            routes[r1_idx] = new_r1
                            routes[r2_idx] = new_r2
                            solution.cost += delta
                            # If a route became empty, cleanup
                            solution.routes = [r for r in routes if r]
                            return True
        return False

    def _relocate_chain(self, solution, chain_len):
        routes = solution.routes
        dist = self.instance.distance
        depot = self.instance.depot
        demands = self.instance.demands
        capacity = self.instance.capacity
        loads = [sum(demands[n] for n in r) for r in routes]

        for s_idx, src in enumerate(routes):
            if len(src) < chain_len: continue

            for i in range(len(src) - chain_len + 1):
                chain = src[i:i + chain_len]
                chain_load = sum(demands[n] for n in chain)

                prev_s = src[i - 1] if i > 0 else depot
                next_s = src[i + chain_len] if i + chain_len < len(src) else depot

                loss = dist(prev_s, next_s) - (dist(prev_s, chain[0]) + dist(chain[-1], next_s))

                for d_idx, dst in enumerate(routes):
                    if s_idx == d_idx: continue
                    if loads[d_idx] + chain_load > capacity: continue

                    best_delta_insert = float('inf')
                    best_k = -1

                    for k in range(len(dst) + 1):
                        prev_d = dst[k - 1] if k > 0 else depot
                        next_d = dst[k] if k < len(dst) else depot

                        gain = (dist(prev_d, chain[0]) + dist(chain[-1], next_d)) - dist(prev_d, next_d)

                        if gain < best_delta_insert:
                            best_delta_insert = gain
                            best_k = k

                    total_delta = loss + best_delta_insert

                    if total_delta < -0.001:
                        del src[i:i + chain_len]
                        dst[best_k:best_k] = chain
                        solution.cost += total_delta
                        if not src: routes.pop(s_idx)
                        return True
        return False

    def _swap_fast(self, solution):
        routes = solution.routes
        dist = self.instance.distance
        depot = self.instance.depot
        demands = self.instance.demands
        capacity = self.instance.capacity
        loads = [sum(demands[n] for n in r) for r in routes]

        for r1_idx in range(len(routes)):
            for r2_idx in range(r1_idx + 1, len(routes)):
                r1, r2 = routes[r1_idx], routes[r2_idx]
                l1, l2 = loads[r1_idx], loads[r2_idx]

                for i, u in enumerate(r1):
                    du = demands[u]
                    up = r1[i - 1] if i > 0 else depot
                    un = r1[i + 1] if i < len(r1) - 1 else depot

                    for j, v in enumerate(r2):
                        dv = demands[v]
                        if l1 - du + dv > capacity or l2 - dv + du > capacity: continue

                        vp = r2[j - 1] if j > 0 else depot
                        vn = r2[j + 1] if j < len(r2) - 1 else depot

                        old_cost = dist(up, u) + dist(u, un) + dist(vp, v) + dist(v, vn)
                        new_cost = dist(up, v) + dist(v, un) + dist(vp, u) + dist(u, vn)

                        if new_cost - old_cost < -0.001:
                            r1[i], r2[j] = v, u
                            solution.cost += (new_cost - old_cost)
                            return True
        return False