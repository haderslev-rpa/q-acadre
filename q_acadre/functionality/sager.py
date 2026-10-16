import asyncio
import math
from typing import Any
from urllib.parse import quote

from playwright.async_api import APIResponse, Page


ACADRE_BASE_URL = "https://udcdokwebfront.intern.udcit.dk"

ACADRE_CASE_URL = (
    f"{ACADRE_BASE_URL}/Frontend/CM/Case"
)

ACADRE_GRID_API_URL = (
    f"{ACADRE_BASE_URL}/Frontend/CM/Case/GetGridContextData"
)

ACADRE_CASE_DETAILS_URL = (
    f"{ACADRE_BASE_URL}/Frontend/CM/Case/Details"
)


def _default_sorting_columns() -> list[dict[str, str]]:
    """
    Returnerer Acadres standardsortering.

    Returns:
        Liste med sortering efter seneste ændringsdato.
    """
    return [
        {
            "ColumnKey": "case-last-modification-date",
            "Direction": "desc",
        }
    ]


def _default_custom_fields() -> list[dict[str, Any]]:
    """
    Returnerer Acadres standarddefinitioner for df14 til df18.

    Returns:
        Liste med custom-field-definitioner.
    """
    custom_fields = []

    for index, db_name in enumerate(
        ["df14", "df15", "df16", "df17", "df18"]
    ):
        custom_fields.append(
            {
                "ControlId": (
                    f"custom-field-no-group-{db_name}"
                ),
                "ControlSelector": (
                    "html>body>section:eq(0)>div"
                    ">div:eq(2)>div:eq(1)>div:eq(1)"
                    ">form>div:eq(2)>div:eq(0)"
                    ">div:eq(1)>div:eq(1)>div"
                    f">div:eq(2)>div:eq({index})>div>div"
                ),
                "DbName": db_name,
                "DataType": "DateTime",
                "IsListType": False,
            }
        )

    return custom_fields


async def case_search(
    page: Page,
    filter_key: str,
    page_size: int = 50,
    sorting_columns: list[dict[str, Any]] | None = None,
    case_type: str = "",
    responsible_unit: str = "",
    identifier: str = "SearchCases",
    start_page_index: int = 0,
    request_delay_seconds: float = 0,
) -> dict[str, Any]:
    """
    Udfører almindelig sagsøgning og henter automatisk alle sider.

    Args:
        page:
            Acadre-siden fra launch_acadre().

        filter_key:
            Søgeteksten, eksempelvis "aktindsigt".

        page_size:
            Antal resultater pr. API-kald.

        sorting_columns:
            Valgfri Acadre-sortering.

        case_type:
            Valgfri sagstype.

        responsible_unit:
            Valgfri ansvarlig enhed.

        identifier:
            Acadres identifier. Normalt "SearchCases".

        start_page_index:
            Første side, der skal hentes. Normalt 0.

        request_delay_seconds:
            Valgfri pause mellem API-kaldene.

    Returns:
        Dictionary med:

        {
            "items": alle resultater,
            "total_count": samlet antal,
            "pages_fetched": antal hentede sider,
            "page_size": anvendt sidestørrelse,
            "raw_first_response": første rå Acadre-svar
        }
    """
    if not isinstance(filter_key, str):
        raise ValueError(
            "filter_key skal være en tekststreng."
        )

    base_payload = {
        "Identifier": identifier,
        "PageSize": page_size,
        "PageIndex": start_page_index,
        "SortingColumns": (
            sorting_columns
            if sorting_columns is not None
            else _default_sorting_columns()
        ),
        "IsFullSearch": False,
        "CaseType": case_type,
        "FilterKey": filter_key,
        "ResponsibleUnit": responsible_unit,
    }

    referer = (
        f"{ACADRE_CASE_URL}"
        f"?IsFullSearch=False"
        f"&SearchKey={quote(filter_key)}"
    )

    return await _fetch_all_pages(
        page=page,
        base_payload=base_payload,
        referer=referer,
        start_page_index=start_page_index,
        request_delay_seconds=request_delay_seconds,
        operation_name="Acadre case_search",
    )

# ============================================================
# START: search_case_by_number
# ============================================================

async def search_case_by_number(
    page: Page,
    case_number: str,
    page_size: int = 20,
    page_index: int = 0,
    timeout_ms: int = 120_000,
) -> dict[str, Any]:
    """
    Søger efter et konkret sagsnummer via Acadres API.

    API-kald:
        POST /Frontend/CM/Case/GetGridContextData

    Browserfanen navigeres ikke. Kaldet foretages gennem den
    eksisterende Playwright BrowserContext, så Acadre-cookies
    genbruges automatisk.

    Args:
        page:
            Den aktive Acadre-side fra launch_acadre().
        case_number:
            Sagsnummeret, eksempelvis "26/20909".
        page_size:
            Antal søgeresultater, Acadre må returnere.
        page_index:
            Indeks på resultatsiden. Første side er 0.
        timeout_ms:
            Maksimal ventetid på API-kaldet.

    Returns:
        Dictionary med:

        {
            "case_number": "26/20909",
            "items": [
                {
                    "case_id": "761237",
                    "type": "Case",
                    "case_url": "...",
                    "case_number": "26/20909",
                    "case_type": "EJSAG",
                    "description": "...",
                    "status": "B - Under behandling",
                    "title": "...",
                    "values": {...},
                    "raw_item": {...},
                    "is_exact_match": True,
                }
            ],
            "exact_matches": [...],
            "result_count": 1,
            "exact_match_count": 1,
            "page_size": 20,
            "page_index": 0,
            "raw_response": {...},
        }
    """
    if not isinstance(case_number, str):
        raise TypeError(
            "case_number skal være en tekststreng."
        )

    normalized_case_number = case_number.strip()

    if not normalized_case_number:
        raise ValueError(
            "case_number må ikke være tom."
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

    if (
        isinstance(page_index, bool)
        or not isinstance(page_index, int)
    ):
        raise TypeError(
            "page_index skal være et helt tal."
        )

    if page_index < 0:
        raise ValueError(
            "page_index må ikke være negativ."
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

    request_payload = {
        "Identifier": "SearchCases",
        "PageSize": page_size,
        "PageIndex": page_index,
        "SortingColumns": [
            {
                "ColumnKey": (
                    "case-last-modification-date"
                ),
                "Direction": "desc",
            }
        ],
        "IsFullSearch": False,
        "CaseType": "",
        "FilterKey": normalized_case_number,
        "ResponsibleUnit": "",
    }

    referer = (
        f"{ACADRE_CASE_URL}"
        f"?IsFullSearch=False"
        f"&SearchKey={quote(normalized_case_number)}"
    )

    print()
    print(
        "Søger efter Acadre-sag via API: "
        f"{normalized_case_number}"
    )

    response = await page.context.request.post(
        ACADRE_GRID_API_URL,
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
        data=request_payload,
        timeout=timeout_ms,
    )

    response_data = await _read_json_response(
        response=response,
        operation_name=(
            "Acadre-søgning efter sagsnummer "
            f"'{normalized_case_number}'"
        ),
    )

    raw_items = _extract_items(
        response_data
    )

    normalized_items: list[dict[str, Any]] = []

    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue

        values_by_key: dict[str, Any] = {}
        links_by_key: dict[str, str] = {}

        raw_values = raw_item.get(
            "Values",
            [],
        )

        if isinstance(raw_values, list):
            for value_item in raw_values:
                if not isinstance(value_item, dict):
                    continue

                key = value_item.get("Key")

                if not isinstance(key, str):
                    continue

                normalized_key = key.strip()

                if not normalized_key:
                    continue

                values_by_key[normalized_key] = (
                    value_item.get("Value")
                )

                link = value_item.get("Link")

                if (
                    isinstance(link, str)
                    and link.strip()
                ):
                    links_by_key[normalized_key] = (
                        link.strip()
                    )

        returned_case_number = values_by_key.get(
            "case-sequence-number"
        )

        relative_case_url = links_by_key.get(
            "case-sequence-number"
        )

        if not relative_case_url:
            relative_case_url = links_by_key.get(
                "case-icon"
            )

        case_url = None

        if relative_case_url:
            if relative_case_url.startswith(
                ("http://", "https://")
            ):
                case_url = relative_case_url
            else:
                case_url = (
                    f"{ACADRE_BASE_URL}"
                    f"{relative_case_url}"
                )

        raw_case_id = raw_item.get("Id")

        case_id = (
            str(raw_case_id).strip()
            if raw_case_id is not None
            else None
        )

        is_exact_match = (
            isinstance(returned_case_number, str)
            and returned_case_number.strip().casefold()
            == normalized_case_number.casefold()
        )

        normalized_item = {
            "case_id": case_id,
            "type": raw_item.get("Type"),
            "case_url": case_url,
            "case_number": returned_case_number,
            "case_type": values_by_key.get(
                "case-type"
            ),
            "description": values_by_key.get(
                "case-description"
            ),
            "status": values_by_key.get(
                "case-status"
            ),
            "title": values_by_key.get(
                "case-title-text"
            ),
            "values": values_by_key,
            "links": links_by_key,
            "is_exact_match": is_exact_match,
            "raw_item": raw_item,
        }

        normalized_items.append(
            normalized_item
        )

    exact_matches = [
        item
        for item in normalized_items
        if item["is_exact_match"]
    ]

    print(
        f"HTTP-status fra Acadre: {response.status}"
    )
    print(
        f"Antal søgeresultater: "
        f"{len(normalized_items)}"
    )
    print(
        f"Antal præcise matches: "
        f"{len(exact_matches)}"
    )

    return {
        "case_number": normalized_case_number,
        "items": normalized_items,
        "exact_matches": exact_matches,
        "result_count": len(normalized_items),
        "exact_match_count": len(exact_matches),
        "page_size": page_size,
        "page_index": page_index,
        "raw_response": response_data,
    }


# ============================================================
# SLUT: search_case_by_number
# ============================================================

async def case_search_full(
    page: Page,
    page_size: int = 50,
    sorting_columns: list[dict[str, Any]] | None = None,
    identifier: str = "SearchCases",
    start_page_index: int = 0,
    request_delay_seconds: float = 0,
    title: str = "",
    status: str = "",
    year: str = "",
    sequence: str = "",
    comment: str = "",
    content: str = "",
    case_type: str = "",
    responsible_user: str = "",
    responsible_unit: str = "",
    created_date_from: str = "",
    created_date_to: str = "",
    modified_date_from: str = "",
    modified_date_to: str = "",
    closed_date_from: str = "",
    closed_date_to: str = "",
    deadline_date_from: str = "",
    deadline_date_to: str = "",
    case_created_date_from: str = "",
    case_created_date_to: str = "",
    obs_date_from: str = "",
    obs_date_to: str = "",
    discard_date_from: str = "",
    discard_date_to: str = "",
    deletion_date_from: str = "",
    deletion_date_to: str = "",
    public_access_level: str = "",
    access_code: str = "",
    access_group: str = "",
    facets: str = "[]",
    discard_code: str = "",
    deletion_code: str = "",
    archive_part: str = "",
    is_principle: str = "",
    multi_case_title: str = "",
    multi_case_year: str = "",
    multi_case_sequence: str = "",
    multi_case_type: str = "",
    multi_case_responsible_user: str = "",
    multi_case_modified_date_from: str = "",
    multi_case_modified_date_to: str = "",
    multi_case_creation_date_from: str = "",
    multi_case_creation_date_to: str = "",
    external_number: str = "",
    active_case: str = "true",
    favorite_case: str = "false",
    own_case: str = "false",
    is_insight: str = "false",
    priority: str = "",
    phase_name: str = "",
    group_name: str = "",
    decision_name: str = "",
    awaiting_name: str = "",
    custom_field_search_values: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Udfører full search og henter automatisk alle resultatsider.

    Alle felter fra det observerede Acadre-request kan gives som input.

    OBS: VIRKER IKKE AT SØGE PÅ TILE!!

    Returns:
        Dictionary med alle samlede resultater:

        {
            "items": alle resultater,
            "total_count": samlet antal,
            "pages_fetched": antal hentede sider,
            "page_size": anvendt sidestørrelse,
            "raw_first_response": første rå Acadre-svar
        }
    """
    base_payload = {
        "Identifier": identifier,
        "PageSize": page_size,
        "PageIndex": start_page_index,
        "SortingColumns": (
            sorting_columns
            if sorting_columns is not None
            else _default_sorting_columns()
        ),
        "IsFullSearch": True,
        "Title": title,
        "Status": status,
        "Year": year,
        "Sequence": sequence,
        "Comment": comment,
        "Content": content,
        "CaseType": case_type,
        "ResponsibleUser": responsible_user,
        "ResponsibleUnit": responsible_unit,
        "CreatedDateFrom": created_date_from,
        "CreatedDateTo": created_date_to,
        "ModifiedDateFrom": modified_date_from,
        "ModifiedDateTo": modified_date_to,
        "ClosedDateFrom": closed_date_from,
        "ClosedDateTo": closed_date_to,
        "DeadlineDateFrom": deadline_date_from,
        "DeadlineDateTo": deadline_date_to,
        "CaseCreatedDateFrom": case_created_date_from,
        "CaseCreatedDateTo": case_created_date_to,
        "OBSDateFrom": obs_date_from,
        "OBSDateTo": obs_date_to,
        "DiscardDateFrom": discard_date_from,
        "DiscardDateTo": discard_date_to,
        "DeletionDateFrom": deletion_date_from,
        "DeletionDateTo": deletion_date_to,
        "PublicAccessLevel": public_access_level,
        "AccessCode": access_code,
        "AccessGroup": access_group,
        "Facets": facets,
        "DiscardCode": discard_code,
        "DeletionCode": deletion_code,
        "ArchivePart": archive_part,
        "IsPrinciple": is_principle,
        "MultiCaseTitle": multi_case_title,
        "MultiCaseYear": multi_case_year,
        "MultiCaseSequence": multi_case_sequence,
        "MultiCaseType": multi_case_type,
        "MultiCaseResponsibleUser": multi_case_responsible_user,
        "MultiCaseModifiedDateFrom": multi_case_modified_date_from,
        "MultiCaseModifiedDateTo": multi_case_modified_date_to,
        "MultiCaseCreationDateFrom": multi_case_creation_date_from,
        "MultiCaseCreationDateTo": multi_case_creation_date_to,
        "ExternalNumber": external_number,
        "ActiveCase": active_case,
        "FavoriteCase": favorite_case,
        "OwnCase": own_case,
        "IsInsight": is_insight,
        "Priority": priority,
        "PhaseName": phase_name,
        "GroupName": group_name,
        "DecisionName": decision_name,
        "AwaitingName": awaiting_name,
        "CustomFieldSearchValues": (
            custom_field_search_values
            if custom_field_search_values is not None
            else _default_custom_fields()
        ),
    }

    return await _fetch_all_pages(
        page=page,
        base_payload=base_payload,
        referer=f"{ACADRE_CASE_URL}?IsFullSearch=True",
        start_page_index=start_page_index,
        request_delay_seconds=request_delay_seconds,
        operation_name="Acadre case_search_full",
    )


async def _fetch_all_pages(
    page: Page,
    base_payload: dict[str, Any],
    referer: str,
    start_page_index: int,
    request_delay_seconds: float,
    operation_name: str,
) -> dict[str, Any]:
    """
    Henter automatisk alle sider fra Acadre.

    Første svar bruges til at finde:

    - Den samlede mængde resultater
    - Listen med resultater
    - Antal nødvendige sider

    Returns:
        Et samlet resultat med alle items.
    """
    page_size = base_payload["PageSize"]

    if page_size < 1:
        raise ValueError(
            "page_size skal være mindst 1."
        )

    if start_page_index < 0:
        raise ValueError(
            "start_page_index må ikke være negativ."
        )

    if request_delay_seconds < 0:
        raise ValueError(
            "request_delay_seconds må ikke være negativ."
        )

    first_response = await _fetch_page(
        page=page,
        payload={
            **base_payload,
            "PageIndex": start_page_index,
        },
        referer=referer,
        operation_name=operation_name,
    )

    first_items = _extract_items(first_response)
    total_count = _extract_total_count(first_response)

    all_items = list(first_items)
    pages_fetched = 1

    if total_count is None:
        print(
            "Acadre-svaret indeholder ikke et genkendeligt "
            "totalfelt."
        )
        print(
            "Fortsætter derfor side for side, indtil Acadre "
            "returnerer færre resultater end PageSize."
        )

        next_page_index = start_page_index + 1

        while len(first_items) == page_size:
            if request_delay_seconds > 0:
                await asyncio.sleep(
                    request_delay_seconds
                )

            response_data = await _fetch_page(
                page=page,
                payload={
                    **base_payload,
                    "PageIndex": next_page_index,
                },
                referer=referer,
                operation_name=operation_name,
            )

            page_items = _extract_items(response_data)

            if not page_items:
                break

            all_items.extend(page_items)
            pages_fetched += 1

            if len(page_items) < page_size:
                break

            first_items = page_items
            next_page_index += 1

        total_count = len(all_items)

    else:
        remaining_count = max(
            total_count - len(first_items),
            0,
        )

        remaining_pages = math.ceil(
            remaining_count / page_size
        )

        print(
            f"Samlet antal resultater: {total_count}"
        )
        print(
            f"Resultater på første side: {len(first_items)}"
        )
        print(
            f"Resterende resultater: {remaining_count}"
        )
        print(
            f"Resterende API-kald: {remaining_pages}"
        )

        for offset in range(1, remaining_pages + 1):
            page_index = start_page_index + offset

            if request_delay_seconds > 0:
                await asyncio.sleep(
                    request_delay_seconds
                )

            response_data = await _fetch_page(
                page=page,
                payload={
                    **base_payload,
                    "PageIndex": page_index,
                },
                referer=referer,
                operation_name=operation_name,
            )

            page_items = _extract_items(response_data)

            if not page_items:
                print(
                    f"PageIndex {page_index} returnerede "
                    "ingen resultater. Pagination stoppes."
                )
                break

            all_items.extend(page_items)
            pages_fetched += 1

            print(
                f"Hentet PageIndex {page_index}: "
                f"{len(page_items)} resultater. "
                f"Samlet hentet: {len(all_items)} af "
                f"{total_count}."
            )

    if (
        total_count is not None
        and len(all_items) > total_count
    ):
        all_items = all_items[:total_count]

    return {
        "items": all_items,
        "total_count": total_count,
        "pages_fetched": pages_fetched,
        "page_size": page_size,
        "raw_first_response": first_response,
    }


async def _fetch_page(
    page: Page,
    payload: dict[str, Any],
    referer: str,
    operation_name: str,
) -> dict[str, Any] | list:
    """
    Henter ét PageIndex fra Acadre.

    Returns:
        Acadres JSON-svar for den pågældende side.
    """
    page_index = payload["PageIndex"]

    print(
        f"Sender {operation_name}, "
        f"PageIndex={page_index}..."
    )

    response = await page.context.request.post(
        ACADRE_GRID_API_URL,
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
        timeout=120_000,
    )

    return await _read_json_response(
        response=response,
        operation_name=(
            f"{operation_name}, "
            f"PageIndex={page_index}"
        ),
    )


async def _read_json_response(
    response: APIResponse,
    operation_name: str,
) -> dict[str, Any] | list:
    """
    Validerer HTTP-svaret og returnerer JSON.

    Returns:
        Dictionary eller liste fra Acadre.
    """
    if not response.ok:
        response_text = await response.text()

        raise RuntimeError(
            f"{operation_name} fejlede.\n"
            f"HTTP-status: {response.status}\n"
            f"Svar fra Acadre:\n"
            f"{response_text}"
        )

    try:
        return await response.json()

    except Exception as error:
        response_text = await response.text()

        raise RuntimeError(
            f"{operation_name} returnerede ikke gyldigt JSON.\n"
            f"HTTP-status: {response.status}\n"
            f"Svar fra Acadre:\n"
            f"{response_text}"
        ) from error


def _extract_items(
    response_data: dict[str, Any] | list[Any],
) -> list:
    """
    Finder resultatlisten i Acadre-svaret.

    Understøtter blandt andet:

    - Data
    - data
    - Items
    - items
    - Rows
    - rows
    - Results
    - results

    Returns:
        Listen med resultater.
    """
    if isinstance(response_data, list):
        return response_data

    item_keys = (
        "Data",
        "data",
        "Items",
        "items",
        "Rows",
        "rows",
        "Results",
        "results",
    )

    for key in item_keys:
        value = response_data.get(key)

        if isinstance(value, list):
            return value

    for value in response_data.values():
        if isinstance(value, dict):
            nested_items = _extract_items(value)

            if nested_items:
                return nested_items

    raise RuntimeError(
        "Kunne ikke finde resultatlisten i Acadre-svaret. "
        f"Felter på øverste niveau: "
        f"{list(response_data.keys())}"
    )


def _extract_total_count(
    response_data: dict[str, Any] | list[Any],
) -> int | None:
    """
    Finder det samlede antal resultater i Acadre-svaret.

    Understøtter blandt andet:

    - Total
    - total
    - TotalCount
    - totalCount
    - Count
    - count
    - RecordCount
    - recordsTotal

    Returns:
        Samlet antal som heltal eller None.
    """
    if isinstance(response_data, list):
        return None

    total_keys = (
        "Total",
        "total",
        "TotalCount",
        "totalCount",
        "total_count",
        "Count",
        "count",
        "RecordCount",
        "recordCount",
        "recordsTotal",
    )

    for key in total_keys:
        value = response_data.get(key)

        if (
            isinstance(value, int)
            and not isinstance(value, bool)
        ):
            return value

        if (
            isinstance(value, str)
            and value.isdigit()
        ):
            return int(value)

    for value in response_data.values():
        if isinstance(value, dict):
            nested_total = _extract_total_count(value)

            if nested_total is not None:
                return nested_total

    return None

# ============================================================
# START: get_case_by_id
# ============================================================

async def get_case_by_id(
    page: Page,
    case_id: str | int,
    timeout_ms: int = 120_000,
) -> dict[str, Any]:
    """
    Åbner en Acadre-sag direkte via caseId og henter de oplysninger,
    der vises på detaljesiden.

    Funktionen forsøger at hente:
    - Formularfelter: input, select og textarea.
    - Label/værdi-par fra definition lists.
    - Label/værdi-par fra tabeller.
    - Label/værdi-par fra almindelige Acadre-containere.
    - Al synlig tekst fra sidens primære indhold.

    Returns:
        {
            "case_id": "761319",
            "case_url": "...",
            "title": "...",
            "fields": {...},
            "visible_text": "...",
            "diagnostics": {...},
        }
    """
    if isinstance(case_id, bool):
        raise ValueError(
            "case_id må ikke være en bool-værdi."
        )

    normalized_case_id = str(case_id).strip()

    if not normalized_case_id:
        raise ValueError(
            "case_id må ikke være tom."
        )

    if not normalized_case_id.isdigit():
        raise ValueError(
            "case_id skal være et positivt helt tal."
        )

    if int(normalized_case_id) <= 0:
        raise ValueError(
            "case_id skal være større end 0."
        )

    if timeout_ms < 1:
        raise ValueError(
            "timeout_ms skal være mindst 1."
        )

    case_url = (
        f"{ACADRE_CASE_DETAILS_URL}"
        f"?caseId={quote(normalized_case_id, safe='')}"
    )

    print()
    print(
        "Åbner Acadre-sag direkte med "
        f"caseId={normalized_case_id}..."
    )

    try:
        response = await page.goto(
            case_url,
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )
    except Exception as error:
        raise RuntimeError(
            "Acadre-sagen kunne ikke åbnes for "
            f"caseId '{normalized_case_id}'."
        ) from error

    if response is not None and not response.ok:
        raise RuntimeError(
            f"Acadre returnerede HTTP-status {response.status}, "
            f"da sagen med caseId "
            f"'{normalized_case_id}' blev åbnet."
        )

    try:
        await page.wait_for_load_state(
            "networkidle",
            timeout=30_000,
        )
    except Exception:
        print(
            "Sagen blev ikke networkidle inden 30 sekunder. "
            "Fortsætter, fordi DOM'en blev indlæst."
        )

    expected_url_part = (
        "/Frontend/CM/Case/Details"
        f"?caseId={normalized_case_id}"
    )

    if expected_url_part not in page.url:
        raise RuntimeError(
            "Acadre endte ikke på den forventede detaljeside.\n"
            f"Forventede caseId: {normalized_case_id}\n"
            f"Aktuel URL: {page.url}"
        )

    page_title = (await page.title()).strip()

    extraction_result = await page.locator("body").evaluate(
        """
        body => {
            const normalize = value => {
                return (value || "")
                    .replace(/\\u00a0/g, " ")
                    .replace(/[ \\t]+/g, " ")
                    .replace(/\\n[ \\t]+/g, "\\n")
                    .replace(/\\n{3,}/g, "\\n\\n")
                    .trim();
            };

            const isVisible = element => {
                if (!element) {
                    return false;
                }

                const style = window.getComputedStyle(element);

                return (
                    style.display !== "none" &&
                    style.visibility !== "hidden" &&
                    element.getAttribute("aria-hidden") !== "true" &&
                    element.getClientRects().length > 0
                );
            };

            const fields = {};

            const addField = (rawLabel, rawValue) => {
                const label = normalize(rawLabel)
                    .replace(/[:*]+$/, "")
                    .trim();

                const value = normalize(rawValue);

                if (!label || !value || label === value) {
                    return;
                }

                let uniqueLabel = label;
                let number = 2;

                while (
                    Object.prototype.hasOwnProperty.call(
                        fields,
                        uniqueLabel
                    )
                ) {
                    if (fields[uniqueLabel] === value) {
                        return;
                    }

                    uniqueLabel = `${label} (${number})`;
                    number += 1;
                }

                fields[uniqueLabel] = value;
            };

            /*
             * 1. Klassiske formularfelter.
             */
            const formElements = body.querySelectorAll(
                "input, select, textarea"
            );

            for (const element of formElements) {
                if (!isVisible(element)) {
                    continue;
                }

                const type = (
                    element.getAttribute("type") || ""
                ).toLowerCase();

                if (
                    type === "hidden" ||
                    type === "password" ||
                    type === "submit" ||
                    type === "button" ||
                    type === "file"
                ) {
                    continue;
                }

                let value = "";

                if (element.tagName === "SELECT") {
                    const selectedOption =
                        element.options[element.selectedIndex];

                    value = selectedOption
                        ? selectedOption.textContent
                        : "";
                } else if (
                    type === "checkbox" ||
                    type === "radio"
                ) {
                    if (!element.checked) {
                        continue;
                    }

                    value = element.value || "true";
                } else {
                    value = element.value || "";
                }

                let label = "";

                if (element.id) {
                    const escapedId = CSS.escape(element.id);

                    const explicitLabel = body.querySelector(
                        `label[for="${escapedId}"]`
                    );

                    if (explicitLabel) {
                        label = explicitLabel.textContent;
                    }
                }

                if (!label) {
                    const surroundingLabel =
                        element.closest("label");

                    if (surroundingLabel) {
                        label = surroundingLabel.textContent;
                    }
                }

                if (!label) {
                    label =
                        element.getAttribute("aria-label") ||
                        element.getAttribute("placeholder") ||
                        element.getAttribute("name") ||
                        element.id ||
                        "";
                }

                addField(label, value);
            }

            /*
             * 2. Definition lists:
             *
             * <dt>Sagsnummer</dt>
             * <dd>...</dd>
             */
            const definitionTerms =
                body.querySelectorAll("dt");

            for (const term of definitionTerms) {
                if (!isVisible(term)) {
                    continue;
                }

                let valueElement = term.nextElementSibling;

                while (
                    valueElement &&
                    valueElement.tagName !== "DD"
                ) {
                    valueElement =
                        valueElement.nextElementSibling;
                }

                if (
                    valueElement &&
                    isVisible(valueElement)
                ) {
                    addField(
                        term.innerText,
                        valueElement.innerText
                    );
                }
            }

            /*
             * 3. Tabelrækker.
             *
             * Første celle bruges som label.
             * De resterende celler bruges som værdi.
             */
            const tableRows =
                body.querySelectorAll("tr");

            for (const row of tableRows) {
                if (!isVisible(row)) {
                    continue;
                }

                const cells = Array.from(
                    row.querySelectorAll(":scope > th, :scope > td")
                ).filter(isVisible);

                if (cells.length < 2) {
                    continue;
                }

                const label = cells[0].innerText;

                const value = cells
                    .slice(1)
                    .map(cell => normalize(cell.innerText))
                    .filter(Boolean)
                    .join(" | ");

                addField(label, value);
            }

            /*
             * 4. Almindelige label/værdi-containere.
             *
             * Understøtter flere typiske klassenavne uden at være
             * afhængig af ét bestemt Acadre-layout.
             */
            const possibleRows = body.querySelectorAll(
                ".form-group, " +
                ".field, " +
                ".form-field, " +
                ".display-field, " +
                ".control-group, " +
                ".row"
            );

            const labelSelector = [
                "label",
                ".label",
                ".field-label",
                ".control-label",
                ".display-label",
                "[class*='label']"
            ].join(", ");

            const valueSelector = [
                ".value",
                ".field-value",
                ".control-value",
                ".display-field",
                ".form-control-static",
                "[class*='value']"
            ].join(", ");

            for (const row of possibleRows) {
                if (!isVisible(row)) {
                    continue;
                }

                const labelElement =
                    row.querySelector(labelSelector);

                const valueElement =
                    row.querySelector(valueSelector);

                if (
                    labelElement &&
                    valueElement &&
                    labelElement !== valueElement &&
                    isVisible(labelElement) &&
                    isVisible(valueElement)
                ) {
                    addField(
                        labelElement.innerText,
                        valueElement.innerText
                    );
                }
            }

            /*
             * 5. Hent al synlig tekst.
             *
             * main foretrækkes, så navigation og standardsidehoved
             * ikke fylder unødigt i outputtet.
             */
            const contentElement =
                body.querySelector("main") ||
                body.querySelector("[role='main']") ||
                body.querySelector(".main-content") ||
                body.querySelector("#content") ||
                body.querySelector(".content") ||
                body;

            const visibleText = normalize(
                contentElement.innerText
            );

            return {
                fields,
                visibleText,
                diagnostics: {
                    formElementCount:
                        formElements.length,
                    definitionTermCount:
                        definitionTerms.length,
                    tableRowCount:
                        tableRows.length,
                    possibleRowCount:
                        possibleRows.length,
                    iframeCount:
                        body.querySelectorAll("iframe").length,
                },
            };
        }
        """
    )

    fields = extraction_result["fields"]
    visible_text = extraction_result["visibleText"]
    diagnostics = extraction_result["diagnostics"]

    print()
    print(
        f"Sagen med caseId={normalized_case_id} blev åbnet."
    )
    print(f"Aktuel URL: {page.url}")
    print(f"Antal fundne label/værdi-par: {len(fields)}")
    print(f"Diagnostik: {diagnostics}")

    if visible_text:
        print()
        print("=" * 60)
        print("SYNLIG TEKST FRA ACADRE")
        print("=" * 60)
        print(visible_text)
        print("=" * 60)
    else:
        print(
            "Der blev ikke fundet synlig tekst i hoveddokumentet."
        )

    return {
        "case_id": normalized_case_id,
        "case_url": page.url,
        "title": page_title,
        "fields": fields,
        "visible_text": visible_text,
        "diagnostics": diagnostics,
    }


# ============================================================
# SLUT: get_case_by_id
# ============================================================

# ============================================================
# START: get_case_details_by_id
# ============================================================

async def get_case_details_by_id(
    page: Page,
    case_id: str | int,
    timeout_ms: int = 120_000,
) -> dict[str, Any]:
    """
    Henter en Acadre-sag via et autentificeret GET-kald.

    HTML-svaret parses til en dictionary med sagstitel,
    sagsstatus og sagens label/værdi-felter.

    Browserfanen navigeres ikke til sagen.
    """
    from html.parser import HTMLParser
    from urllib.parse import quote

    if isinstance(case_id, bool):
        raise ValueError(
            "case_id må ikke være en bool-værdi."
        )

    normalized_case_id = str(case_id).strip()

    if not normalized_case_id:
        raise ValueError(
            "case_id må ikke være tom."
        )

    if not normalized_case_id.isdigit():
        raise ValueError(
            "case_id skal være et positivt helt tal."
        )

    if int(normalized_case_id) <= 0:
        raise ValueError(
            "case_id skal være større end 0."
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

    request_url = (
        f"{ACADRE_CASE_DETAILS_URL}"
        f"?caseId={quote(normalized_case_id, safe='')}"
    )

    print()
    print(
        "Henter Acadre-sag via GET-kald: "
        f"caseId={normalized_case_id}"
    )

    response = await page.context.request.get(
        request_url,
        headers={
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Referer": (
                f"{ACADRE_BASE_URL}/Frontend/CM/"
            ),
        },
        timeout=timeout_ms,
    )

    response_text = await response.text()

    print(
        f"HTTP-status fra Acadre: {response.status}"
    )

    if not response.ok:
        raise RuntimeError(
            "Acadre GET-kaldet fejlede.\n"
            f"CaseId: {normalized_case_id}\n"
            f"HTTP-status: {response.status}\n"
            f"Svar fra Acadre:\n"
            f"{response_text[:2_000]}"
        )

    content_type = response.headers.get(
        "content-type",
        "",
    )

    if "<html" not in response_text.casefold():
        raise RuntimeError(
            "Acadre returnerede HTTP-success, men svaret "
            "indeholder ikke et HTML-dokument.\n"
            f"Content-Type: {content_type}"
        )

    class CaseDetailsParser(HTMLParser):
        """
        Parser de relevante elementer i Acadres HTML-svar.
        """

        def __init__(self) -> None:
            super().__init__(
                convert_charrefs=True
            )

            self.page_title_parts: list[str] = []
            self.case_title_parts: list[str] = []
            self.case_status_parts: list[str] = []
            self.fields: dict[str, str] = {}

            self.active_tags: list[str] = []
            self.active_classes: list[set[str]] = []

            self.in_page_title = False
            self.in_case_title = False
            self.in_case_status = False
            self.in_form_group = False
            self.in_label = False

            self.current_label_parts: list[str] = []
            self.current_group_text_parts: list[str] = []
            self.form_group_depth = 0

        @staticmethod
        def normalize_text(
            values: list[str],
        ) -> str:
            return " ".join(
                " ".join(values).split()
            ).strip()

        def handle_starttag(
            self,
            tag: str,
            attrs,
        ) -> None:
            attributes = {
                name: value or ""
                for name, value in attrs
            }

            classes = set(
                attributes.get(
                    "class",
                    "",
                ).split()
            )

            self.active_tags.append(tag)
            self.active_classes.append(classes)

            if tag == "title":
                self.in_page_title = True

            if "header-title" in classes:
                self.in_case_title = True

            if "boble" in classes:
                self.in_case_status = True

            if "form-group" in classes:
                if not self.in_form_group:
                    self.in_form_group = True
                    self.form_group_depth = 1
                    self.current_label_parts = []
                    self.current_group_text_parts = []
                else:
                    self.form_group_depth += 1

            elif self.in_form_group and tag not in {
                "br",
                "hr",
                "img",
                "input",
                "meta",
                "link",
            }:
                self.form_group_depth += 1

            if (
                self.in_form_group
                and tag in {"label", "h3"}
            ):
                self.in_label = True

        def handle_startendtag(
            self,
            tag: str,
            attrs,
        ) -> None:
            # Input, meta og lignende har ingen tekst,
            # som er relevant for sagens viste oplysninger.
            return

        def handle_data(
            self,
            data: str,
        ) -> None:
            text = data.strip()

            if not text:
                return

            if self.in_page_title:
                self.page_title_parts.append(text)

            if self.in_case_title:
                self.case_title_parts.append(text)

            if self.in_case_status:
                self.case_status_parts.append(text)

            if self.in_form_group:
                self.current_group_text_parts.append(text)

                if self.in_label:
                    self.current_label_parts.append(text)

        def handle_endtag(
            self,
            tag: str,
        ) -> None:
            if tag == "title":
                self.in_page_title = False

            if self.in_case_title and tag == "span":
                current_classes = (
                    self.active_classes[-1]
                    if self.active_classes
                    else set()
                )

                if "header-title" in current_classes:
                    self.in_case_title = False

            if self.in_case_status and tag == "span":
                current_classes = (
                    self.active_classes[-1]
                    if self.active_classes
                    else set()
                )

                if "boble" in current_classes:
                    self.in_case_status = False

            if (
                self.in_form_group
                and tag in {"label", "h3"}
            ):
                self.in_label = False

            if self.in_form_group:
                self.form_group_depth -= 1

                if self.form_group_depth == 0:
                    self.finish_form_group()

            if self.active_tags:
                self.active_tags.pop()

            if self.active_classes:
                self.active_classes.pop()

        def finish_form_group(self) -> None:
            label = self.normalize_text(
                self.current_label_parts
            ).rstrip(":").strip()

            group_text = self.normalize_text(
                self.current_group_text_parts
            )

            value = group_text

            if label:
                if value.startswith(f"{label}:"):
                    value = value[
                        len(label) + 1:
                    ].strip()
                elif value.startswith(label):
                    value = value[
                        len(label):
                    ].strip()

                if label not in self.fields:
                    self.fields[label] = value

            self.in_form_group = False
            self.in_label = False
            self.current_label_parts = []
            self.current_group_text_parts = []
            self.form_group_depth = 0

    parser = CaseDetailsParser()

    try:
        parser.feed(response_text)
        parser.close()
    except Exception as error:
        raise RuntimeError(
            "HTML-svaret fra Acadre kunne ikke parses."
        ) from error

    page_title = parser.normalize_text(
        parser.page_title_parts
    )

    case_title = parser.normalize_text(
        parser.case_title_parts
    )

    case_status = parser.normalize_text(
        parser.case_status_parts
    )

    fields = parser.fields

    if case_status:
        fields["Sagsstatus"] = case_status

    if not case_title:
        raise RuntimeError(
            "Acadre returnerede HTML, men sagstitlen "
            "kunne ikke findes."
        )

    if not fields:
        raise RuntimeError(
            "Acadre returnerede HTML, men der blev ikke "
            "fundet genkendelige sagsfelter."
        )

    expected_field_names = (
        "Sagsnummer",
        "Sagstype",
        "Ejendomsnummer",
        "Matrikelnummer",
        "Sagsindhold",
        "Sagsansvarlig",
    )

    missing_expected_fields = [
        field_name
        for field_name in expected_field_names
        if field_name not in fields
    ]

    print()
    print("=" * 60)
    print("ACADRE-SAGEN BLEV HENTET VIA GET")
    print("=" * 60)
    print(f"Case ID: {normalized_case_id}")
    print(f"Titel: {case_title}")
    print(f"Sagsstatus: {case_status}")
    print(f"Antal fundne felter: {len(fields)}")

    if missing_expected_fields:
        print(
            "Forventede felter, der ikke blev fundet: "
            f"{missing_expected_fields}"
        )

    result = {
        "case_id": normalized_case_id,
        "request_url": request_url,
        "http_status": response.status,
        "content_type": content_type,
        "page_title": page_title,
        "title": case_title,
        "case_status": case_status,
        "fields": fields,
        "missing_expected_fields": (
            missing_expected_fields
        ),
    }

    print(
        f"Returnerer resultat med nøgler: "
        f"{list(result.keys())}"
    )

    return result


# ============================================================
# SLUT: get_case_details_by_id
# ============================================================

async def find_and_open_case(
    page: Page,
    case_number: str,
    case_type: str = "",
    responsible_unit: str = "",
    page_size: int = 50,
    timeout_ms: int = 120_000,
) -> dict[str, Any]:
    """
    Finder en Acadre-sag ud fra sagsnummeret og åbner sagen direkte.

    Funktionen søger via den eksisterende case_search(), finder et
    entydigt resultat, udtrækker caseId og åbner sagen via den direkte
    Details-URL.

    Returns:
        Dictionary med case_number, case_id, case_url og item.
    """
    if not isinstance(case_number, str) or not case_number.strip():
        raise ValueError(
            "case_number skal være en tekststreng med et sagsnummer."
        )

    if page_size < 1:
        raise ValueError("page_size skal være mindst 1.")

    if timeout_ms < 1:
        raise ValueError("timeout_ms skal være mindst 1.")

    normalized_case_number = case_number.strip()

    search_result = await case_search(
        page=page,
        filter_key=normalized_case_number,
        page_size=page_size,
        case_type=case_type,
        responsible_unit=responsible_unit,
        start_page_index=0,
    )

    items = search_result["items"]

    if not items:
        raise LookupError(
            f"Ingen Acadre-sag blev fundet for sagsnummeret "
            f"'{normalized_case_number}'."
        )

    exact_matches = _find_exact_case_matches(
        items=items,
        case_number=normalized_case_number,
    )

    if len(exact_matches) == 1:
        case_item = exact_matches[0]
    elif len(items) == 1:
        case_item = items[0]
    elif not exact_matches:
        raise LookupError(
            f"Acadre returnerede {len(items)} resultater for "
            f"sagsnummeret '{normalized_case_number}', men ingen "
            "kunne vælges entydigt."
        )
    else:
        raise LookupError(
            f"Acadre returnerede {len(exact_matches)} resultater, "
            f"som indeholder sagsnummeret '{normalized_case_number}'."
        )

    case_id = _extract_case_id(case_item)

    if case_id is None:
        raise RuntimeError(
            f"Sagen '{normalized_case_number}' blev fundet, men "
            "resultatet indeholder ikke et genkendeligt caseId. "
            f"Tilgængelige felter: {list(case_item.keys())}"
        )

    case_url = (
        f"{ACADRE_CASE_DETAILS_URL}"
        f"?caseId={quote(str(case_id), safe='')}"
    )

    try:
        response = await page.goto(
            case_url,
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )
    except Exception as error:
        raise RuntimeError(
            f"Sagen '{normalized_case_number}' med caseId "
            f"'{case_id}' kunne ikke åbnes via '{case_url}'."
        ) from error

    if response is not None and not response.ok:
        raise RuntimeError(
            f"Acadre returnerede HTTP-status {response.status}, "
            f"da sagen '{normalized_case_number}' blev åbnet."
        )

    try:
        await page.wait_for_load_state(
            "networkidle",
            timeout=30_000,
        )
    except Exception:
        print(
            "Sagen blev ikke networkidle inden 30 sekunder. "
            "Fortsætter, fordi DOM'en blev indlæst."
        )

    return {
        "case_number": normalized_case_number,
        "case_id": case_id,
        "case_url": page.url,
        "item": case_item,
    }


def _find_exact_case_matches(
    items: list[dict[str, Any]],
    case_number: str,
) -> list[dict[str, Any]]:
    """Finder resultater, der indeholder det præcise sagsnummer."""
    expected_value = case_number.strip().casefold()

    return [
        item
        for item in items
        if isinstance(item, dict)
        and _item_contains_exact_value(
            value=item,
            expected_value=expected_value,
        )
    ]


def _item_contains_exact_value(
    value: Any,
    expected_value: str,
) -> bool:
    """Leder rekursivt efter en præcis værdi i et API-resultat."""
    if isinstance(value, dict):
        return any(
            _item_contains_exact_value(
                value=nested_value,
                expected_value=expected_value,
            )
            for nested_value in value.values()
        )

    if isinstance(value, list):
        return any(
            _item_contains_exact_value(
                value=list_item,
                expected_value=expected_value,
            )
            for list_item in value
        )

    if value is None or isinstance(value, bool):
        return False

    if isinstance(value, (str, int, float)):
        return str(value).strip().casefold() == expected_value

    return False


def _extract_case_id(
    item: dict[str, Any],
) -> str | int | None:
    """
    Finder caseId i et Acadre-søgeresultat.

    Acadre returnerer normalt sagens interne ID i top-level-feltet
    "Id". Funktionen understøtter desuden eksplicitte varianter som
    "caseId", "case_id" og "case-id" samt indlejrede dictionaries.

    Returns:
        Sagens interne ID som tekst eller heltal.

        Returnerer None, hvis der ikke findes et gyldigt ID.
    """
    if not isinstance(item, dict):
        return None

    explicit_case_id_fields = {
        "caseid",
        "case_id",
        "case-id",
    }

    for key, value in item.items():
        normalized_key = str(key).strip().casefold()

        if normalized_key in explicit_case_id_fields:
            if isinstance(value, bool):
                continue

            if isinstance(value, (str, int)):
                normalized_value = str(value).strip()

                if normalized_value:
                    return value

    top_level_id = item.get("Id")

    if not isinstance(top_level_id, bool):
        if isinstance(top_level_id, (str, int)):
            normalized_top_level_id = str(top_level_id).strip()

            if normalized_top_level_id:
                return top_level_id

    for value in item.values():
        if isinstance(value, dict):
            nested_case_id = _extract_case_id(value)

            if nested_case_id is not None:
                return nested_case_id

        elif isinstance(value, list):
            for list_item in value:
                if not isinstance(list_item, dict):
                    continue

                nested_case_id = _extract_case_id(list_item)

                if nested_case_id is not None:
                    return nested_case_id

    return None