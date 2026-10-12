import random
import time
from functools import partial
from itertools import accumulate
from math import inf

from initial_solution import nearest_neighbor

EPS = 1e-3  # minimum improvement required to accept a move (guards against float noise)


class VNSSolver:
    """General VNS: ruin & recreate shaking followed by a VND local search over five neighborhoods.

    Routes are padded with the depot (`[depot, *route, depot]`) wherever a move needs a predecessor
    or successor, so no operator needs its own depot special-casing.
    """

    def __init__(self, instance, max_iterations=2000, max_seconds=600, rng=None):
        self.inst = instance
        self.max_iterations = max_iterations
        self.max_seconds = max_seconds
        self.rng = rng or random.Random()
        # Cheapest first; the VND restarts from the top after every improving move.
        self._neighborhoods = (
            self._two_opt,
            self._two_opt_star,
            partial(self._relocate, chain_len=2),
            partial(self._relocate, chain_len=1),
            self._swap,
        )

    def solve(self):
        start = time.perf_counter()
        print("--> Generating Initial Solution...")
        current = nearest_neighbor(self.inst)
        best = current
        print(f"--> Initial Cost: {current.cost:.2f}")

        num_customers = len(self.inst.customers)
        stall = 0
        for iteration in range(1, self.max_iterations + 1):
            if time.perf_counter() - start > self.max_seconds:
                print("\n[STOP] Time limit reached.")
                break

            # Solutions are never mutated after acceptance, so sharing references is safe.
            candidate = current.clone()
            ruin_rate = 0.30 if stall > 50 else 0.10  # adaptive: ruin harder when stuck
            self._ruin_and_recreate(candidate.routes, max(4, int(num_customers * ruin_rate)))
            self._local_search(candidate.routes)

            if candidate.cost < current.cost - EPS:
                current = candidate
                stall = 0
                if current.cost < best.cost - EPS:
                    best = current
                    print(f"Iter {iteration}: New Best Cost = {best.cost:.2f}")
            else:
                stall += 1

        return best

    # ----- Shaking: ruin & recreate -------------------------------------------------------------

    def _ruin_and_recreate(self, routes, num_remove):
        customers = [c for route in routes for c in route]
        if not customers:
            return

        removed = set(self.rng.sample(customers, min(num_remove, len(customers))))
        kept_routes = []
        for route in routes:
            kept = [c for c in route if c not in removed]
            if kept:
                kept_routes.append(kept)
        routes[:] = kept_routes

        order = list(removed)
        self.rng.shuffle(order)
        for node in order:
            self._insert_best(routes, node)

    def _insert_best(self, routes, node):
        """Cheapest feasible insertion across all routes; opens a new route only if that is cheaper."""
        inst = self.inst
        dist, depot, demand = inst.dist, inst.depot, inst.demand
        best_delta, best_route, best_pos = inf, None, None

        for r_idx, route in enumerate(routes):
            if sum(demand[c] for c in route) + demand[node] > inst.capacity:
                continue
            path = [depot, *route, depot]
            for pos in range(len(path) - 1):
                a, b = path[pos], path[pos + 1]
                delta = dist[a][node] + dist[node][b] - dist[a][b]
                if delta < best_delta:
                    best_delta, best_route, best_pos = delta, r_idx, pos

        new_route_delta = dist[depot][node] + dist[node][depot]
        if new_route_delta < best_delta:
            routes.append([node])
        else:
            routes[best_route].insert(best_pos, node)

    # ----- Local search: variable neighborhood descent ------------------------------------------

    def _local_search(self, routes):
        # `any` short-circuits, so only the first improving neighborhood is applied per pass.
        while any(move(routes) for move in self._neighborhoods):
            pass

    def _two_opt(self, routes):
        """Intra-route 2-opt: reverse a segment of one route when that shortens it."""
        dist, depot = self.inst.dist, self.inst.depot
        for route in routes:
            n = len(route)
            path = [depot, *route, depot]
            for a in range(n - 1):
                for b in range(a + 1, n + 1):
                    if a == 0 and b == n:
                        continue  # reversing the entire route is a no-op
                    u, v, x, y = path[a], path[a + 1], path[b], path[b + 1]
                    delta = (dist[u][x] + dist[v][y]) - (dist[u][v] + dist[x][y])
                    if delta < -EPS:
                        route[a:b] = route[a:b][::-1]
                        return True
        return False

    def _two_opt_star(self, routes):
        """Inter-route 2-opt: exchange the tails of two routes when both stay within capacity."""
        inst = self.inst
        dist, depot, capacity = inst.dist, inst.depot, inst.capacity
        paths = [[depot, *r, depot] for r in routes]
        heads = [list(accumulate((inst.demand[c] for c in r), initial=0)) for r in routes]

        for r1 in range(len(routes)):
            for r2 in range(r1 + 1, len(routes)):
                p1, p2, h1, h2 = paths[r1], paths[r2], heads[r1], heads[r2]
                load1, load2 = h1[-1], h2[-1]
                for a in range(len(p1) - 1):  # a customers kept from the head of r1
                    u, u_next = p1[a], p1[a + 1]
                    for b in range(len(p2) - 1):  # b customers kept from the head of r2
                        if a == 0 and b == 0:
                            continue
                        if h1[a] + (load2 - h2[b]) > capacity or h2[b] + (load1 - h1[a]) > capacity:
                            continue
                        v, v_next = p2[b], p2[b + 1]
                        delta = (dist[u][v_next] + dist[v][u_next]) - (dist[u][u_next] + dist[v][v_next])
                        if delta < -EPS:
                            routes[r1], routes[r2] = routes[r1][:a] + routes[r2][b:], routes[r2][:b] + routes[r1][a:]
                            routes[:] = [r for r in routes if r]
                            return True
        return False

    def _relocate(self, routes, chain_len):
        """Move `chain_len` consecutive customers into the cheapest feasible position of another route."""
        inst = self.inst
        dist, depot, demand, capacity = inst.dist, inst.depot, inst.demand, inst.capacity
        paths = [[depot, *r, depot] for r in routes]
        loads = [sum(demand[c] for c in r) for r in routes]

        for s, src in enumerate(routes):
            for i in range(len(src) - chain_len + 1):
                chain = src[i:i + chain_len]
                chain_load = sum(demand[c] for c in chain)
                prev_s, next_s = paths[s][i], paths[s][i + chain_len + 1]
                loss = dist[prev_s][next_s] - (dist[prev_s][chain[0]] + dist[chain[-1]][next_s])

                for t, dst in enumerate(routes):
                    if t == s or loads[t] + chain_load > capacity:
                        continue
                    best_gain, best_k = inf, -1
                    for k in range(len(paths[t]) - 1):
                        prev_d, next_d = paths[t][k], paths[t][k + 1]
                        gain = (dist[prev_d][chain[0]] + dist[chain[-1]][next_d]) - dist[prev_d][next_d]
                        if gain < best_gain:
                            best_gain, best_k = gain, k

                    if loss + best_gain < -EPS:
                        del src[i:i + chain_len]
                        dst[best_k:best_k] = chain
                        if not src:
                            routes.pop(s)
                        return True
        return False

    def _swap(self, routes):
        """Exchange one customer between two routes when the combined cost drops and both stay feasible."""
        inst = self.inst
        dist, depot, demand, capacity = inst.dist, inst.depot, inst.demand, inst.capacity
        paths = [[depot, *r, depot] for r in routes]
        loads = [sum(demand[c] for c in r) for r in routes]

        for r1 in range(len(routes)):
            for r2 in range(r1 + 1, len(routes)):
                p1, p2 = paths[r1], paths[r2]
                for i in range(len(routes[r1])):
                    u, up, un = p1[i + 1], p1[i], p1[i + 2]
                    du = demand[u]
                    for j in range(len(routes[r2])):
                        v, vp, vn = p2[j + 1], p2[j], p2[j + 2]
                        dv = demand[v]
                        if loads[r1] - du + dv > capacity or loads[r2] - dv + du > capacity:
                            continue
                        old = dist[up][u] + dist[u][un] + dist[vp][v] + dist[v][vn]
                        new = dist[up][v] + dist[v][un] + dist[vp][u] + dist[u][vn]
                        if new - old < -EPS:
                            routes[r1][i], routes[r2][j] = v, u
                            return True
        return False
