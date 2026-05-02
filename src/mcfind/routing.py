from __future__ import annotations

from dataclasses import dataclass
from math import inf

from mcfind.coords import distance_blocks
from mcfind.models import ResultRecord


@dataclass(frozen=True, slots=True)
class RoutePlan:
    results: list[ResultRecord]
    total_distance_blocks: float
    algorithm: str


_EXACT_GROUP_LIMIT = 10
_EXACT_CANDIDATE_LIMIT = 60


def plan_route(origin: tuple[int, int], candidates_by_structure: dict[str, list[ResultRecord]]) -> RoutePlan:
    available = {name: records for name, records in candidates_by_structure.items() if records}
    if not available:
        return RoutePlan(results=[], total_distance_blocks=0.0, algorithm="exact")

    total_candidates = sum(len(records) for records in available.values())
    if len(available) <= _EXACT_GROUP_LIMIT and total_candidates <= _EXACT_CANDIDATE_LIMIT:
        return _plan_route_exact(origin, available)
    return _plan_route_heuristic(origin, available)


def _distance_from_origin(origin: tuple[int, int], record: ResultRecord) -> float:
    return distance_blocks(origin[0], origin[1], record.x, record.z)


def _distance_between(left: ResultRecord, right: ResultRecord) -> float:
    return distance_blocks(left.x, left.z, right.x, right.z)


def _reconstruct_group_path(
    order: list[str],
    candidates_by_structure: dict[str, list[ResultRecord]],
    parents: list[dict[int, int | None]],
    last_index: int,
) -> list[ResultRecord]:
    selected: list[ResultRecord] = []
    current_index: int | None = last_index
    for position in range(len(order) - 1, -1, -1):
        assert current_index is not None
        group = order[position]
        selected.append(candidates_by_structure[group][current_index])
        current_index = parents[position].get(current_index)
    selected.reverse()
    return selected


def _solve_order(
    origin: tuple[int, int],
    order: list[str],
    candidates_by_structure: dict[str, list[ResultRecord]],
) -> tuple[list[ResultRecord], float]:
    if not order:
        return [], 0.0

    first_group = order[0]
    costs = {
        index: _distance_from_origin(origin, record)
        for index, record in enumerate(candidates_by_structure[first_group])
    }
    parents: list[dict[int, int | None]] = [{index: None for index in costs}]

    for position in range(1, len(order)):
        previous_group = order[position - 1]
        group = order[position]
        previous_candidates = candidates_by_structure[previous_group]
        group_candidates = candidates_by_structure[group]
        next_costs: dict[int, float] = {}
        next_parents: dict[int, int | None] = {}
        for index, record in enumerate(group_candidates):
            best_parent: int | None = None
            best_cost = inf
            for previous_index, previous_cost in costs.items():
                candidate_cost = previous_cost + _distance_between(previous_candidates[previous_index], record)
                if candidate_cost < best_cost:
                    best_cost = candidate_cost
                    best_parent = previous_index
            next_costs[index] = best_cost
            next_parents[index] = best_parent
        costs = next_costs
        parents.append(next_parents)

    last_index, total = min(costs.items(), key=lambda item: item[1])
    return _reconstruct_group_path(order, candidates_by_structure, parents, last_index), total


def _plan_route_exact(origin: tuple[int, int], candidates_by_structure: dict[str, list[ResultRecord]]) -> RoutePlan:
    groups = list(candidates_by_structure)
    group_index = {name: index for index, name in enumerate(groups)}
    nodes: list[tuple[str, ResultRecord]] = []
    nodes_by_group: dict[str, list[int]] = {name: [] for name in groups}

    for name in groups:
        for record in candidates_by_structure[name]:
            node_index = len(nodes)
            nodes.append((name, record))
            nodes_by_group[name].append(node_index)

    costs: dict[tuple[int, int], float] = {}
    parents: dict[tuple[int, int], tuple[int, int] | None] = {}
    for node_index, (name, record) in enumerate(nodes):
        mask = 1 << group_index[name]
        costs[(mask, node_index)] = _distance_from_origin(origin, record)
        parents[(mask, node_index)] = None

    full_mask = (1 << len(groups)) - 1
    for visited_count in range(1, len(groups)):
        next_costs = dict(costs)
        next_parents = dict(parents)
        for (mask, node_index), cost in costs.items():
            if mask.bit_count() != visited_count:
                continue
            current_name, current_record = nodes[node_index]
            for next_name in groups:
                next_group_mask = 1 << group_index[next_name]
                if next_name == current_name or mask & next_group_mask:
                    continue
                for next_index in nodes_by_group[next_name]:
                    next_record = nodes[next_index][1]
                    candidate_cost = cost + _distance_between(current_record, next_record)
                    next_state = (mask | next_group_mask, next_index)
                    if candidate_cost < next_costs.get(next_state, inf):
                        next_costs[next_state] = candidate_cost
                        next_parents[next_state] = (mask, node_index)
        costs = next_costs
        parents = next_parents

    final_state, total = min(
        ((state, cost) for state, cost in costs.items() if state[0] == full_mask),
        key=lambda item: item[1],
    )

    ordered_nodes: list[ResultRecord] = []
    state: tuple[int, int] | None = final_state
    while state is not None:
        _, node_index = state
        ordered_nodes.append(nodes[node_index][1])
        state = parents[state]
    ordered_nodes.reverse()
    return RoutePlan(results=ordered_nodes, total_distance_blocks=total, algorithm="exact")


def _build_greedy_group_order(origin: tuple[int, int], candidates_by_structure: dict[str, list[ResultRecord]]) -> list[str]:
    remaining = list(candidates_by_structure)
    order: list[str] = []
    prefix_costs: dict[int, float] | None = None
    previous_group: str | None = None

    while remaining:
        best_group: str | None = None
        best_cost = inf
        best_next_costs: dict[int, float] | None = None
        for group in remaining:
            group_candidates = candidates_by_structure[group]
            if previous_group is None:
                next_costs = {
                    index: _distance_from_origin(origin, record)
                    for index, record in enumerate(group_candidates)
                }
            else:
                assert prefix_costs is not None
                previous_candidates = candidates_by_structure[previous_group]
                next_costs = {}
                for index, record in enumerate(group_candidates):
                    next_costs[index] = min(
                        prefix_costs[previous_index] + _distance_between(previous_candidates[previous_index], record)
                        for previous_index in prefix_costs
                    )
            candidate_total = min(next_costs.values(), default=inf)
            if candidate_total < best_cost:
                best_group = group
                best_cost = candidate_total
                best_next_costs = next_costs
        assert best_group is not None
        order.append(best_group)
        remaining.remove(best_group)
        prefix_costs = best_next_costs
        previous_group = best_group
    return order


def _improve_order_with_two_opt(
    origin: tuple[int, int],
    order: list[str],
    candidates_by_structure: dict[str, list[ResultRecord]],
) -> list[str]:
    best_order = list(order)
    _, best_cost = _solve_order(origin, best_order, candidates_by_structure)
    improved = True
    while improved:
        improved = False
        for start in range(len(best_order) - 1):
            for end in range(start + 2, len(best_order) + 1):
                candidate_order = best_order[:start] + list(reversed(best_order[start:end])) + best_order[end:]
                _, candidate_cost = _solve_order(origin, candidate_order, candidates_by_structure)
                if candidate_cost + 1e-9 < best_cost:
                    best_order = candidate_order
                    best_cost = candidate_cost
                    improved = True
                    break
            if improved:
                break
    return best_order


def _plan_route_heuristic(origin: tuple[int, int], candidates_by_structure: dict[str, list[ResultRecord]]) -> RoutePlan:
    order = _build_greedy_group_order(origin, candidates_by_structure)
    improved_order = _improve_order_with_two_opt(origin, order, candidates_by_structure)
    records, total = _solve_order(origin, improved_order, candidates_by_structure)
    return RoutePlan(results=records, total_distance_blocks=total, algorithm="heuristic-2opt")
