"""Rooted containment analysis, independent of CSV and HTTP concerns."""

from collections import deque


class AmbiguousCycleError(ValueError):
    """A cycle remains after removing provably upward containment edges."""


def reachable(graph: dict[str, set[str]], root: str) -> set[str]:
    seen = {root}
    pending = [root]
    while pending:
        for child in graph.get(pending.pop(), ()):
            if child not in seen:
                seen.add(child)
                pending.append(child)
    return seen


def topological_order(graph: dict[str, set[str]]) -> list[str]:
    incoming = dict.fromkeys(graph, 0)
    for children in graph.values():
        for child in children:
            incoming[child] += 1
    pending = deque(sorted(p for p, count in incoming.items() if count == 0))
    result = []
    while pending:
        parent = pending.popleft()
        result.append(parent)
        for child in sorted(graph[parent]):
            incoming[child] -= 1
            if incoming[child] == 0:
                pending.append(child)
    return result


def repair_hierarchy(
    raw: dict[str, set[str]], root: str
) -> tuple[dict[str, set[str]], tuple[tuple[str, str], ...], list[str]]:
    """Remove self-edges and edges to unavoidable rooted ancestors.

    An ancestor dominates a node if *every* route from the root to the node
    passes through that ancestor. This is stronger than being an ancestor in
    one arbitrarily chosen DFS tree. Dominator sets converge by intersecting
    the sets of all direct parents. A remaining cycle has no justified repair
    under this conservative policy and is reported, not broken by row order.
    """
    members = reachable(raw, root)
    graph = {p: set(raw.get(p, ())) for p in sorted(members)}
    removed = {(p, p) for p, children in graph.items() if p in children}
    for p, _ in removed:
        graph[p].remove(p)
    order = topological_order(graph)
    if len(order) == len(graph):
        return graph, tuple(sorted(removed)), order

    parents = {p: set() for p in graph}
    for parent, children in graph.items():
        for child in children:
            parents[child].add(parent)
    dominators = {p: ({root} if p == root else set(members)) for p in graph}
    changed = True
    while changed:
        changed = False
        for p in graph:
            if p == root:
                continue
            common = set.intersection(*(dominators[parent] for parent in parents[p]))
            updated = common | {p}
            if updated != dominators[p]:
                dominators[p] = updated
                changed = True

    upward = {(p, c) for p, children in graph.items() for c in children if c in dominators[p]}
    for p, c in upward:
        graph[p].remove(c)
    removed.update(upward)
    order = topological_order(graph)
    if len(order) != len(graph):
        unresolved = sorted(set(graph) - set(order))
        raise AmbiguousCycleError(
            "Cycle has no unambiguous rooted-ancestor repair; unresolved parts: "
            + ", ".join(unresolved)
        )
    return graph, tuple(sorted(removed)), order
