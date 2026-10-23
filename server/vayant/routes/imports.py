from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Response

from ..importing import pipeline
from ..importing.parse import DATE_FORMATS, Mapping, Parsed
from ..schemas import ImportCommit, ImportFile, ImportPreview, ImportRecord, ImportResult
from . import DB

router = APIRouter(tags=["imports"])


def _parse(db: DB, body: ImportFile) -> tuple[dict, Parsed, bool]:
    account = pipeline.load_account(db, body.account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    mapping = None
    if body.mapping:
        if body.mapping.date_format not in DATE_FORMATS:
            raise HTTPException(422, "Unsupported date format")
        if (body.mapping.amount is None) == (body.mapping.debit is None and body.mapping.credit is None):
            raise HTTPException(422, "Map either an amount column or debit/credit columns")
        mapping = Mapping(**body.mapping.model_dump())
    parsed, profile_used = pipeline.parse_file(db, account, body.filename, body.content, mapping)
    return account, parsed, profile_used


@router.post("/imports/preview", response_model=ImportPreview)
def preview(body: ImportFile, db: DB):
    """Reads the file without saving anything: column guesses, every row's status and suggested category."""
    account, parsed, profile_used = _parse(db, body)
    return {
        "format": parsed.format, "header": parsed.header, "columns": parsed.columns, "sample": parsed.sample,
        "mapping": asdict(parsed.mapping) if parsed.mapping else None, "date_formats": parsed.date_formats,
        "profile_used": profile_used, "rows": pipeline.review(db, account, parsed),
        "skipped": [{"line": line, "reason": reason} for line, reason in parsed.skipped],
        "ledger_balance": {"amount": parsed.ledger_balance[0], "as_of": parsed.ledger_balance[1]} if parsed.ledger_balance else None,
        "file_currency": parsed.currency,
    }


@router.post("/imports", response_model=ImportResult)
def commit(body: ImportCommit, db: DB):
    account, parsed, _ = _parse(db, body)
    if not parsed.rows:
        raise HTTPException(422, "No transactions found in the file with this mapping")
    choices = {c.hash: c.model_dump() for c in body.choices}
    known = (body.balance.amount, body.balance.as_of) if body.balance else None
    return pipeline.commit(db, account, body.filename, parsed, choices, known)


@router.get("/imports", response_model=list[ImportRecord])
def list_imports(db: DB, account_id: int | None = None):
    return db.execute("""
        SELECT i.id, i.account_id, a.name AS account_name, i.filename, i.format, i.row_count, i.created_at
        FROM imports i JOIN accounts a ON a.id = i.account_id
        WHERE %(acct)s::int IS NULL OR i.account_id = %(acct)s
        ORDER BY i.created_at DESC LIMIT 50""", {"acct": account_id}).fetchall()


@router.delete("/imports/{import_id}", status_code=204)
def undo_import(import_id: int, db: DB):
    """Removes the import's transactions and the balances it recorded."""
    if not db.execute("DELETE FROM imports WHERE id = %s", (import_id,)).rowcount:
        raise HTTPException(404, "Import not found")
    return Response(status_code=204)
