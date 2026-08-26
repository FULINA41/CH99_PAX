from parsing.cumulation import disagrees, states_cumulation


def test_a_note_displacing_note_one_is_read_as_cumulative():
    # This is the sentence that decides whether a bare rate is charged on top of the ordinary
    # duty or instead of it, and it opens 31 of the notes that carry the language.
    assert states_cumulation(
        "Notwithstanding U.S. note 1 to this subchapter, all products that are subject to "
        "the additional ad valorem rates of duty imposed by these headings shall also be "
        "subject to the general rates of duty imposed under subheadings in chapters 1 to 97"
    ) == "cumulative"


def test_the_subchapter_default_is_read_as_in_lieu():
    assert states_cumulation(
        "any article described in the provisions of this subchapter, for which rates of duty "
        "are herein provided, if entered during the period specified, is subject to duty at "
        "the rate set forth herein in lieu of the rate provided therefor in chapters 1 to 98"
    ) == "in_lieu"


def test_cumulative_requirements_are_not_cumulative_duties():
    # U.S. note 16(e) says derivative articles must satisfy "cumulative" requirements. That is
    # a statement about conditions, not about how duties combine, and reading it as the latter
    # would turn a replacement into an addition on eleven provisions.
    assert states_cumulation(
        "These requirements are cumulative such that a derivative article in more than one "
        "subdivision must satisfy each requirement"
    ) is None


def test_a_note_saying_neither_leaves_the_default_standing():
    assert states_cumulation(
        "For the purposes of heading 9903.88.01, products of China shall be subject to an "
        "additional 25 percent ad valorem rate of duty"
    ) is None


def test_a_rate_naming_the_base_never_disagrees_with_the_note():
    # "The duty provided in the applicable subheading + 25%" states its own relation to the
    # base. That is note 1's "unless the context requires otherwise", not a contradiction --
    # treating it as one raised 62 issues about provisions that were read correctly.
    assert disagrees("in_lieu", "additive",
                     "The duty provided in the applicable subheading + 25%") is False


def test_a_bare_rate_under_a_cumulative_note_is_flagged():
    # 9903.05.39 prints "10%" and says nothing about the base; U.S. note 52(a) says the
    # heading imposes an additional duty. Read from the rate alone it replaced a 16.5% base.
    assert disagrees("cumulative", "replace", "10%") is True


def test_a_bare_rate_agreeing_with_its_note_is_not_flagged():
    assert disagrees("in_lieu", "replace", "10%") is False
