import math
import os


class CVRPInstance:
    def __init__(self, filepath):
        self.filepath = filepath
        self.name = ""
        self.dimension = 0
        self.capacity = 0
        self.edge_weight_type = "EUC_2D"  # Default fallback
        self.depot = None

        # Raw Data
        self.coords = {}  # {real_id: (x, y)}
        self.demands = {}  # {real_id: demand}

        # Internal Mapping (για χειρισμό sparse IDs)
        self.nodes = []  # Λίστα με τα real_ids ταξινομημένα
        self.id_to_idx = {}  # {real_id: matrix_index}
        self.dist_matrix = []  # NxN matrix

        # Εκτέλεση ροής
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

                # Header Parsing
                if line.startswith("NAME"):
                    self.name = line.split(":")[-1].strip()
                elif line.startswith("DIMENSION"):
                    self.dimension = int(line.split(":")[-1].strip())
                elif line.startswith("CAPACITY"):
                    self.capacity = int(line.split(":")[-1].strip())
                elif line.startswith("EDGE_WEIGHT_TYPE"):
                    # Normalize: strip spaces and uppercase
                    self.edge_weight_type = line.split(":")[-1].strip().upper()

                # Section Detection
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

                # Data Parsing
                if section == "COORD":
                    parts = line.split()
                    node_id = int(parts[0])
                    x = float(parts[1])
                    y = float(parts[2])
                    self.coords[node_id] = (x, y)

                elif section == "DEMAND":
                    parts = line.split()
                    node_id = int(parts[0])
                    demand = int(parts[1])
                    self.demands[node_id] = demand

                elif section == "DEPOT":
                    val = int(line)
                    if val == -1:
                        section = None
                    else:
                        if self.depot is None:
                            self.depot = val

    def _validate_data(self):
        # 1. Dimension Check
        if len(self.coords) != self.dimension:
            raise ValueError(
                f"Dimension mismatch: Header says {self.dimension}, "
                f"but found {len(self.coords)} coordinates."
            )

        # 2. Demand Check
        missing_demands = set(self.coords.keys()) - set(self.demands.keys())
        if missing_demands:
            raise ValueError(f"Missing demands for nodes: {missing_demands}")

        # 3. Depot Check
        if self.depot is None:
            raise ValueError("No depot defined in DEPOT_SECTION.")
        if self.depot not in self.coords:
            raise ValueError(f"Depot ID {self.depot} has no coordinates.")

    def _compute_distances(self):
        """
        Δημιουργεί τον πίνακα NxN χρησιμοποιώντας mapping.
        """
        # Ταξινομούμε τα IDs για συνέπεια
        self.nodes = sorted(self.coords.keys())
        self.num_nodes = len(self.nodes)

        # Δημιουργία Mapping: Real ID -> Matrix Index (0..N-1)
        self.id_to_idx = {uid: i for i, uid in enumerate(self.nodes)}

        # Αρχικοποίηση πίνακα NxN
        self.dist_matrix = [[0.0] * self.num_nodes for _ in range(self.num_nodes)]

        is_euc_2d = (self.edge_weight_type == "EUC_2D")

        # Υπολογισμός μόνο για j > i (Upper Triangle) και mirroring
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

                # Άμεση ανάθεση και στα δύο κελιά
                self.dist_matrix[i][j] = final_dist
                self.dist_matrix[j][i] = final_dist

    def distance(self, u, v):
        """
        Επιστρέφει την απόσταση μεταξύ των κόμβων με Real IDs u και v.
        """
        try:
            idx_u = self.id_to_idx[u]
            idx_v = self.id_to_idx[v]
            return self.dist_matrix[idx_u][idx_v]
        except KeyError as e:
            raise KeyError(f"Node ID {e} not found in instance.")

    def __repr__(self):
        return (f"Instance: {self.name}\n"
                f"Type: {self.edge_weight_type}\n"
                f"Nodes: {self.dimension} (Depot: {self.depot})\n"
                f"Capacity: {self.capacity}")


# --- Test Case για τον έλεγχο ---
if __name__ == "__main__":
    # Test με "περίεργα" IDs (1, 10, 20) και EUC_2D
    dummy_vrp = """NAME : Sparse-Test
DIMENSION : 3
CAPACITY : 50
EDGE_WEIGHT_TYPE : EUC_2D
NODE_COORD_SECTION
1 0 0
10 3 4
20 10 0
DEMAND_SECTION
1 0
10 5
20 10
DEPOT_SECTION
1
-1
EOF
"""
    with open("sparse_test.vrp", "w") as f:
        f.write(dummy_vrp)

    try:
        inst = CVRPInstance("sparse_test.vrp")
        print(inst)

        # Test 1: Απόσταση 1->10 (Pythagoras 3-4-5)
        # Real IDs: 1 και 10. Indices: 0 και 1.
        d1 = inst.distance(1, 10)
        print(f"Dist 1->10 (Expect 5): {d1}")

        # Test 2: Απόσταση 1->20 (Euclidean 10)
        d2 = inst.distance(1, 20)
        print(f"Dist 1->20 (Expect 10): {d2}")

        # Test 3: Λάθος ID
        # inst.distance(1, 999) # Θα πετάξει KeyError

    except Exception as e:
        print(f"Error: {e}")