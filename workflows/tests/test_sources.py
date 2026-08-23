from sources import source_by_key


def test_pdf_url_pins_the_requested_release():
    assert "release=2026HTSRev16" in source_by_key("notes_pdf").url("2026HTSRev16")


def test_pdf_url_asks_for_the_current_release_when_none_is_given():
    assert "release=currentRelease" in source_by_key("notes_pdf").url(None)


def test_export_url_is_the_same_with_or_without_a_release():
    # The exportList endpoint takes no release parameter, so a pinned release cannot
    # change what it serves. Pretending otherwise would hide a mid-run release change.
    export = source_by_key("ch99")
    assert export.url("2026HTSRev16") == export.url(None)
