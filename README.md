# hornet-ARC – Projektreferenzen

Kleiner Python-Microservice (FastAPI + SQLite) zum Erfassen, Durchsuchen, Bearbeiten und Exportieren von Projektreferenzen, mit Weboberfläche.

## Start (Windows, PowerShell)

```powershell
cd "D:\Programming Projects\hornet-ARC"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Der Browser öffnet sich automatisch. Die Adresse steht auch in der Konsole, z.B. `http://127.0.0.1:8765`.

Ist Port 8765 belegt, sucht der Dienst selbst den nächsten freien Port. Anderen Startport wählen: `python run.py --port 9000`. Browser nicht öffnen: `--no-browser`.

## Daten

Die Referenzen liegen in `data\referenzen.db` (SQLite, wird beim ersten Start angelegt). Für eine Sicherung diese Datei kopieren oder über die Oberfläche als JSON exportieren. Anderer Speicherort: Umgebungsvariable `HORNET_DB`.

## Felder

| Feld | Pflicht | Hinweis |
|---|---|---|
| name | ja | Projektname |
| kunde | ja | Auftraggeber |
| von | ja | Monat, `JJJJ-MM` |
| bis | ja, außer `laufend` | Monat, `JJJJ-MM` |
| laufend | – | `true`, wenn das Projekt noch läuft |
| volumenWert | ja | Zahl ≥ 0 |
| volumenEinheit | ja | `PT` oder `EUR` |
| beschreibung | ja | kurze Projektbeschreibung (max. 1500 Zeichen) |
| situation | – | Ausgangssituation des Kunden |
| herausforderungen | – | Herausforderungen |
| loesung | – | Lösung |
| sonstiges | – | Sonstiges |

## REST-API

Interaktive Doku: `<Adresse aus der Konsole>/docs`, z.B. http://127.0.0.1:8765/docs

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/referenzen?q=…&einheit=PT` | Liste, optional Suche/Filter |
| GET | `/api/referenzen/{id}` | eine Referenz |
| POST | `/api/referenzen` | anlegen |
| PUT | `/api/referenzen/{id}` | ändern |
| DELETE | `/api/referenzen/{id}` | löschen |
| POST | `/api/import` | Liste im JSON-Exportformat importieren |
| GET | `/api/export.csv` | alle als CSV (Excel, Semikolon) |
| GET | `/api/export.json` | alle als JSON |
| GET | `/api/health` | Statusprüfung |

## Lizenz

MIT, siehe [LICENSE](LICENSE).
