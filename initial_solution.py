import sys

try:
    from CVRP_Instance import CVRPInstance
except ImportError:
    pass


class CVRPSolution:
    def __init__(self, instance, routes):
        self.instance = instance
        self.routes = routes
        # Υπολογισμός κόστους κατά την αρχικοποίηση
        self.cost = self.compute_total_cost()

    def compute_total_cost(self):
        """Υπολογίζει το συνολικό κόστος όλων των διαδρομών."""
        total = 0.0
        for route in self.routes:
            total += self.calculate_route_cost(self.instance, route)
        return total

    @staticmethod
    def calculate_route_cost(instance, route):
        """Static method: Υπολογίζει το κόστος μίας διαδρομής."""
        if not route: return 0.0
        cost = 0.0
        depot = instance.depot

        # Depot -> First
        cost += instance.distance(depot, route[0])
        # Node -> Node
        for i in range(len(route) - 1):
            cost += instance.distance(route[i], route[i + 1])
        # Last -> Depot
        cost += instance.distance(route[-1], depot)

        return cost

    def clone(self):
        """Δημιουργεί ένα βαθύ αντίγραφο της λύσης (χρήσιμο για τον VNS)."""
        import copy
        return CVRPSolution(self.instance, copy.deepcopy(self.routes))

    def __repr__(self):
        return f"CVRPSolution(Cost: {self.cost:.2f}, Vehicles: {len(self.routes)})"


def solve_nearest_neighbor(instance):
    """Ντετερμινιστικός Nearest Neighbor"""
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
                # Αν δεν χωράει ούτε σε άδειο, υπάρχει πρόβλημα στα δεδομένα
                pass

            routes.append(current_route)
            current_route = []
            current_load = 0
            current_loc = instance.depot

    if current_route:
        routes.append(current_route)

    return CVRPSolution(instance, routes)