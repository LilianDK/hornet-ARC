"""hornet-ARC: Microservice für Projektreferenzen (FastAPI + SQLite)."""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("HORNET_DB", BASE_DIR.parent / "data" / "referenzen.db"))
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
TEXT_FIELDS = ["name", "kunde", "von", "bis", "beschreibung", "situation", "herausforderungen", "loesung", "sonstiges"]


# ---------- Datenbank ----------
def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS referenzen (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                kunde TEXT NOT NULL,
                von TEXT NOT NULL,
                bis TEXT NOT NULL DEFAULT '',
                laufend INTEGER NOT NULL DEFAULT 0,
                volumenWert REAL NOT NULL,
                volumenEinheit TEXT NOT NULL CHECK (volumenEinheit IN ('PT','EUR')),
                beschreibung TEXT NOT NULL,
                situation TEXT NOT NULL DEFAULT '',
                herausforderungen TEXT NOT NULL DEFAULT '',
                loesung TEXT NOT NULL DEFAULT '',
                sonstiges TEXT NOT NULL DEFAULT '',
                createdAt TEXT NOT NULL,
                updatedAt TEXT NOT NULL
            )"""
        )


@contextmanager
def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["laufend"] = bool(d["laufend"])
    return d


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------- Modelle ----------
class ReferenzIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kunde: str = Field(min_length=1, max_length=200)
    von: str
    bis: str = ""
    laufend: bool = False
    volumenWert: float = Field(ge=0)
    volumenEinheit: Literal["PT", "EUR"] = "PT"
    beschreibung: str = Field(min_length=1, max_length=1500)
    situation: str = Field(default="", max_length=8000)
    herausforderungen: str = Field(default="", max_length=8000)
    loesung: str = Field(default="", max_length=8000)
    sonstiges: str = Field(default="", max_length=8000)

    @field_validator("name", "kunde", "beschreibung", "situation", "herausforderungen", "loesung", "sonstiges", "von", "bis", mode="before")
    @classmethod
    def strip(cls, v):
        return (v or "").strip() if isinstance(v, str) or v is None else v

    @model_validator(mode="after")
    def check_zeitraum(self):
        if not MONTH.match(self.von):
            raise ValueError("'von' muss im Format JJJJ-MM sein")
        if self.laufend:
            self.bis = ""
        else:
            if not MONTH.match(self.bis):
                raise ValueError("'bis' muss im Format JJJJ-MM sein oder 'laufend' gesetzt werden")
            if self.bis < self.von:
                raise ValueError("'bis' liegt vor 'von'")
        return self


class Referenz(ReferenzIn):
    id: str
    createdAt: str
    updatedAt: str


# ---------- App ----------
app = FastAPI(title="hornet-ARC Projektreferenzen", version="1.0.0")


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/referenzen", response_model=list[Referenz])
def list_referenzen(q: Optional[str] = Query(None, description="Volltextsuche"), einheit: Optional[Literal["PT", "EUR"]] = None):
    sql, args = "SELECT * FROM referenzen WHERE 1=1", []
    if einheit:
        sql += " AND volumenEinheit = ?"
        args.append(einheit)
    if q:
        for term in q.split():
            like = f"%{term}%"
            sql += " AND (" + " OR ".join(f"{f} LIKE ?" for f in TEXT_FIELDS) + ")"
            args += [like] * len(TEXT_FIELDS)
    sql += " ORDER BY von DESC"
    with connect() as con:
        return [row_to_dict(r) for r in con.execute(sql, args)]


@app.get("/api/referenzen/{ref_id}", response_model=Referenz)
def get_referenz(ref_id: str):
    with connect() as con:
        row = con.execute("SELECT * FROM referenzen WHERE id = ?", (ref_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Referenz nicht gefunden")
    return row_to_dict(row)


def _insert(con, data: ReferenzIn, created: Optional[str] = None) -> dict:
    ts = now()
    rec = {"id": uuid.uuid4().hex[:12], **data.model_dump(), "createdAt": created or ts, "updatedAt": ts}
    cols = ",".join(rec)
    con.execute(f"INSERT INTO referenzen ({cols}) VALUES ({','.join('?' * len(rec))})",
                [int(v) if isinstance(v, bool) else v for v in rec.values()])
    return rec


@app.post("/api/referenzen", response_model=Referenz, status_code=201)
def create_referenz(data: ReferenzIn):
    with connect() as con:
        return _insert(con, data)


@app.put("/api/referenzen/{ref_id}", response_model=Referenz)
def update_referenz(ref_id: str, data: ReferenzIn):
    with connect() as con:
        row = con.execute("SELECT createdAt FROM referenzen WHERE id = ?", (ref_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Referenz nicht gefunden")
        rec = {**data.model_dump(), "updatedAt": now()}
        sets = ",".join(f"{k} = ?" for k in rec)
        con.execute(f"UPDATE referenzen SET {sets} WHERE id = ?",
                    [int(v) if isinstance(v, bool) else v for v in rec.values()] + [ref_id])
        return {"id": ref_id, **rec, "createdAt": row["createdAt"]}


@app.delete("/api/referenzen/{ref_id}", status_code=204)
def delete_referenz(ref_id: str):
    with connect() as con:
        cur = con.execute("DELETE FROM referenzen WHERE id = ?", (ref_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Referenz nicht gefunden")
    return Response(status_code=204)


@app.post("/api/import")
def import_referenzen(items: list[dict]):
    """Importiert eine Liste von Referenzen (Format wie der JSON-Export)."""
    ok, fehler = 0, []
    with connect() as con:
        for i, raw in enumerate(items):
            try:
                _insert(con, ReferenzIn(**{k: raw.get(k) for k in ReferenzIn.model_fields if k in raw}), raw.get("createdAt"))
                ok += 1
            except Exception as e:  # noqa: BLE001
                fehler.append({"index": i, "fehler": str(e)})
    return {"importiert": ok, "fehler": fehler}


EXPORT_COLS = [("name", "Projektname"), ("kunde", "Auftraggeber"), ("von", "Von"), ("bis", "Bis"), ("laufend", "Laufend"),
               ("volumenWert", "Volumen"), ("volumenEinheit", "Einheit"), ("beschreibung", "Projektbeschreibung"),
               ("situation", "Ausgangssituation"), ("herausforderungen", "Herausforderungen"), ("loesung", "Lösung"), ("sonstiges", "Sonstiges")]


@app.get("/api/export.csv")
def export_csv():
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([c[1] for c in EXPORT_COLS])
    for r in list_referenzen(None, None):
        w.writerow([("ja" if r[k] else "nein") if k == "laufend" else str(r[k]).replace(".", ",") if k == "volumenWert" else r[k] for k, _ in EXPORT_COLS])
    name = f"projektreferenzen-{datetime.now():%Y-%m-%d}.csv"
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/export.json")
def export_json():
    data = [{k: v for k, v in r.items() if k != "id"} for r in list_referenzen(None, None)]
    name = f"projektreferenzen-{datetime.now():%Y-%m-%d}.json"
    return Response(json.dumps(data, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---------- Oberfläche ----------
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")
