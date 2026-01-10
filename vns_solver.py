import random
import time
from initial_solution import CVRPSolution, solve_nearest_neighbor


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
        current_sol.cost = current_sol.compute_total_cost()

        self.best_solution = current_sol.clone()
        print(f"--> Initial Cost: {current_sol.cost:.2f}")

        k = 1
        k_max = 3
        iteration = 0
        no_improv_iter = 0  # Μετρητής στασιμότητας

        while iteration < self.max_iterations:
            if self._check_time():
                print("\n[STOP] Time limit reached.")
                break

            iteration += 1

            # --- PHASE 1: ADAPTIVE SHAKING ---
            candidate_sol = current_sol.clone()

            # Αν έχουμε κολλήσει για >50 επαναλήψεις, χτυπάμε πιο δυνατά (3-6 κινήσεις)
            # Αλλιώς, μικρές κινήσεις (1-2) για εξερεύνηση γειτονιάς.
            if no_improv_iter > 50:
                moves = random.randint(3, 6)
            else:
                moves = random.randint(1, 2)

            self._apply_shaking(candidate_sol, k, moves)

            # --- PHASE 2: LOCAL SEARCH (VND) ---
            self._local_search(candidate_sol)

            # --- PHASE 3: ACCEPTANCE ---
            if candidate_sol.cost < current_sol.cost - 0.001:
                current_sol = candidate_sol
                k = 1
                no_improv_iter = 0  # Reset counter

                if current_sol.cost < self.best_solution.cost - 0.001:
                    self.best_solution = current_sol.clone()
                    print(f"Iter {iteration}: New Best Cost = {self.best_solution.cost:.2f}")
            else:
                no_improv_iter += 1
                k += 1
                if k > k_max:
                    k = 1

        print(f"\n[DONE] Finished after {iteration} iterations.")
        return self.best_solution

    def _check_time(self):
        return (time.time() - self.start_time) > self.max_seconds

    def _apply_shaking(self, solution, k, moves=1):
        routes = solution.routes
        if not routes: return

        demands = self.instance.demands
        capacity = self.instance.capacity

        for _ in range(moves):
            if len(routes) < 2:
                # Αν έμεινε 1 route, κάνουμε μόνο intra-changes
                self._shaking_intra_2opt(routes)
                continue

            if k == 1:  # Relocate
                self._shaking_relocate(routes, demands, capacity)
            elif k == 2:  # Swap
                self._shaking_swap(routes, demands, capacity)
            elif k == 3:  # Intra 2-Opt
                self._shaking_intra_2opt(routes)

        solution.routes = [r for r in routes if r]
        solution.cost = solution.compute_total_cost()

    # --- Shaking Helpers ---
    def _shaking_relocate(self, routes, demands, capacity):
        r1_idx, r2_idx = random.sample(range(len(routes)), 2)
        r1, r2 = routes[r1_idx], routes[r2_idx]
        if not r1: return
        node_idx = random.randint(0, len(r1) - 1)
        node = r1[node_idx]
        if sum(demands[n] for n in r2) + demands[node] <= capacity:
            r1.pop(node_idx)
            r2.insert(random.randint(0, len(r2)), node)

    def _shaking_swap(self, routes, demands, capacity):
        r1_idx, r2_idx = random.sample(range(len(routes)), 2)
        r1, r2 = routes[r1_idx], routes[r2_idx]
        if not r1 or not r2: return
        idx1, idx2 = random.randint(0, len(r1) - 1), random.randint(0, len(r2) - 1)
        u, v = r1[idx1], r2[idx2]
        l1 = sum(demands[n] for n in r1)
        l2 = sum(demands[n] for n in r2)
        if (l1 - demands[u] + demands[v] <= capacity and l2 - demands[v] + demands[u] <= capacity):
            r1[idx1], r2[idx2] = v, u

    def _shaking_intra_2opt(self, routes):
        r_idx = random.randint(0, len(routes) - 1)
        route = routes[r_idx]
        if len(route) < 3: return
        i, j = sorted(random.sample(range(len(route)), 2))
        if i + 1 == j: return
        routes[r_idx] = route[:i + 1] + route[i + 1:j + 1][::-1] + route[j + 1:]

    def _local_search(self, solution):
        """
        VND Strategy:
        1. Intra-2Opt (Fast cleanup)
        2. Inter-2Opt* (Structural change - THE GAP CLOSER)
        3. Relocate (Load balancing)
        4. Swap (Exchange)
        """
        improved = True
        while improved:
            improved = False

            # 1. Clean individual routes first
            while self._2opt_intra_fast(solution): improved = True

            # 2. Try to untangle routes (Inter-Route 2-Opt / Cross)
            # Αυτό είναι το πιο σημαντικό για το Gap < 2%
            if self._2opt_star_fast(solution):
                improved = True
                continue

                # 3. Move nodes to balance loads
            if self._relocate_fast(solution):
                improved = True
                continue

            # 4. Swap nodes
            if self._swap_fast(solution):
                improved = True
                continue

    # ------------------------------------------------------------------
    # OPERATORS (With Inter-Route 2-Opt*)
    # ------------------------------------------------------------------

    def _2opt_intra_fast(self, solution):
        """Intra-route 2-opt O(1). Includes Depot edges."""
        dist = self.instance.distance
        depot = self.instance.depot

        for r_idx, route in enumerate(solution.routes):
            n = len(route)
            if n < 2: continue

            for i in range(-1, n - 1):
                for j in range(i + 2, n):
                    # Edge 1: (A, B)
                    A = depot if i == -1 else route[i]
                    B = route[0] if i == -1 else route[i + 1]

                    # Edge 2: (C, D)
                    C = route[j]
                    D = depot if j == n - 1 else route[j + 1]

                    curr = dist(A, B) + dist(C, D)
                    new_c = dist(A, C) + dist(B, D)

                    if new_c < curr - 0.001:
                        # Reverse segment [i+1 ... j]
                        start, end = i + 1, j
                        solution.routes[r_idx][start:end + 1] = solution.routes[r_idx][start:end + 1][::-1]
                        solution.cost += (new_c - curr)
                        return True
        return False

    def _2opt_star_fast(self, solution):
        """
        Inter-Route 2-Opt (2-Opt*).
        Ανταλλάσσει τις ουρές δύο διαδρομών.
        R1: A -> B -> [Tail1]
        R2: C -> D -> [Tail2]
        New R1: A -> B -> [Tail2]
        New R2: C -> D -> [Tail1]
        """
        routes = solution.routes
        dist = self.instance.distance
        depot = self.instance.depot
        demands = self.instance.demands
        capacity = self.instance.capacity

        # Precompute loads
        loads = [sum(demands[n] for n in r) for r in routes]

        for r1_idx in range(len(routes)):
            for r2_idx in range(r1_idx + 1, len(routes)):
                r1 = routes[r1_idx]
                r2 = routes[r2_idx]

                # Προσπάθεια κοψίματος μετά από κάθε κόμβο (συμπεριλαμβανομένου του depot)
                # i: index του τελευταίου κόμβου που μένει στο R1 (αν -1, μένει μόνο το depot)
                for i in range(-1, len(r1)):
                    # Load του κομματιού που μένει στο R1
                    load_r1_head = 0
                    if i >= 0:
                        # Αυτό είναι λίγο αργό (O(N)), αλλά οι διαδρομές είναι μικρές
                        load_r1_head = sum(demands[r1[x]] for x in range(i + 1))

                    load_r1_tail = loads[r1_idx] - load_r1_head

                    # Nodes γύρω από το κόψιμο στο R1
                    u = depot if i == -1 else r1[i]
                    u_next = depot if i == len(r1) - 1 else r1[i + 1]

                    # j: index του τελευταίου κόμβου που μένει στο R2
                    for j in range(-1, len(r2)):
                        # Optimization: Αν και οι δύο αλλαγές περιλαμβάνουν depot (i=-1, j=-1),
                        # ουσιαστικά ανταλλάσσουμε ολόκληρες διαδρομές -> άχρηστο.
                        if i == -1 and j == -1: continue

                        load_r2_head = 0
                        if j >= 0:
                            load_r2_head = sum(demands[r2[x]] for x in range(j + 1))

                        load_r2_tail = loads[r2_idx] - load_r2_head

                        # Check Capacity για τις νέες διαδρομές
                        # New R1 = Head1 + Tail2
                        if load_r1_head + load_r2_tail > capacity: continue
                        # New R2 = Head2 + Tail1
                        if load_r2_head + load_r1_tail > capacity: continue

                        # Nodes γύρω από το κόψιμο στο R2
                        v = depot if j == -1 else r2[j]
                        v_next = depot if j == len(r2) - 1 else r2[j + 1]

                        # Υπολογισμός Delta
                        # Old edges: (u, u_next) + (v, v_next)
                        current_cost = dist(u, u_next) + dist(v, v_next)

                        # New edges: (u, v_next) + (v, u_next)
                        # R1 connect u to old tail of R2 (starts at v_next)
                        # R2 connect v to old tail of R1 (starts at u_next)
                        new_cost = dist(u, v_next) + dist(v, u_next)

                        if new_cost < current_cost - 0.001:
                            # Apply Move
                            # Tails
                            tail1 = r1[i + 1:]
                            tail2 = r2[j + 1:]

                            # Heads
                            head1 = r1[:i + 1]
                            head2 = r2[:j + 1]

                            new_r1 = head1 + tail2
                            new_r2 = head2 + tail1

                            routes[r1_idx] = new_r1
                            routes[r2_idx] = new_r2

                            solution.cost += (new_cost - current_cost)
                            # Αν αδειάσουν διαδρομές, clean up
                            solution.routes = [r for r in routes if r]
                            return True
        return False

    def _relocate_fast(self, solution):
        """Standard Relocate with Delta."""
        routes = solution.routes
        dist = self.instance.distance
        depot = self.instance.depot
        demands = self.instance.demands
        capacity = self.instance.capacity
        loads = [sum(demands[n] for n in r) for r in routes]

        for s_idx, src_route in enumerate(routes):
            if not src_route: continue
            for n_idx, node in enumerate(src_route):
                demand = demands[node]
                prev_n = src_route[n_idx - 1] if n_idx > 0 else depot
                next_n = src_route[n_idx + 1] if n_idx < len(src_route) - 1 else depot
                cost_rem = dist(prev_n, node) + dist(node, next_n) - dist(prev_n, next_n)

                for d_idx, dst_route in enumerate(routes):
                    if s_idx == d_idx: continue
                    if loads[d_idx] + demand > capacity: continue

                    best_pos_delta = float('inf')
                    best_k = -1

                    for k in range(len(dst_route) + 1):
                        p = dst_route[k - 1] if k > 0 else depot
                        n = dst_route[k] if k < len(dst_route) else depot
                        delta = (dist(p, node) + dist(node, n) - dist(p, n)) - cost_rem
                        if delta < best_pos_delta:
                            best_pos_delta = delta
                            best_k = k

                    if best_pos_delta < -0.001:
                        val = routes[s_idx].pop(n_idx)
                        routes[d_idx].insert(best_k, val)
                        solution.cost += best_pos_delta
                        if not routes[s_idx]: routes.pop(s_idx)
                        return True
        return False

    def _swap_fast(self, solution):
        """Standard Swap with Delta."""
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
                    loss_u = dist(up, u) + dist(u, un)

                    for j, v in enumerate(r2):
                        dv = demands[v]
                        if (l1 - du + dv > capacity or l2 - dv + du > capacity): continue

                        vp = r2[j - 1] if j > 0 else depot
                        vn = r2[j + 1] if j < len(r2) - 1 else depot
                        loss_v = dist(vp, v) + dist(v, vn)

                        gain_v = dist(up, v) + dist(v, un)
                        gain_u = dist(vp, u) + dist(u, vn)

                        delta = (gain_v + gain_u) - (loss_u + loss_v)
                        if delta < -0.001:
                            r1[i], r2[j] = v, u
                            solution.cost += delta
                            return True
        return False