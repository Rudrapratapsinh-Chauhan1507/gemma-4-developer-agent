"""Code graph query API for Stage 3 — Code-Relationship & Graph Retrieval.

Provides a clean, deterministic, read-only query interface over the CodeGraph.
"""

from typing import Any, Dict, List
from .ast_graph import CodeGraph

def get_code_neighbors(
    graph: CodeGraph,
    node_id: str,
    direction: str = "both"
) -> List[Dict[str, Any]]:
    """Retrieve immediate neighbors of a given node in the code graph.

    Args:
        graph: The CodeGraph instance to query.
        node_id: The exact qualified node ID (e.g. 'shop/cart.py::ShoppingCart').
        direction: One of 'incoming', 'outgoing', or 'both' (default).

    Returns:
        A list of neighbor metadata dictionaries. Each dictionary contains:
            - neighbor_id: The node ID of the neighbor
            - relationship: The edge relationship type (e.g., 'contains', 'calls')
            - direction: 'incoming' or 'outgoing'
            - node_type: The type of the neighbor node
            - symbol_name: The symbol name of the neighbor
            - qualified_name: The qualified name of the neighbor
            - file_path: The file path of the neighbor
            - line: The line number of the neighbor

    Raises:
        ValueError: If an invalid direction is provided.
    """
    valid_directions = {"incoming", "outgoing", "both"}
    if direction not in valid_directions:
        raise ValueError(
            f"Invalid direction '{direction}'. Must be one of: {valid_directions}"
        )

    if not graph.graph.has_node(node_id):
        return []

    results = []

    if direction in {"outgoing", "both"}:
        for _, successor, data in graph.graph.out_edges(node_id, data=True):
            neighbor_data = graph.get_node(successor) or {}
            results.append({
                "neighbor_id": successor,
                "relationship": data.get("relationship", "unknown"),
                "direction": "outgoing",
                "node_type": neighbor_data.get("node_type", "unknown"),
                "symbol_name": neighbor_data.get("symbol_name", successor),
                "qualified_name": neighbor_data.get("qualified_name", successor),
                "file_path": neighbor_data.get("file_path", "unknown"),
                "line": neighbor_data.get("line", 0),
            })

    if direction in {"incoming", "both"}:
        for predecessor, _, data in graph.graph.in_edges(node_id, data=True):
            neighbor_data = graph.get_node(predecessor) or {}
            results.append({
                "neighbor_id": predecessor,
                "relationship": data.get("relationship", "unknown"),
                "direction": "incoming",
                "node_type": neighbor_data.get("node_type", "unknown"),
                "symbol_name": neighbor_data.get("symbol_name", predecessor),
                "qualified_name": neighbor_data.get("qualified_name", predecessor),
                "file_path": neighbor_data.get("file_path", "unknown"),
                "line": neighbor_data.get("line", 0),
            })

    # Sort deterministically
    results.sort(key=lambda x: (x["relationship"], x["direction"], x["neighbor_id"]))

    return results


def get_code_subgraph(
    graph: CodeGraph,
    node_id: str,
    max_depth: int = 2,
    direction: str = "both",
) -> Dict[str, Any]:
    """Retrieve a bounded multi-hop neighborhood around a selected code node.

    Args:
        graph: The CodeGraph instance to query.
        node_id: The exact qualified node ID to start traversal from.
        max_depth: Maximum BFS traversal depth (default 2). Must be >= 0.
        direction: 'incoming', 'outgoing', or 'both' (default).

    Returns:
        A dictionary with "root", "nodes", and "edges" containing the traversal results.
        If node_id is not in the graph, returns {"root": None, "nodes": [], "edges": []}.
    """
    valid_directions = {"incoming", "outgoing", "both"}
    if direction not in valid_directions:
        raise ValueError(f"Invalid direction '{direction}'. Must be one of: {valid_directions}")

    if not isinstance(max_depth, int) or isinstance(max_depth, bool):
        raise TypeError("max_depth must be an integer")
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")

    if not graph.graph.has_node(node_id):
        return {"root": None, "nodes": [], "edges": []}

    root_data = graph.get_node(node_id) or {}
    root_info = {
        "node_id": node_id,
        "depth": 0,
        "node_type": root_data.get("node_type", "unknown"),
        "symbol_name": root_data.get("symbol_name", node_id),
        "qualified_name": root_data.get("qualified_name", node_id),
        "file_path": root_data.get("file_path", "unknown"),
        "line": root_data.get("line", 0),
    }

    # BFS state
    from collections import deque
    queue = deque([(node_id, 0)])
    visited_nodes: Dict[str, int] = {node_id: 0} # node_id -> min_depth
    edges = set() # Store (source, target, relationship, direction) tuples

    while queue:
        current_node, current_depth = queue.popleft()

        if current_depth >= max_depth:
            continue

        next_depth = current_depth + 1

        if direction in {"outgoing", "both"}:
            for _, successor, data in graph.graph.out_edges(current_node, data=True):
                rel = data.get("relationship", "unknown")
                edges.add((current_node, successor, rel, "outgoing"))
                if successor not in visited_nodes:
                    visited_nodes[successor] = next_depth
                    queue.append((successor, next_depth))

        if direction in {"incoming", "both"}:
            for predecessor, _, data in graph.graph.in_edges(current_node, data=True):
                rel = data.get("relationship", "unknown")
                edges.add((predecessor, current_node, rel, "incoming"))
                if predecessor not in visited_nodes:
                    visited_nodes[predecessor] = next_depth
                    queue.append((predecessor, next_depth))

    # Format nodes
    nodes_out = []
    for n_id, depth in visited_nodes.items():
        if n_id == node_id:
            continue # root is separate
        n_data = graph.get_node(n_id) or {}
        nodes_out.append({
            "node_id": n_id,
            "depth": depth,
            "node_type": n_data.get("node_type", "unknown"),
            "symbol_name": n_data.get("symbol_name", n_id),
            "qualified_name": n_data.get("qualified_name", n_id),
            "file_path": n_data.get("file_path", "unknown"),
            "line": n_data.get("line", 0),
        })

    # Sort deterministically
    nodes_out.sort(key=lambda x: (x["depth"], x["node_id"]))

    edges_out = []
    for src, tgt, rel, drct in edges:
        edges_out.append({
            "source": src,
            "target": tgt,
            "relationship": rel,
            "direction": drct,
        })
    edges_out.sort(key=lambda x: (x["source"], x["target"], x["relationship"]))

    return {
        "root": root_info,
        "nodes": nodes_out,
        "edges": edges_out,
    }
