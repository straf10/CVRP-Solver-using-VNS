import math
import os


class CVRPInstance:
    def __init__(self, filepath):
        self.filepath = filepath
        self.name = ""
        self.dimension = 0
        self.capacity = 0
        self.edge_weight_type = "EUC_2D"
        self.depot = None

        # Raw Data
        self.coords = {}
        self.demands = {}

        # Internal Mapping
        self.nodes = []
        self.id_to_idx = {}
        self.dist_matrix = []

        self._read_file(filepath)
        self._validate_data()
        self._compute_distances()

    def _read_file(self, filepath):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        section = None
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line: continue

                if line.startswith("NAME"):
                    self.name = line.split(":")[-1].strip()
                elif line.startswith("DIMENSION"):
                    self.dimension = int(line.split(":")[-1].strip())
                elif line.startswith("CAPACITY"):
                    self.capacity = int(line.split(":")[-1].strip())
                elif line.startswith("EDGE_WEIGHT_TYPE"):
                    self.edge_weight_type = line.split(":")[-1].strip().upper()

                # Section detection
                elif line.startswith("NODE_COORD_SECTION"):
                    section = "COORD"
                    continue
                elif line.startswith("DEMAND_SECTION"):
                    section = "DEMAND"
                    continue
                elif line.startswith("DEPOT_SECTION"):
                    section = "DEPOT"
                    continue
                elif line.startswith("EOF"):
                    break

                # Parsing
                if section == "COORD":
                    parts = line.split()
                    self.coords[int(parts[0])] = (float(parts[1]), float(parts[2]))
                elif section == "DEMAND":
                    parts = line.split()
                    self.demands[int(parts[0])] = int(parts[1])
                elif section == "DEPOT":
                    val = int(line)
                    if val == -1:
                        section = None
                    elif self.depot is None:
                        self.depot = val

    def _validate_data(self):
        # 1. Dimension Check
        if len(self.coords) != self.dimension:
            raise ValueError(
                f"Dimension mismatch: Header says {self.dimension}, "
                f"but found {len(self.coords)} coordinates."
            )

        # 2. Demand Check (Robustness Fix)
        # Ensure every node with coordinates has a demand entry
        missing_demands = set(self.coords.keys()) - set(self.demands.keys())
        if missing_demands:
            raise ValueError(f"Missing demands for nodes: {list(missing_demands)[:5]}...")

        # 3. Depot Check (Robustness Fix)
        if self.depot is None:
            raise ValueError("No depot defined in DEPOT_SECTION.")
        if self.depot not in self.coords:
            raise ValueError(f"Depot ID {self.depot} has no coordinates.")

    def _compute_distances(self):
        self.nodes = sorted(self.coords.keys())
        self.num_nodes = len(self.nodes)
        self.id_to_idx = {uid: i for i, uid in enumerate(self.nodes)}

        # Initialize matrix
        self.dist_matrix = [[0.0] * self.num_nodes for _ in range(self.num_nodes)]
        is_euc_2d = (self.edge_weight_type == "EUC_2D")

        for i in range(self.num_nodes):
            u = self.nodes[i]
            x1, y1 = self.coords[u]
            for j in range(i + 1, self.num_nodes):
                v = self.nodes[j]
                x2, y2 = self.coords[v]

                dist_val = math.hypot(x1 - x2, y1 - y2)
                if is_euc_2d:
                    final_dist = int(dist_val + 0.5)
                else:
                    final_dist = dist_val

                self.dist_matrix[i][j] = final_dist
                self.dist_matrix[j][i] = final_dist

    def distance(self, u, v):
        try:
            return self.dist_matrix[self.id_to_idx[u]][self.id_to_idx[v]]
        except KeyError:
            raise KeyError(f"Node ID {u} or {v} not found in instance data.")