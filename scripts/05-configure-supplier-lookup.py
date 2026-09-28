"""Configure the Supplier Quick Find and Lookup views so supplier lookups search and show DUNS.

Lookup controls search the table's Quick Find view find columns (SRM-INT-002: suppliers are
identified by DUNS) and display the Lookup view columns. Idempotent; publishes mag_supplier.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from auth import get_token

TABLE = "mag_supplier"
SOLUTION = "SRMAgentDemo"
FIND_COLUMNS = ["mag_name", "mag_duns"]
QUICK_FIND_LAYOUT = [("mag_name", 300), ("mag_duns", 125), ("mag_legalname", 200), ("mag_country", 150)]
LOOKUP_LAYOUT = [("mag_name", 300), ("mag_duns", 125), ("mag_country", 150)]


URL_SAFE = "/?$=&(),'"


def web_api(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> dict | None:
    request = urllib.request.Request(
        f"{os.environ['DATAVERSE_URL'].rstrip('/')}/api/data/v9.2/{urllib.parse.quote(path, safe=URL_SAFE)}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {get_token()}",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            **(headers or {}),
        },
    )
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read()
            return json.loads(payload) if payload else None
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"{method} {path} failed with {error.code}: {error.read().decode()[:800]}") from error
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 5:
                raise
            time.sleep(attempt * 10)
    return None


def attributes(columns: list[str]) -> str:
    return "".join(f'<attribute name="{name}" />' for name in ["mag_supplierid", *columns])


def layout(existing: str, cells: list[tuple[str, int]]) -> str:
    """Replace the cells of an existing layout, keeping its grid/row attributes (e.g. 'object')."""
    body = "".join(f'<cell name="{name}" width="{width}" />' for name, width in cells)
    start = existing.index(">", existing.index("<row ")) + 1
    end = existing.index("</row>")
    return existing[:start] + body + existing[end:]


def view(querytype: int) -> dict:
    rows = web_api(
        "GET",
        f"savedqueries?$select=savedqueryid,name,fetchxml,layoutxml"
        f"&$filter=returnedtypecode eq '{TABLE}' and querytype eq {querytype} and isdefault eq true",
    )["value"]
    if len(rows) != 1:
        raise RuntimeError(f"Expected one default view of type {querytype} on {TABLE}, found {len(rows)}")
    return rows[0]


def ensure_searchable(columns: set[str]) -> None:
    """Quick Find and view columns must be searchable (IsValidForAdvancedFind)."""
    for name in sorted(columns):
        path = f"EntityDefinitions(LogicalName='{TABLE}')/Attributes(LogicalName='{name}')"
        definition = web_api("GET", path)
        if definition["IsValidForAdvancedFind"]["Value"]:
            continue
        definition["IsValidForAdvancedFind"]["Value"] = True
        for attempt in range(1, 7):
            try:
                web_api("PUT", path, definition, {
                    "MSCRM.MergeLabels": "true",
                    "MSCRM.SolutionUniqueName": SOLUTION,
                })
                break
            except RuntimeError as error:
                if "still being processed" not in str(error) or attempt == 6:
                    raise
                time.sleep(attempt * 10)
        print(f"Made {TABLE}.{name} searchable.")


def main() -> None:
    ensure_searchable({name for name, _ in QUICK_FIND_LAYOUT + LOOKUP_LAYOUT} | set(FIND_COLUMNS))
    quick_find = view(4)
    missing = [name for name in FIND_COLUMNS
               if f'<condition attribute="{name}" operator="like"' not in quick_find["fetchxml"]]
    if not missing:
        print(f"'{quick_find['name']}' already searches {', '.join(FIND_COLUMNS)}.")
    else:
        # DemoPRE rejects Web API fetchxml updates on Quick Find views (0x80040216, even unchanged
        # fetch). The supported fallback is a solution import; see docs/03-model-driven-app.md.
        raise RuntimeError(
            f"Quick Find view is missing find columns {missing}. Edit the unpacked view XML and "
            "import the solution (Web API updates to Quick Find fetchxml are rejected)."
        )
    lookup = view(64)
    lookup_fetch = (
        f'<fetch version="1.0" mapping="logical"><entity name="{TABLE}">'
        f'{attributes([name for name, _ in LOOKUP_LAYOUT])}'
        '<order attribute="mag_name" descending="false" />'
        '<filter type="and"><condition attribute="statecode" operator="eq" value="0" /></filter>'
        '</entity></fetch>'
    )
    web_api("PATCH", f"savedqueries({lookup['savedqueryid']})", {
        "fetchxml": lookup_fetch,
        "layoutxml": layout(lookup["layoutxml"], LOOKUP_LAYOUT),
    })
    print(f"Updated '{lookup['name']}': columns {', '.join(name for name, _ in LOOKUP_LAYOUT)}.")

    web_api("POST", "PublishXml", {
        "ParameterXml": f"<importexportxml><entities><entity>{TABLE}</entity></entities></importexportxml>"
    })
    print(f"Published {TABLE}.")


if __name__ == "__main__":
    main()
