import matplotlib
import matplotlib.pyplot as plt


def plot_solution(solution, name, bks=None, save_path=None, show=True):
    """Draw the routes of a CVRP solution, optionally saving the figure and/or displaying it.

    Args:
        solution: CVRPSolution to draw.
        name: Instance name used in the title.
        bks: Best-known solution cost, used to report the optimality gap.
        save_path: Optional file path to save the figure to (e.g. 'visualizations/X-n101-k25.png').
        show: Whether to open an interactive window.
    """
    inst = solution.instance
    depot, coords = inst.depot, inst.coords
    cmap = matplotlib.colormaps["tab20"]

    fig, ax = plt.subplots(figsize=(12, 10))
    for idx, route in enumerate(solution.routes):
        xs, ys = zip(*(coords[n] for n in [depot, *route, depot]))
        color = cmap(idx % 20)
        ax.plot(xs, ys, color=color, linewidth=1.5, alpha=0.7, zorder=1)
        ax.scatter(xs[1:-1], ys[1:-1], color=color, edgecolors="black", s=80, zorder=2,
                   label=f"Route {idx + 1} ({len(route)} customers)")

    dx, dy = coords[depot]
    ax.scatter([dx], [dy], color="red", marker="s", s=200, edgecolors="black", linewidth=2,
               label="Depot", zorder=10)

    title = f"{name} - VNS Solution\nVNS Distance: {solution.cost:.2f}"
    if bks is not None:
        gap = (solution.cost - bks) / bks * 100
        title += f" | Best-known: {bks:.2f} | Gap: {gap:.2f}%"
    ax.set_title(f"{title}\nRoutes: {len(solution.routes)}", fontsize=14, fontweight="bold")
    ax.set_xlabel("X Coordinate", fontsize=12)
    ax.set_ylabel("Y Coordinate", fontsize=12)
    ax.grid(True, linestyle="-", alpha=0.3)
    ax.legend(loc="lower left", fontsize=9, framealpha=0.9, fancybox=True)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300)
    if show:
        plt.show()
    plt.close(fig)
