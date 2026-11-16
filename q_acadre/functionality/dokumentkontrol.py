from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import Page


logger = logging.getLogger(__name__)


ACADRE_BASE_URL = (
    "https://udcdokwebfront.intern.udcit.dk"
)

ACADRE_MAIN_DOCUMENT_GRID_URL = (
    f"{ACADRE_BASE_URL}"
    "/Frontend/CM/MainDocument/GetGridContextData"
)

ACADRE_CASE_DETAILS_URL = (
    f"{ACADRE_BASE_URL}"
    "/Frontend/CM/Case/Details"
)

STANDARD_DATE_FIELD = (
    "main-document-journalization-date"
)

TILLADTE_DATE_FIELDS = {
    "main-document-modification-date",
    "main-document-document-date",
    "main-document-created-date",
    "main-document-journalization-date",
}


async def find_case_documents_by_title_and_date(
    page: Page,
    *,
    case_id: str | int,
    title: str,
    document_date: date | datetime | str,
    date_field: str = STANDARD_DATE_FIELD,
    page_size: int = 50,
    folder_id: str | int = "0",
    timeout_ms: int = 120_000,
) -> dict[str, Any]:
    """
    Finder eksisterende dokumenter på en Acadre-sag ud fra titel og dato.

    Funktionen kalder:

        POST /Frontend/CM/MainDocument/GetGridContextData

    Der matches på:

    1. Dokumentets titel:
       "main-document-title-link"

    2. Den valgte datokolonne, som som standard er:
       "main-document-journalization-date"

    Titel sammenlignes uden forskel på store og små bogstaver.
    Mellemrum før og efter titlen ignoreres.

    Dato kan gives som:

        date(2026, 11, 16)
        datetime(2026, 11, 16, 10, 30)
        "16-11-2026"

    Alle resultatsider hentes automatisk. Funktionen kontrollerer derfor
    også sager med flere dokumenter end page_size.

    Args:
        page:
            En autentificeret Playwright-side fra den eksisterende
            Acadre BrowserSession.

        case_id:
            Acadres tekniske caseId, eksempelvis 763145.

        title:
            Den præcise dokumenttitel, eksempelvis "Konfliktrapport".

        document_date:
            Den dato, dokumentet skal have.

        date_field:
            Acadre-feltet, datoen skal sammenlignes med.

            Standard:
                main-document-journalization-date

            Tilladte værdier:
                main-document-modification-date
                main-document-document-date
                main-document-created-date
                main-document-journalization-date

        page_size:
            Antal dokumenter pr. Acadre-request.

        folder_id:
            Acadres mappe-id. Rodmappen er normalt "0".

        timeout_ms:
            Maksimal ventetid for hvert Acadre-request.

    Returns:
        En dictionary i denne form:

        {
            "found": True,
            "match_count": 3,
            "matches": [
                {
                    "document_id": "7002051",
                    "title": "Konfliktrapport",
                    "matched_date": "16-11-2026",
                    "date_field": (
                        "main-document-journalization-date"
                    ),
                    "document_url": (
                        "https://..."
                        "/Frontend/CM/MainDocument/Details"
                        "?documentId=7002051"
                    ),
                    "type": "DocumentPDF",
                    "values": {...},
                    "raw_item": {...},
                }
            ],
            "case_id": "763145",
            "expected_title": "Konfliktrapport",
            "expected_date": "16-11-2026",
            "date_field": (
                "main-document-journalization-date"
            ),
            "documents_checked": 7,
            "total_count": 7,
            "pages_fetched": 1,
        }

    Raises:
        TypeError:
            Hvis parametrenes datatyper er ugyldige.

        ValueError:
            Hvis en påkrævet værdi er tom eller ugyldig.

        RuntimeError:
            Hvis Acadre-requestet fejler eller svaret har en uventet
            struktur.
    """
    _validate_page(page)

    normalized_case_id = _normalize_positive_integer(
        case_id,
        field_name="case_id",
    )

    normalized_title = _normalize_required_text(
        title,
        field_name="title",
    )

    normalized_document_date = _normalize_document_date(
        document_date
    )

    normalized_date_field = _normalize_required_text(
        date_field,
        field_name="date_field",
    )

    if normalized_date_field not in TILLADTE_DATE_FIELDS:
        accepted_fields = ", ".join(
            sorted(TILLADTE_DATE_FIELDS)
        )

        raise ValueError(
            "date_field skal være en af følgende værdier: "
            f"{accepted_fields}."
        )

    normalized_folder_id = _normalize_non_negative_integer(
        folder_id,
        field_name="folder_id",
    )

    if (
        isinstance(page_size, bool)
        or not isinstance(page_size, int)
    ):
        raise TypeError(
            "page_size skal være et helt tal."
        )

    if page_size < 1:
        raise ValueError(
            "page_size skal være mindst 1."
        )

    if page_size > 500:
        raise ValueError(
            "page_size må højst være 500."
        )

    if (
        isinstance(timeout_ms, bool)
        or not isinstance(timeout_ms, int)
    ):
        raise TypeError(
            "timeout_ms skal være et helt tal."
        )

    if timeout_ms < 1:
        raise ValueError(
            "timeout_ms skal være mindst 1."
        )

    logger.info(
        "Søger efter eksisterende Acadre-dokument. "
        "caseId=%s, titel=%r, dato=%s, datofelt=%s.",
        normalized_case_id,
        normalized_title,
        normalized_document_date,
        normalized_date_field,
    )

    all_documents: list[dict[str, Any]] = []
    page_index = 0
    pages_fetched = 0
    total_count: int | None = None

    while True:
        payload = {
            "Identifier": "CaseMainDocuments",
            "PageSize": page_size,
            "PageIndex": page_index,
            "FilterKey": "",
            "SortingColumns": [
                {
                    "ColumnKey": (
                        "main-document-journalization-date"
                    ),
                    "Direction": "desc",
                }
            ],
            "CaseId": normalized_case_id,
            "FolderId": normalized_folder_id,
        }

        referer = (
            f"{ACADRE_CASE_DETAILS_URL}"
            f"?caseId={normalized_case_id}"
        )

        logger.info(
            "Henter Acadre-dokumenter. "
            "caseId=%s, PageIndex=%s, PageSize=%s.",
            normalized_case_id,
            page_index,
            page_size,
        )

        response = await page.context.request.post(
            ACADRE_MAIN_DOCUMENT_GRID_URL,
            headers={
                "Accept": (
                    "application/json, text/javascript, "
                    "*/*; q=0.01"
                ),
                "Content-Type": (
                    "application/json; charset=UTF-8"
                ),
                "Origin": ACADRE_BASE_URL,
                "Referer": referer,
                "X-Requested-With": "XMLHttpRequest",
            },
            data=payload,
            timeout=timeout_ms,
        )

        response_text = await response.text()

        if not response.ok:
            raise RuntimeError(
                "Acadre kunne ikke hente sagens dokumenter.\n"
                f"CaseId: {normalized_case_id}\n"
                f"PageIndex: {page_index}\n"
                f"HTTP-status: {response.status}\n"
                f"Svar fra Acadre:\n"
                f"{response_text[:2_000]}"
            )

        try:
            response_data = await response.json()

        except Exception as error:
            raise RuntimeError(
                "Acadre returnerede ikke gyldigt JSON ved "
                "hentning af sagens dokumenter.\n"
                f"CaseId: {normalized_case_id}\n"
                f"PageIndex: {page_index}\n"
                f"HTTP-status: {response.status}\n"
                f"Svar fra Acadre:\n"
                f"{response_text[:2_000]}"
            ) from error

        if not isinstance(response_data, dict):
            raise RuntimeError(
                "Acadre returnerede en uventet datatype ved "
                "hentning af sagens dokumenter. "
                f"Modtaget datatype: "
                f"{type(response_data).__name__}."
            )

        raw_items = response_data.get("Items")

        if raw_items is None:
            raw_items = []

        if not isinstance(raw_items, list):
            raise RuntimeError(
                "Acadre-svaret indeholder ikke en gyldig "
                "Items-liste."
            )

        raw_total_count = response_data.get(
            "TotalCount"
        )

        if (
            isinstance(raw_total_count, int)
            and not isinstance(raw_total_count, bool)
            and raw_total_count >= 0
        ):
            total_count = raw_total_count

        elif (
            isinstance(raw_total_count, str)
            and raw_total_count.strip().isdigit()
        ):
            total_count = int(
                raw_total_count.strip()
            )

        pages_fetched += 1

        parsed_page_documents = [
            _parse_main_document_item(item)
            for item in raw_items
            if isinstance(item, dict)
        ]

        all_documents.extend(
            parsed_page_documents
        )

        logger.info(
            "Acadre returnerede %s dokumenter på side %s. "
            "Samlet hentet=%s, TotalCount=%s.",
            len(parsed_page_documents),
            page_index,
            len(all_documents),
            total_count,
        )

        if not raw_items:
            break

        if (
            total_count is not None
            and len(all_documents) >= total_count
        ):
            break

        if len(raw_items) < page_size:
            break

        page_index += 1

    expected_title_casefold = (
        normalized_title.casefold()
    )

    matches: list[dict[str, Any]] = []

    for document in all_documents:
        document_title = str(
            document.get("title") or ""
        ).strip()

        document_date_value = str(
            document["values"].get(
                normalized_date_field
            )
            or ""
        ).strip()

        title_matches = (
            document_title.casefold()
            == expected_title_casefold
        )

        date_matches = (
            document_date_value
            == normalized_document_date
        )

        if not title_matches or not date_matches:
            continue

        matches.append(
            {
                **document,
                "matched_date": (
                    document_date_value
                ),
                "date_field": (
                    normalized_date_field
                ),
            }
        )

    result = {
        "found": bool(matches),
        "match_count": len(matches),
        "matches": matches,
        "case_id": normalized_case_id,
        "expected_title": normalized_title,
        "expected_date": (
            normalized_document_date
        ),
        "date_field": normalized_date_field,
        "documents_checked": len(
            all_documents
        ),
        "total_count": (
            total_count
            if total_count is not None
            else len(all_documents)
        ),
        "pages_fetched": pages_fetched,
    }

    if matches:
        logger.info(
            "Fandt %s eksisterende Acadre-dokumenter. "
            "caseId=%s, titel=%r, dato=%s, "
            "documentIds=%s.",
            len(matches),
            normalized_case_id,
            normalized_title,
            normalized_document_date,
            [
                match.get("document_id")
                for match in matches
            ],
        )

    else:
        logger.info(
            "Fandt ingen eksisterende Acadre-dokumenter. "
            "caseId=%s, titel=%r, dato=%s. "
            "Antal kontrollerede dokumenter=%s.",
            normalized_case_id,
            normalized_title,
            normalized_document_date,
            len(all_documents),
        )

    return result


def _parse_main_document_item(
    item: dict[str, Any],
) -> dict[str, Any]:
    """
    Omdanner ét råt Acadre-dokument til en enklere dictionary.

    Values-listen omdannes til:

        {
            "main-document-title-link": "...",
            "main-document-created-date": "...",
        }

    Links gemmes separat.
    """
    raw_values = item.get("Values")

    if raw_values is None:
        raw_values = []

    if not isinstance(raw_values, list):
        raise RuntimeError(
            "Et Acadre-dokument indeholder ikke en "
            "gyldig Values-liste."
        )

    values: dict[str, Any] = {}
    links: dict[str, str] = {}

    for value_item in raw_values:
        if not isinstance(value_item, dict):
            continue

        raw_key = value_item.get("Key")

        if not isinstance(raw_key, str):
            continue

        key = raw_key.strip()

        if not key:
            continue

        values[key] = value_item.get("Value")

        raw_link = value_item.get("Link")

        if (
            isinstance(raw_link, str)
            and raw_link.strip()
        ):
            links[key] = raw_link.strip()

    raw_document_id = (
        values.get("main-document-document-id")
        or item.get("Id")
    )

    document_id = (
        str(raw_document_id).strip()
        if raw_document_id is not None
        else None
    )

    title = str(
        values.get("main-document-title-link")
        or ""
    ).strip()

    relative_document_url = links.get(
        "main-document-title-link"
    )

    document_url = None

    if relative_document_url:
        document_url = urljoin(
            f"{ACADRE_BASE_URL}/",
            relative_document_url,
        )

    elif document_id:
        document_url = (
            f"{ACADRE_BASE_URL}"
            "/Frontend/CM/MainDocument/Details"
            f"?documentId={document_id}"
        )

    return {
        "document_id": document_id,
        "title": title,
        "document_url": document_url,
        "type": item.get("Type"),
        "file_type": values.get(
            "main-document-file-type-text"
        ),
        "document_date": values.get(
            "main-document-document-date"
        ),
        "created_date": values.get(
            "main-document-created-date"
        ),
        "modification_date": values.get(
            "main-document-modification-date"
        ),
        "journalization_date": values.get(
            "main-document-journalization-date"
        ),
        "sequence_number": values.get(
            "main-document-sequence-number"
        ),
        "status": values.get(
            "main-document-status"
        ),
        "values": values,
        "links": links,
        "raw_item": item,
    }


def _normalize_document_date(
    value: date | datetime | str,
) -> str:
    """
    Normaliserer dato til Acadres format dd-mm-åååå.
    """
    if isinstance(value, datetime):
        return value.strftime("%d-%m-%Y")

    if isinstance(value, date):
        return value.strftime("%d-%m-%Y")

    if not isinstance(value, str):
        raise TypeError(
            "document_date skal være date, datetime "
            "eller en tekst i formatet dd-mm-åååå."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            "document_date må ikke være tom."
        )

    try:
        parsed_date = datetime.strptime(
            normalized_value,
            "%d-%m-%Y",
        ).date()

    except ValueError as error:
        raise ValueError(
            "document_date skal have formatet "
            "dd-mm-åååå, eksempelvis 16-11-2026."
        ) from error

    return parsed_date.strftime("%d-%m-%Y")


def _normalize_required_text(
    value: Any,
    *,
    field_name: str,
) -> str:
    """
    Validerer og normaliserer en obligatorisk tekst.
    """
    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} skal være en tekststreng."
        )

    normalized_value = " ".join(
        value.split()
    )

    if not normalized_value:
        raise ValueError(
            f"{field_name} må ikke være tom."
        )

    return normalized_value


def _normalize_positive_integer(
    value: str | int,
    *,
    field_name: str,
) -> str:
    """
    Validerer et positivt heltal og returnerer det som tekst.
    """
    if isinstance(value, bool):
        raise TypeError(
            f"{field_name} må ikke være en bool-værdi."
        )

    normalized_value = str(value).strip()

    if (
        not normalized_value.isdigit()
        or int(normalized_value) < 1
    ):
        raise ValueError(
            f"{field_name} skal være et positivt heltal."
        )

    return normalized_value


def _normalize_non_negative_integer(
    value: str | int,
    *,
    field_name: str,
) -> str:
    """
    Validerer et heltal på mindst nul og returnerer det som tekst.
    """
    if isinstance(value, bool):
        raise TypeError(
            f"{field_name} må ikke være en bool-værdi."
        )

    normalized_value = str(value).strip()

    if (
        not normalized_value.isdigit()
        or int(normalized_value) < 0
    ):
        raise ValueError(
            f"{field_name} skal være et heltal på mindst 0."
        )

    return normalized_value


def _validate_page(
    page: Page,
) -> None:
    """
    Validerer den Playwright-side, Acadre-requestet skal bruge.
    """
    if not isinstance(page, Page):
        raise TypeError(
            "page skal være en Playwright Page."
        )

    if page.is_closed():
        raise RuntimeError(
            "Acadre-siden er lukket."
        )