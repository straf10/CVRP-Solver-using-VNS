import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np


def plot_solution(solution, bks=None, name="Instance", save_path=None, show=True):
    """
    Visualizes the CVRP solution using Matplotlib.

    Args:
        solution: The CVRPSolution object.
        bks: (Optional) Best Known Solution cost (float) to calculate Gap.
        name: Name of the instance (string).
        save_path: (Optional) Filepath to save the image (e.g., 'result.png').
        show: Whether to display the plot window (True/False).
    """
    instance = solution.instance
    routes = solution.routes
    depot_id = instance.depot
    coords = instance.coords

    # 1. Setup Figure
    plt.figure(figsize=(12, 10))

    # 2. Setup Colors (Use tab20 for distinct colors, cycle if > 20 routes)
    cmap = plt.get_cmap("tab20")
    colors = [cmap(i % 20) for i in range(len(routes))]

    # 3. Plot Routes
    for r_idx, route in enumerate(routes):
        # Build the full path of coordinates: Depot -> Node1 -> ... -> NodeN -> Depot
        path_ids = [depot_id] + route + [depot_id]

        xs = [coords[uid][0] for uid in path_ids]
        ys = [coords[uid][1] for uid in path_ids]

        color = colors[r_idx]

        # Plot the Line (Edges)
        plt.plot(xs, ys, color=color, linewidth=1.5, alpha=0.7, zorder=1)

        # Plot the Customers (Nodes) - Exclude depot from this scatter
        # We slice [1:-1] to skip the first and last point (which are the depot)
        plt.scatter(xs[1:-1], ys[1:-1], color=color, edgecolors='black', s=80, zorder=2,
                    label=f"Route {r_idx + 1} ({len(route)} customers)")

    # 4. Plot Depot (Red Square)
    dx, dy = coords[depot_id]
    plt.scatter([dx], [dy], color='red', marker='s', s=200, edgecolors='black',
                linewidth=2, label='Depot', zorder=10)

    # 5. Determine Title & Metrics
    total_dist = solution.cost
    gap_str = ""
    bks_str = ""

    if bks:
        gap = ((total_dist - bks) / bks) * 100
        gap_str = f" | Gap: {gap:.2f}%"
        bks_str = f" | Best-known: {bks:.2f}"

    main_title = f"{name} - VNS Solution\nVNS Distance: {total_dist:.2f}{bks_str}{gap_str}"
    subtitle = f"Routes: {len(routes)}"

    plt.title(f"{main_title}\n{subtitle}", fontsize=14, fontweight='bold')
    plt.xlabel("X Coordinate", fontsize=12)
    plt.ylabel("Y Coordinate", fontsize=12)

    # 6. Styling
    plt.grid(True, linestyle='-', alpha=0.3)

    # Legend settings (outside or inside depending on preference, here bottom-left like reference)
    plt.legend(loc='lower left', fontsize=9, framealpha=0.9, fancybox=True)

    # Adjust layout to prevent cutting off labels
    plt.tight_layout()

    # 7. Save or Show
    if save_path:
        plt.savefig(save_path, dpi=300)
        print(f"-> Plot saved to {save_path}")

    if show:
        plt.show()

    # Close to free memory if running in a loop
    plt.close()