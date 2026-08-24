from dataclasses import dataclass
from typing import Any, Iterable

from parsing.issues import Issue


@dataclass(frozen=True)
class Node:
    hts: str
    parent_hts: str | None
    indent: int
    description: str
    full_description: str
    row: dict[str, Any]


def build_nodes(rows: Iterable[dict[str, Any]], stage: str) -> tuple[list[Node], list[Issue]]:
    """Rebuild the schedule's tree and attach each row's inherited wording.

    Rows without a code are heading rows. They are not emitted -- they cannot be
    classified against and carry no rate -- but their prose scopes their descendants,
    so it stays in every descendant's ``full_description`` (D-0012).

    Args:
        rows: Export rows in document order, each with ``indent``, ``description``
            and possibly ``htsno``.
        stage: Which parse task is running, recorded on any issue raised.

    Returns:
        The coded nodes in document order, and the issues found while validating.
    """
    stack: list[tuple[int, str, str | None]] = []
    nodes: list[Node] = []
    issues: list[Issue] = []

    for row in rows:
        indent = int(row["indent"])
        # Pop to the row's own level: whatever is left is its ancestor chain. This
        # survives the 12 places where indent jumps by more than one, because it asks
        # for the nearest shallower row rather than for indent - 1.
        while stack and stack[-1][0] >= indent:
            stack.pop()

        description = row["description"]
        full = " ".join([entry[1] for entry in stack] + [description])
        code = row.get("htsno") or None

        if code:
            parent = next((entry[2] for entry in reversed(stack) if entry[2]), None)
            # The tree came from indent; the codes are an independent statement of the
            # same hierarchy. Where they disagree, one of them is wrong and the row is
            # not silently accepted.
            if parent and not _under(code, parent):
                issues.append(Issue(
                    stage=stage,
                    kind="parent_prefix_mismatch",
                    subject=code,
                    detail=f"indent puts {code} under {parent}, but its code is not",
                ))
            nodes.append(Node(code, parent, indent, description, full, row))

        stack.append((indent, description, code))

    return nodes, issues


def inherit(nodes: list[Node], has_own) -> dict[str, str]:
    """Say, for each node lacking a value, which ancestor supplies it.

    Args:
        nodes: Coded nodes from ``build_nodes``.
        has_own: Predicate returning whether a node states the value itself.

    Returns:
        Node code -> the ancestor's code. A node that states its own value, or has no
        ancestor that states one, is absent from the mapping.
    """
    by_code = {node.hts: node for node in nodes}
    inherited: dict[str, str] = {}

    for node in nodes:
        if has_own(node):
            continue
        ancestor = node.parent_hts
        while ancestor and not has_own(by_code[ancestor]):
            ancestor = by_code[ancestor].parent_hts
        if ancestor:
            inherited[node.hts] = ancestor

    return inherited


# A parent's code must be the child's code or a dotted prefix of it. Anchoring on the
# separator matters: a bare startswith would accept 2922.49.3 as a parent of 2922.49.30.
def _under(code: str, parent: str) -> bool:
    return code == parent or code.startswith(parent + ".")
