import sys


class CVRPSolution:
    def __init__(self, instance, routes):
        self.instance = instance
        self.routes = routes
        self.cost = self.compute_total_cost()

    def compute_total_cost(self):
        total = 0.0
        for route in self.routes:
            total += self.calculate_route_cost(self.instance, route)
        return total

    @staticmethod
    def calculate_route_cost(instance, route):
        if not route: return 0.0
        cost = 0.0
        depot = instance.depot
        cost += instance.distance(depot, route[0])
        for i in range(len(route) - 1):
            cost += instance.distance(route[i], route[i + 1])
        cost += instance.distance(route[-1], depot)
        return cost

    def clone(self):
        import copy
        return CVRPSolution(self.instance, copy.deepcopy(self.routes))


def solve_nearest_neighbor(instance):
    unvisited = set(instance.nodes)
    if instance.depot in unvisited:
        unvisited.remove(instance.depot)

    routes = []
    current_route = []
    current_load = 0
    current_loc = instance.depot

    while unvisited:
        best_node = None
        min_dist = float('inf')
        candidates = sorted(list(unvisited))

        for candidate in candidates:
            demand = instance.demands[candidate]
            if current_load + demand <= instance.capacity:
                dist = instance.distance(current_loc, candidate)
                if dist < min_dist:
                    min_dist = dist
                    best_node = candidate

        if best_node is not None:
            current_route.append(best_node)
            current_load += instance.demands[best_node]
            current_loc = best_node
            unvisited.remove(best_node)
        else:
            if current_loc == instance.depot:
                # This implies there is a customer with Demand > Capacity
                raise ValueError("Instance contains a customer with demand > capacity, or NN failed.")

            # Close current route and return to depot
            routes.append(current_route)
            current_route = []
            current_load = 0
            current_loc = instance.depot

    if current_route:
        routes.append(current_route)

    return CVRPSolution(instance, routes)