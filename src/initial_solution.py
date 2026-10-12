from itertools import pairwise


class CVRPSolution:
    """A set of depot-to-depot routes. Cost is always derived from the routes, so it cannot go stale."""

    def __init__(self, instance, routes):
        self.instance = instance
        self.routes = routes

    @property
    def cost(self):
        return sum(self.route_cost(route) for route in self.routes)

    def route_cost(self, route):
        depot = self.instance.depot
        dist = self.instance.dist
        return sum(dist[u][v] for u, v in pairwise([depot, *route, depot]))

    def clone(self):
        return CVRPSolution(self.instance, [route[:] for route in self.routes])


def nearest_neighbor(instance):
    """Greedy construction: repeatedly visit the closest feasible customer, opening a new route when none fits."""
    dist, depot = instance.dist, instance.depot
    demand, capacity = instance.demand, instance.capacity
    unvisited = sorted(instance.customers)
    routes = []

    while unvisited:
        route, load, loc = [], 0, depot
        while True:
            feasible = [c for c in unvisited if load + demand[c] <= capacity]
            if not feasible:
                break
            nxt = min(feasible, key=lambda c: dist[loc][c])
            route.append(nxt)
            unvisited.remove(nxt)
            load += demand[nxt]
            loc = nxt
        routes.append(route)

    return CVRPSolution(instance, routes)
