"""Playwright-selectors til Acadre."""


class DocumentSelectors:
    """
    Selectors til siden Opret dokument og dokumentkvitteringen.

    Acadre genererer dele af elementernes ID'er dynamisk. Derfor
    anvendes de stabile field-ID'er frem for hele profile-ID'et.
    """

    TITLE = (
        'input[id$="_field_de9df981f9424f9eb7e75f1cf0918174"]'
    )

    FILE_INPUT = 'input[type="file"]'

    FILE_BROWSE_BUTTON = "#fileinput-browse-btn"

    DOCUMENT_TYPE = (
        'select[id$="_field_452f9b983b9f4ceb801fdcacd46c2fcc"]'
    )

    CATEGORY = (
        'select[id$="_field_f4d8c454ba1c4301adaaa6c10d8a0581"]'
    )

    CASEWORKER = (
        'input[id*="_field_2441e634a72144b081e5fc3af2342a7f-text-"]'
    )

    CONTENT_DESCRIPTION = (
        'input[id$="_field_42786fc2c8fe4aee909ed1870ecfc2e9"]'
    )

    PUBLIC_ACCESS = (
        'select[id$="_field_f6832745b50f4a82bb1bbfd7be0feab0"]'
    )

    STATUS_CONTAINER = (
        'div[id$="_field_c92e277623a744bf95fa3a2cbb1a3eae_select"]'
    )

    STATUS_SELECTED = (
        f"{STATUS_CONTAINER} .dd-selected"
    )

    STATUS_OPTIONS = (
        f"{STATUS_CONTAINER} .dd-options"
    )

    STATUS_OPTION = (
        f"{STATUS_CONTAINER} .dd-option"
    )

    STATUS_HIDDEN_INPUT = (
        'input[id$="_field_c92e277623a744bf95fa3a2cbb1a3eae"]'
    )

    DATES_SECTION_TOGGLE = (
        'a[href="#-section-content-2"]'
    )

    DATES_SECTION_CONTENT = (
        "#-section-content-2"
    )

    DOCUMENT_DATE = (
        'input[id$="_field_6baea284e501429da6ef7c4d76bd6244"]'
    )

    JOURNAL_DATE = (
        'input[id$="_field_8658ef923d414601910179038331169e"]'
    )

    SAVE_BUTTON = (
        'button[type="submit"]'
        '[name="btn-new-document-submit-button"]'
        '[value="Save"]'
    )

    SUCCESS_STRIP = (
        'div[data-control="strip"].alert-success'
    )

    SUCCESS_MESSAGE = (
        'div[data-control="strip"].alert-success '
        '.strip__content'
    )