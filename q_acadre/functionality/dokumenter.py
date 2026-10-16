import logging
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from playwright.async_api import Page, expect

from q_acadre.selectors import DocumentSelectors


logger = logging.getLogger(__name__)

ACADRE_BASE_URL = "https://udcdokwebfront.intern.udcit.dk"
ACADRE_CREATE_MAIN_DOCUMENT_URL = (
    f"{ACADRE_BASE_URL}/Frontend/CM/MainDocument/Create"
)

DOCUMENT_TYPE_VALUES = {"I", "N", "U", "X"}
PUBLIC_ACCESS_VALUES = {"1", "2", "3"}
STATUS_VALUES = {"J", "P", "R"}


async def open_document_upload_page(
    page: Page,
    case_id: str | int,
    timeout_ms: int = 120_000,
) -> dict[str, Any]:
    """Åbner Opret dokument i den eksisterende Playwright-fane."""
    normalized_case_id = _normalize_required_value(
        case_id,
        "case_id",
    )

    if timeout_ms < 1:
        raise ValueError(
            "timeout_ms skal være mindst 1."
        )

    upload_url = (
        f"{ACADRE_CREATE_MAIN_DOCUMENT_URL}"
        f"?caseId={quote(normalized_case_id, safe='')}"
    )

    logger.info(
        "Åbner Acadre upload-side for caseId %s.",
        normalized_case_id,
    )

    try:
        response = await page.goto(
            upload_url,
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )
    except Exception as error:
        raise RuntimeError(
            "Acadre upload-siden kunne ikke åbnes for "
            f"caseId '{normalized_case_id}'."
        ) from error

    if response is not None and not response.ok:
        raise RuntimeError(
            f"Acadre returnerede HTTP-status {response.status}, "
            f"da upload-siden blev åbnet for caseId "
            f"'{normalized_case_id}'."
        )

    await expect(
        page.locator(DocumentSelectors.TITLE)
    ).to_be_visible(
        timeout=timeout_ms
    )

    return {
        "case_id": normalized_case_id,
        "upload_url": page.url,
        "page": page,
    }


# ============================================================
# START: _select_import_file_mode
# ============================================================

async def _select_import_file_mode(
    page: Page,
    timeout_ms: int,
) -> None:
    """
    Vælger Acadres radioknap "Importer fil".

    Acadre eksponerer radioknappen med det tilgængelige navn
    "Importer fil:".
    """
    import_radio = page.get_by_role(
        "radio",
        name="Importer fil:",
        exact=True,
    )

    radio_count = await import_radio.count()

    if radio_count != 1:
        radio_data = await page.locator(
            'input[type="radio"]'
        ).evaluate_all(
            """
            elements => elements.map(element => ({
                id: element.id || "",
                name: element.name || "",
                value: element.value || "",
                checked: element.checked,
                outerHTML: element.outerHTML
            }))
            """
        )

        raise RuntimeError(
            "Kunne ikke identificere præcis én radioknap "
            "med navnet 'Importer fil:'.\n"
            f"Antal matches: {radio_count}\n"
            f"Radioknapper på siden: {radio_data}"
        )

    await expect(
        import_radio
    ).to_be_visible(
        timeout=timeout_ms,
    )

    await expect(
        import_radio
    ).to_be_enabled(
        timeout=timeout_ms,
    )

    if not await import_radio.is_checked():
        logger.info(
            "Vælger Acadre-radioknappen 'Importer fil'."
        )
        await import_radio.check()

    await expect(
        import_radio
    ).to_be_checked(
        timeout=timeout_ms,
    )

    start_program_radio = page.get_by_role(
        "radio",
        name="Start program:",
        exact=True,
    )

    if await start_program_radio.count() == 1:
        await expect(
            start_program_radio
        ).not_to_be_checked(
            timeout=timeout_ms,
        )

    logger.info(
        "Acadre er sat til 'Importer fil'."
    )


# ============================================================
# SLUT: _select_import_file_mode
# ============================================================


# ============================================================
# START: _wait_for_visible_uploaded_file
# ============================================================

async def _wait_for_visible_uploaded_file(
    page: Page,
    expected_file_name: str,
    timeout_ms: int,
) -> None:
    """
    Venter på, at Acadre viser navnet på den importerede fil.

    Acadre viser filnavnet i et synligt small-element. Det oprindelige
    input[type="file"] kan blive nulstillet af Acadres JavaScript, så
    filvalget valideres på den synlige tekst i stedet for files-listen.
    """
    normalized_file_name = _normalize_required_value(
        expected_file_name,
        "expected_file_name",
    )

    visible_file_name = page.locator(
        "small:visible"
    ).filter(
        has_text=normalized_file_name
    )

    try:
        await expect(
            visible_file_name
        ).to_have_count(
            1,
            timeout=timeout_ms,
        )

        await expect(
            visible_file_name
        ).to_have_text(
            normalized_file_name,
            timeout=timeout_ms,
        )

        await expect(
            visible_file_name
        ).to_be_visible(
            timeout=timeout_ms,
        )
    except Exception as error:
        visible_small_texts = [
            " ".join(text.split())
            for text in await page.locator(
                "small:visible"
            ).all_inner_texts()
            if " ".join(text.split())
        ]

        raise RuntimeError(
            "Acadre viste ikke præcis det forventede filnavn "
            "efter filvalget.\n"
            f"Forventet filnavn: {normalized_file_name!r}\n"
            f"Synlige small-elementer: {visible_small_texts}"
        ) from error

    logger.info(
        "Acadre viser den importerede fil '%s'.",
        normalized_file_name,
    )


# ============================================================
# SLUT: _wait_for_visible_uploaded_file
# ============================================================


# ============================================================
# START: upload_document_to_case
# ============================================================

async def upload_document_to_case(
    page: Page,
    session,
    case_id: str | int,
    file_path: str | Path,
    title: str,
    document_type: str,
    category: str,
    caseworker: str,
    content_description: str,
    public_access: str,
    status: str,
    document_date: str,
    journal_date: str,
    timeout_ms: int = 120_000,
) -> dict[str, Any]:
    """
    Åbner Opret dokument, vælger "Importer fil", udfylder
    formularen, uploader filen og gemmer dokumentet.

    Datoværdier skal gives som dd-mm-yyyy.

    Returns:
        Dictionary med case_id, document_id, document_url,
        success_message og file_path.
    """
    normalized_case_id = _normalize_required_value(
        case_id,
        "case_id",
    )
    normalized_title = _normalize_required_value(
        title,
        "title",
    )
    normalized_category = _normalize_required_value(
        category,
        "category",
    )
    normalized_caseworker = _normalize_required_value(
        caseworker,
        "caseworker",
    )
    normalized_content_description = _normalize_required_value(
        content_description,
        "content_description",
    )
    normalized_document_date = _normalize_required_value(
        document_date,
        "document_date",
    )
    normalized_journal_date = _normalize_required_value(
        journal_date,
        "journal_date",
    )

    _validate_choice(
        document_type,
        DOCUMENT_TYPE_VALUES,
        "document_type",
    )
    _validate_choice(
        public_access,
        PUBLIC_ACCESS_VALUES,
        "public_access",
    )
    _validate_choice(
        status,
        STATUS_VALUES,
        "status",
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

    resolved_file_path = Path(
        file_path
    ).expanduser().resolve()

    if not resolved_file_path.is_file():
        raise FileNotFoundError(
            f"Filen findes ikke: {resolved_file_path}"
        )

    if resolved_file_path.stat().st_size == 0:
        raise RuntimeError(
            f"Filen er tom: {resolved_file_path}"
        )

    try:
        await open_document_upload_page(
            page=page,
            case_id=normalized_case_id,
            timeout_ms=timeout_ms,
        )

        await _take_screenshot_safely(
            session=session,
            page=page,
            name=(
                "ACADRE_DOKUMENT_STEP_1_"
                "uploadside_aabnet"
            ),
        )

        title_locator = page.locator(
            DocumentSelectors.TITLE
        )
        await expect(
            title_locator
        ).to_be_visible(
            timeout=timeout_ms,
        )
        await title_locator.fill(
            normalized_title
        )
        await expect(
            title_locator
        ).to_have_value(
            normalized_title,
            timeout=timeout_ms,
        )

        await _select_import_file_mode(
            page=page,
            timeout_ms=timeout_ms,
        )

        file_input = page.locator(
            DocumentSelectors.FILE_INPUT
        )
        await expect(
            file_input
        ).to_be_attached(
            timeout=timeout_ms,
        )
        await file_input.set_input_files(
            str(resolved_file_path)
        )

        await _wait_for_visible_uploaded_file(
            page=page,
            expected_file_name=resolved_file_path.name,
            timeout_ms=timeout_ms,
        )

        logger.info(
            "Filen '%s' er valgt til import.",
            resolved_file_path.name,
        )

        await _take_screenshot_safely(
            session=session,
            page=page,
            name=(
                "ACADRE_DOKUMENT_STEP_2_"
                "importfil_valgt"
            ),
        )

        document_type_locator = page.locator(
            DocumentSelectors.DOCUMENT_TYPE
        )
        await expect(
            document_type_locator
        ).to_be_visible(
            timeout=timeout_ms,
        )
        await document_type_locator.select_option(
            value=document_type
        )
        await expect(
            document_type_locator
        ).to_have_value(
            document_type,
            timeout=timeout_ms,
        )
        logger.info(
            "Dokumenttype er valgt med værdien '%s'.",
            document_type,
        )

        category_locator = page.locator(
            DocumentSelectors.CATEGORY
        )
        await expect(
            category_locator
        ).to_be_visible(
            timeout=timeout_ms,
        )
        await category_locator.select_option(
            value=normalized_category
        )
        await expect(
            category_locator
        ).to_have_value(
            normalized_category,
            timeout=timeout_ms,
        )
        logger.info(
            "Kategori er valgt med værdien '%s'.",
            normalized_category,
        )

        await _fill_caseworker(
            page=page,
            caseworker=normalized_caseworker,
            timeout_ms=timeout_ms,
        )
        logger.info(
            "Sagsbehandler er udfyldt med '%s'.",
            normalized_caseworker,
        )

        content_description_locator = page.locator(
            DocumentSelectors.CONTENT_DESCRIPTION
        )
        await expect(
            content_description_locator
        ).to_be_visible(
            timeout=timeout_ms,
        )
        await content_description_locator.fill(
            normalized_content_description
        )
        await expect(
            content_description_locator
        ).to_have_value(
            normalized_content_description,
            timeout=timeout_ms,
        )

        public_access_locator = page.locator(
            DocumentSelectors.PUBLIC_ACCESS
        )
        await expect(
            public_access_locator
        ).to_be_visible(
            timeout=timeout_ms,
        )
        await public_access_locator.select_option(
            value=public_access
        )
        await expect(
            public_access_locator
        ).to_have_value(
            public_access,
            timeout=timeout_ms,
        )

        await _select_status(
            page=page,
            status=status,
            timeout_ms=timeout_ms,
        )

        await _expand_dates_section(
            page=page,
            timeout_ms=timeout_ms,
        )
        await _fill_date_if_needed(
            page=page,
            selector=DocumentSelectors.DOCUMENT_DATE,
            date_value=normalized_document_date,
        )
        await _fill_date_if_needed(
            page=page,
            selector=DocumentSelectors.JOURNAL_DATE,
            date_value=normalized_journal_date,
        )

        await expect(
            page.locator(
                DocumentSelectors.DOCUMENT_DATE
            )
        ).to_have_value(
            normalized_document_date,
            timeout=timeout_ms,
        )
        await expect(
            page.locator(
                DocumentSelectors.JOURNAL_DATE
            )
        ).to_have_value(
            normalized_journal_date,
            timeout=timeout_ms,
        )

        await _take_screenshot_safely(
            session=session,
            page=page,
            name=(
                "ACADRE_DOKUMENT_STEP_3_"
                "formular_udfyldt"
            ),
            always=True,
        )

        logger.info(
            "Gemmer dokumentet '%s' på caseId %s.",
            normalized_title,
            normalized_case_id,
        )

        save_button = page.locator(
            DocumentSelectors.SAVE_BUTTON
        )
        await expect(
            save_button
        ).to_be_visible(
            timeout=timeout_ms,
        )
        await expect(
            save_button
        ).to_be_enabled(
            timeout=timeout_ms,
        )

        await _take_screenshot_safely(
            session=session,
            page=page,
            name=(
                "ACADRE_DOKUMENT_STEP_4_"
                "foer_gem"
            ),
            always=True,
        )

        try:
            await save_button.click()

            logger.info(
                "Gem er aktiveret. Venter på Acadres "
                "dokumentdetaljeside."
            )

            await page.wait_for_url(
                "**/Frontend/CM/MainDocument/Details?**",
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
        except Exception as error:
            validation_messages = (
                await _get_validation_messages(
                    page
                )
            )

            await _take_screenshot_safely(
                session=session,
                page=page,
                name=(
                    "ACADRE_DOKUMENT_FEJL_"
                    "efter_gem"
                ),
                always=True,
            )

            raise RuntimeError(
                "Dokumentet blev ikke viderestillet til Acadre "
                "MainDocument/Details efter Gem.\n"
                f"Aktuel URL: {page.url}\n"
                "Kontrollér screenshot "
                "'ACADRE_DOKUMENT_STEP_4_foer_gem'.\n"
                "Synlige validerings- og advarselsbeskeder: "
                f"{validation_messages}"
            ) from error

        await _take_screenshot_safely(
            session=session,
            page=page,
            name=(
                "ACADRE_DOKUMENT_STEP_5_"
                "detaljeside_aabnet"
            ),
        )

        success_strip = page.locator(
            DocumentSelectors.SUCCESS_STRIP
        ).filter(
            has_text="Dokumentet er oprettet."
        )
        await expect(
            success_strip
        ).to_have_count(
            1,
            timeout=timeout_ms,
        )
        await expect(
            success_strip
        ).to_be_visible(
            timeout=timeout_ms,
        )

        success_message_locator = success_strip.locator(
            ".strip__content"
        )
        await expect(
            success_message_locator
        ).to_contain_text(
            "Dokumentet er oprettet.",
            timeout=timeout_ms,
        )

        success_message = (
            await success_message_locator.inner_text()
        ).strip()
        document_id = _extract_document_id(
            page.url
        )

        await _take_screenshot_safely(
            session=session,
            page=page,
            name=(
                "ACADRE_DOKUMENT_STEP_6_"
                "dokument_oprettet"
            ),
        )

        logger.info(
            "Dokumentet blev oprettet med documentId %s.",
            document_id,
        )

        return {
            "case_id": normalized_case_id,
            "document_id": document_id,
            "document_url": page.url,
            "success_message": success_message,
            "file_path": str(resolved_file_path),
        }

    except Exception:
        await _take_screenshot_safely(
            session=session,
            page=page,
            name=(
                "ACADRE_DOKUMENT_FEJL_"
                "upload_flow"
            ),
            always=True,
        )
        raise


# ============================================================
# SLUT: upload_document_to_case
# ============================================================


# ============================================================
# START: _fill_caseworker
# ============================================================

async def _fill_caseworker(
    page: Page,
    caseworker: str,
    timeout_ms: int,
) -> None:
    """
    Udfylder Acadre-sagsbehandleren og bekræfter med Tab.

    Den forventede værdi er eksempelvis:
        dimkro - Marianne Kryger Olsen
    """
    normalized_caseworker = _normalize_required_value(
        caseworker,
        "caseworker",
    )

    locator = page.locator(
        DocumentSelectors.CASEWORKER
    )
    await expect(
        locator
    ).to_be_visible(
        timeout=timeout_ms
    )
    await expect(
        locator
    ).to_be_enabled(
        timeout=timeout_ms
    )

    current_value = (
        await locator.input_value()
    ).strip()

    if current_value == normalized_caseworker:
        await locator.press("Tab")
        return

    logger.info(
        "Udfylder Acadre-sagsbehandler med '%s'.",
        normalized_caseworker,
    )

    await locator.fill("")
    await locator.fill(
        normalized_caseworker
    )

    suggestions = page.locator(
        ".tt-menu:visible .tt-suggestion, "
        ".typeahead.dropdown-menu:visible li"
    )

    try:
        await expect(
            suggestions.first
        ).to_be_visible(
            timeout=min(
                timeout_ms,
                10_000,
            )
        )
    except Exception as error:
        raise RuntimeError(
            "Acadre viste ikke et sagsbehandlerforslag for "
            f"'{normalized_caseworker}'."
        ) from error

    suggestion_texts = [
        " ".join(text.split())
        for text in await suggestions.all_inner_texts()
        if " ".join(text.split())
    ]

    normalized_expected = (
        normalized_caseworker.casefold()
    )
    exact_suggestions = [
        suggestion_text
        for suggestion_text in suggestion_texts
        if suggestion_text.casefold()
        == normalized_expected
    ]

    if not exact_suggestions:
        raise RuntimeError(
            "Acadre viste forslag til sagsbehandleren, men "
            "ingen forslag matchede den forventede værdi præcist.\n"
            f"Forventet: {normalized_caseworker!r}\n"
            f"Forslag: {suggestion_texts}"
        )

    await locator.press("Tab")
    await page.wait_for_timeout(500)

    selected_value = (
        await locator.input_value()
    ).strip()

    if not selected_value:
        raise RuntimeError(
            "Sagsbehandlerfeltet blev tomt efter Tab."
        )

    if (
        selected_value.casefold()
        != normalized_expected
    ):
        raise RuntimeError(
            "Acadre-sagsbehandlerfeltet har en uventet værdi "
            "efter Tab.\n"
            f"Forventet: {normalized_caseworker!r}\n"
            f"Fundet: {selected_value!r}"
        )

    logger.info(
        "Acadre-sagsbehandleren blev valgt med Tab: '%s'.",
        selected_value,
    )


# ============================================================
# SLUT: _fill_caseworker
# ============================================================


async def _select_status(
    page: Page,
    status: str,
    timeout_ms: int,
) -> None:
    """Vælger Acadre-status i den specialbyggede dropdown."""
    hidden_input = page.locator(
        DocumentSelectors.STATUS_HIDDEN_INPUT
    )

    if (
        await hidden_input.input_value()
    ).strip() == status:
        return

    await page.locator(
        DocumentSelectors.STATUS_SELECTED
    ).click()

    option = page.locator(
        DocumentSelectors.STATUS_OPTION
    ).filter(
        has=page.locator(
            f'input.dd-option-value[value="{status}"]'
        )
    )

    await expect(
        option
    ).to_be_visible(
        timeout=timeout_ms
    )
    await option.click()
    await expect(
        hidden_input
    ).to_have_value(
        status,
        timeout=timeout_ms,
    )


async def _expand_dates_section(
    page: Page,
    timeout_ms: int,
) -> None:
    """Udvider Datoer, hvis sektionen er lukket."""
    toggle = page.locator(
        DocumentSelectors.DATES_SECTION_TOGGLE
    )
    await expect(
        toggle
    ).to_be_visible(
        timeout=timeout_ms
    )

    if await toggle.get_attribute(
        "aria-expanded"
    ) != "true":
        await toggle.click()

    await expect(
        page.locator(
            DocumentSelectors.DOCUMENT_DATE
        )
    ).to_be_visible(
        timeout=timeout_ms
    )


async def _fill_date_if_needed(
    page: Page,
    selector: str,
    date_value: str,
) -> None:
    """Beholder korrekt dato, ellers erstattes feltets værdi."""
    locator = page.locator(selector)
    current_value = (
        await locator.input_value()
    ).strip()

    if current_value == date_value:
        return

    await locator.fill(date_value)
    await locator.press("Tab")


async def _take_screenshot_safely(
    session,
    page: Page,
    name: str,
    always: bool = False,
) -> None:
    """Forsøger at gemme et screenshot via BrowserSession."""
    try:
        if session is None:
            return
        if page.is_closed():
            return

        await session.screenshot(
            page=page,
            name=name,
            always=always,
        )
    except Exception as screenshot_error:
        logger.warning(
            "Screenshot '%s' kunne ikke gemmes: %s",
            name,
            screenshot_error,
        )


async def _get_validation_messages(
    page: Page,
) -> list[str]:
    """Henter synlige validerings- og fejlbeskeder fra Acadre."""
    validation_locator = page.locator(
        ".field-validation-error:visible, "
        ".validation-summary-errors:visible, "
        ".alert-danger:visible, "
        ".alert-warning:visible"
    )

    messages: list[str] = []

    for message in await validation_locator.all_inner_texts():
        normalized_message = " ".join(
            message.split()
        )
        if normalized_message:
            messages.append(
                normalized_message
            )

    return messages


def _extract_document_id(
    document_url: str,
) -> str:
    """Henter documentId fra Acadre-kvitteringens URL."""
    query = parse_qs(
        urlparse(document_url).query
    )
    document_ids = query.get(
        "documentId",
        [],
    )

    if (
        not document_ids
        or not document_ids[0].strip()
    ):
        raise RuntimeError(
            "Acadre-kvitteringen indeholder ikke "
            "documentId i URL'en."
        )

    return document_ids[0].strip()


def _normalize_required_value(
    value: str | int,
    field_name: str,
) -> str:
    """Validerer og normaliserer en obligatorisk tekstværdi."""
    if isinstance(value, bool):
        raise ValueError(
            f"{field_name} må ikke være en bool-værdi."
        )

    normalized_value = str(value).strip()

    if not normalized_value:
        raise ValueError(
            f"{field_name} må ikke være tom."
        )

    return normalized_value


def _validate_choice(
    value: str,
    accepted_values: set[str],
    field_name: str,
) -> None:
    """Validerer en kode til et Acadre-valgfelt."""
    if value not in accepted_values:
        accepted_text = ", ".join(
            sorted(accepted_values)
        )
        raise ValueError(
            f"{field_name} skal være en af: "
            f"{accepted_text}."
        )
