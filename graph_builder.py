"""
Contract Dependency Graph Builder — constructs a graph of clause
interdependencies with interaction classification.

Edges come from three sources:
1. Explicit cross-references in clause text
2. Structural dependency rules from the EMS ontology
3. Shared-trigger dependencies
"""

import math
from ems_ontology import DEPENDENCY_RULES, ZONES

# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph(clauses):
    """Build a dependency graph from parsed clauses.

    Returns {"nodes": [...], "edges": [...]}.
    """
    nodes = []
    edges = []
    seen_edges = set()

    # Index clauses by family and number
    family_to_ids = {}
    number_to_id = {}
    for clause in clauses:
        cid = clause["id"]
        family = clause["family"]
        number = clause["number"]
        family_to_ids.setdefault(family, []).append(cid)
        number_to_id[number] = cid

        nodes.append({
            "id": cid,
            "zone": clause["zone"],
            "family": clause["family"],
            "title": clause["title"],
            "risk": clause["risk_rating"],
        })

    # Source 1: Explicit cross-references
    for clause in clauses:
        for ref_num in clause.get("cross_references", []):
            target_id = number_to_id.get(ref_num)
            if target_id and target_id != clause["id"]:
                edge_key = (clause["id"], target_id)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({
                        "source": clause["id"],
                        "target": target_id,
                        "type": "cross_reference",
                        "label": f"References Section {ref_num}",
                        "interaction_effect": "additive",
                    })

    # Source 2: Structural dependency rules
    for src_family, tgt_family, rel_type, label, effect in DEPENDENCY_RULES:
        src_ids = family_to_ids.get(src_family, [])
        tgt_ids = family_to_ids.get(tgt_family, [])
        for sid in src_ids:
            for tid in tgt_ids:
                edge_key = (sid, tid)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({
                        "source": sid,
                        "target": tid,
                        "type": rel_type,
                        "label": label,
                        "interaction_effect": effect,
                    })

    # Source 3: Shared-trigger dependencies
    trigger_index = {}
    for clause in clauses:
        for trigger in clause.get("triggers", []):
            key = _normalize_trigger(trigger)
            trigger_index.setdefault(key, []).append(clause["id"])

    for key, ids in trigger_index.items():
        if len(ids) > 1 and len(ids) <= 5:  # Only meaningful clusters
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    edge_key = (ids[i], ids[j])
                    rev_key = (ids[j], ids[i])
                    if edge_key not in seen_edges and rev_key not in seen_edges:
                        seen_edges.add(edge_key)
                        edges.append({
                            "source": ids[i],
                            "target": ids[j],
                            "type": "shared_trigger",
                            "label": f"Shared trigger: {key}",
                            "interaction_effect": "additive",
                        })

    # Compute layout positions
    node_positions = compute_layout(nodes)
    for node in nodes:
        node["position"] = node_positions.get(node["id"], [0, 0, 0])

    return {"nodes": nodes, "edges": edges}


def _normalize_trigger(trigger):
    """Normalize trigger text for grouping."""
    words = trigger.lower().split()[:4]
    return " ".join(words)


# ---------------------------------------------------------------------------
# Layout computation — position nodes within their zones
# ---------------------------------------------------------------------------

_GOLDEN_ANGLE = math.pi * (3 - math.sqrt(5))  # ~137.5 degrees


def compute_layout(nodes):
    """Assign 3D positions to nodes within their zones.

    Uses golden-angle spiral layout within each zone for even distribution.
    """
    # Group nodes by zone
    zone_groups = {}
    for node in nodes:
        zone = node["zone"]
        zone_groups.setdefault(zone, []).append(node["id"])

    positions = {}
    for zone_name, node_ids in zone_groups.items():
        zone_config = ZONES.get(zone_name, ZONES["manufacturer"])
        center = zone_config["position"]
        radius = 6.0  # Zone radius

        for i, nid in enumerate(node_ids):
            if len(node_ids) == 1:
                # Single node goes at center
                positions[nid] = [center[0], 1.5, center[2]]
            else:
                # Golden-angle spiral
                angle = i * _GOLDEN_ANGLE
                r = radius * math.sqrt(i + 1) / math.sqrt(len(node_ids))
                x = center[0] + r * math.cos(angle)
                y = 1.0 + (i % 3) * 1.2  # Slight vertical staggering
                z = center[2] + r * math.sin(angle)
                positions[nid] = [round(x, 2), round(y, 2), round(z, 2)]

    return positions


# ---------------------------------------------------------------------------
# Dependency chain analysis
# ---------------------------------------------------------------------------

def find_dependency_chains(graph, start_id, max_depth=6):
    """Walk the graph from a starting clause to find causal chains.

    Returns list of chains, each chain being a list of
    (clause_id, edge_label, interaction_effect) tuples.
    """
    edges_by_source = {}
    for edge in graph["edges"]:
        edges_by_source.setdefault(edge["source"], []).append(edge)

    chains = []
    _walk(edges_by_source, start_id, [], set(), max_depth, chains)
    return chains


def _walk(edges_by_source, current, path, visited, depth, chains):
    if depth <= 0:
        if path:
            chains.append(list(path))
        return

    visited.add(current)
    outgoing = edges_by_source.get(current, [])

    if not outgoing and path:
        chains.append(list(path))
    else:
        for edge in outgoing:
            target = edge["target"]
            if target not in visited:
                path.append({
                    "clause_id": target,
                    "edge_label": edge["label"],
                    "interaction_effect": edge["interaction_effect"],
                })
                _walk(edges_by_source, target, path, visited, depth - 1, chains)
                path.pop()

    visited.discard(current)


def compute_centrality(graph):
    """Compute simple degree centrality for each node.

    Returns dict of node_id -> centrality_score.
    """
    degree = {}
    for edge in graph["edges"]:
        degree[edge["source"]] = degree.get(edge["source"], 0) + 1
        degree[edge["target"]] = degree.get(edge["target"], 0) + 1

    max_degree = max(degree.values()) if degree else 1
    return {nid: round(d / max_degree, 2) for nid, d in degree.items()}
