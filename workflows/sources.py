"""
The three USITC sources the scraper fetches, and how to address each one.

Only the notes PDF endpoint accepts a release parameter. The two bulk exports always
serve whatever is current, which is why a run records the release it saw before and
after fetching rather than assuming one.
"""

from dataclasses import dataclass

REST_ROOT = "https://hts.usitc.gov/reststop"
CURRENT_RELEASE = "currentRelease"
RELEASE_URL = f"{REST_ROOT}/currentRelease"


@dataclass(frozen=True)
class Source:
    key: str
    filename: str
    describes: str
    template: str
    pinnable: bool

    def url(self, release: str | None = None) -> str:
        """The address to fetch, pinned to `release` where the endpoint allows it."""
        if not self.pinnable:
            return self.template
        return self.template.format(release=release or CURRENT_RELEASE)


SOURCES: tuple[Source, ...] = (
    Source(
        key="ch99",
        filename="ch99.json",
        describes="Chapter 99 provisions",
        template=f"{REST_ROOT}/exportList?from=9900&to=9999&format=JSON&styles=false",
        pinnable=False,
    ),
    Source(
        key="base",
        filename="base.json",
        describes="Chapters 1-97, the base schedule Chapter 99 points at",
        template=f"{REST_ROOT}/exportList?from=0100&to=9799&format=JSON&styles=false",
        pinnable=False,
    ),
    Source(
        key="notes_pdf",
        filename="ch99-notes.pdf",
        describes="Chapter 99 document, including the U.S. Notes",
        template=f"{REST_ROOT}/file?release={{release}}&filename=Chapter%2099",
        pinnable=True,
    ),
)

SOURCE_KEYS = frozenset(source.key for source in SOURCES)


def source_by_key(key: str) -> Source:
    for source in SOURCES:
        if source.key == key:
            return source
    raise KeyError(f"unknown source: {key}")
