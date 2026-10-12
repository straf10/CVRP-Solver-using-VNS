import math

SECTIONS = {"NODE_COORD_SECTION": "coord", "DEMAND_SECTION": "demand", "DEPOT_SECTION": "depot"}


class CVRPInstance:
    """A TSPLIB-format CVRP instance with a precomputed distance matrix."""

    def __init__(self, filepath):
        self.filepath = filepath
        self.name = ""
        self.dimension = 0
        self.capacity = 0
        self.edge_weight_type = "EUC_2D"
        self.depot = None
        self.coords = {}
        self.demand = {}

        self._parse()
        self._validate()

        self.nodes = sorted(self.coords)
        self.customers = [n for n in self.nodes if n != self.depot]
        self.dist = self._build_distances()

    def _parse(self):
        section = None
        with open(self.filepath, "r") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                if line == "EOF":
                    break
                if line in SECTIONS:
                    section = SECTIONS[line]
                    continue

                key, sep, value = line.partition(":")
                if sep:
                    key, value = key.strip(), value.strip()
                    if key == "NAME":
                        self.name = value
                    elif key == "DIMENSION":
                        self.dimension = int(value)
                    elif key == "CAPACITY":
                        self.capacity = int(value)
                    elif key == "EDGE_WEIGHT_TYPE":
                        self.edge_weight_type = value.upper()
                elif section == "coord":
                    node, x, y = line.split()[:3]
                    self.coords[int(node)] = (float(x), float(y))
                elif section == "demand":
                    node, demand = line.split()[:2]
                    self.demand[int(node)] = int(demand)
                elif section == "depot":
                    node = int(line)
                    if node == -1:
                        section = None
                    elif self.depot is None:
                        self.depot = node

    def _validate(self):
        if len(self.coords) != self.dimension:
            raise ValueError(
                f"Dimension mismatch: header says {self.dimension}, "
                f"found {len(self.coords)} coordinates."
            )
        if self.depot is None:
            raise ValueError("No depot defined in DEPOT_SECTION.")
        if self.depot not in self.coords:
            raise ValueError(f"Depot ID {self.depot} has no coordinates.")

        missing = sorted(set(self.coords) - set(self.demand))
        if missing:
            raise ValueError(f"Missing demands for nodes: {missing[:5]}...")

        oversized = [n for n in self.coords if n != self.depot and self.demand[n] > self.capacity]
        if oversized:
            raise ValueError(f"Customer {oversized[0]} demand exceeds vehicle capacity {self.capacity}.")

    def _build_distances(self):
        round_nint = self.edge_weight_type == "EUC_2D"

        def metric(u, v):
            (x1, y1), (x2, y2) = self.coords[u], self.coords[v]
            d = math.hypot(x1 - x2, y1 - y2)
            return int(d + 0.5) if round_nint else d

        return {u: {v: metric(u, v) for v in self.nodes} for u in self.nodes}
