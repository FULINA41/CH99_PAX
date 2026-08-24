from dataclasses import dataclass

INSERT = """
INSERT INTO parse_issue (run_id, stage, issue_kind, subject, detail)
VALUES (%(run_id)s, %(stage)s, %(kind)s, %(subject)s, %(detail)s)
"""


@dataclass(frozen=True)
class Issue:
    stage: str
    kind: str
    subject: str | None
    detail: str


def insert_issues(cursor, run_id: str | None, issues: list[Issue]) -> None:
    if not issues:
        return
    cursor.executemany(INSERT, [
        {"run_id": run_id, "stage": i.stage, "kind": i.kind,
         "subject": i.subject, "detail": i.detail}
        for i in issues
    ])
