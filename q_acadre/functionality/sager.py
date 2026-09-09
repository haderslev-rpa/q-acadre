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
        raise ValueError("filter_key skal være en tekststreng.")

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
        raise ValueError("page_size skal være mindst 1.")

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
                await asyncio.sleep(request_delay_seconds)

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

        print(f"Samlet antal resultater: {total_count}")
        print(f"Resultater på første side: {len(first_items)}")
        print(f"Resterende resultater: {remaining_count}")
        print(f"Resterende API-kald: {remaining_pages}")

        for offset in range(1, remaining_pages + 1):
            page_index = start_page_index + offset

            if request_delay_seconds > 0:
                await asyncio.sleep(request_delay_seconds)

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

    if total_count is not None and len(all_items) > total_count:
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
        f"Sender {operation_name}, PageIndex={page_index}..."
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
            f"{operation_name}, PageIndex={page_index}"
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
            f"Svar fra Acadre:\n{response_text}"
        )

    try:
        return await response.json()
    except Exception as error:
        response_text = await response.text()

        raise RuntimeError(
            f"{operation_name} returnerede ikke gyldigt JSON.\n"
            f"HTTP-status: {response.status}\n"
            f"Svar fra Acadre:\n{response_text}"
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
        f"Felter på øverste niveau: {list(response_data.keys())}"
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

        if isinstance(value, int) and not isinstance(value, bool):
            return value

        if isinstance(value, str) and value.isdigit():
            return int(value)

    for value in response_data.values():
        if isinstance(value, dict):
            nested_total = _extract_total_count(value)

            if nested_total is not None:
                return nested_total

    return None