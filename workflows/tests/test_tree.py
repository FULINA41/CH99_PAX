from parsing.tree import build_nodes, inherit


def row(indent, description, htsno=None, superior=None):
    return {"indent": str(indent), "description": description,
            "htsno": htsno or "", "superior": superior}


def test_heading_rows_become_context_on_their_descendants_not_rows_of_their_own():
    nodes, _ = build_nodes([
        row(0, "Sugars, syrups and molasses:", superior="true"),
        row(1, "Described in U.S. note 15(a):", superior="true"),
        row(2, "First quota period", "9903.17.01"),
    ], "ch99")

    assert [node.hts for node in nodes] == ["9903.17.01"]
    assert nodes[0].full_description == (
        "Sugars, syrups and molasses: Described in U.S. note 15(a): First quota period")


def test_a_statistical_line_two_levels_below_its_parent_still_finds_it():
    # 12 rows in the base export skip a level like this.
    nodes, _ = build_nodes([
        row(1, "Other materials", "2620.99.75"),
        row(3, "Vanadium bearing materials", "2620.99.75.20"),
    ], "base")

    assert nodes[1].parent_hts == "2620.99.75"


def test_a_child_whose_code_contradicts_its_indent_is_reported():
    _, issues = build_nodes([
        row(0, "Live horses", "0101"),
        row(1, "Something else entirely", "9999.99.99"),
    ], "base")

    assert [issue.kind for issue in issues] == ["parent_prefix_mismatch"]


def test_a_shorter_code_is_not_treated_as_a_parent_unless_it_ends_at_a_separator():
    _, issues = build_nodes([
        row(0, "Parent", "2922.49.3"),
        row(1, "Child", "2922.49.30"),
    ], "base")

    assert [issue.kind for issue in issues] == ["parent_prefix_mismatch"]


def test_inheritance_names_the_nearest_ancestor_that_states_a_value():
    nodes, _ = build_nodes([
        row(0, "Amino-acids", "2922.49"),
        row(1, "Other amino acids", "2922.49.49"),
        row(2, "Alanine", "2922.49.49.10"),
    ], "base")
    stated = {"2922.49.49"}

    assert inherit(nodes, lambda n: n.hts in stated) == {"2922.49.49.10": "2922.49.49"}


def test_a_row_that_states_its_own_value_inherits_nothing():
    nodes, _ = build_nodes([
        row(0, "Parent", "0101"),
        row(1, "Child", "0101.21"),
    ], "base")

    assert inherit(nodes, lambda n: True) == {}
