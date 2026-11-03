import asyncio
import json
import logging
from html.parser import HTMLParser
from pprint import pprint
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from automation_server_client import AutomationServer, Credential
from dotenv import load_dotenv
from playwright.async_api import Page

from q_acadre.functionality.launch import launch_acadre
from q_acadre.functionality.sager import get_user_by_display_name
from q_haderslev_vbo.playwright.browser_session import BrowserSession


load_dotenv()


logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# ACADRE OG LOGIN
# ------------------------------------------------------------

ACADRE_BASE_URL = (
    "https://udcdokwebfront.intern.udcit.dk"
)

ACADRE_CREATE_CASE_URL = (
    f"{ACADRE_BASE_URL}/Frontend/CM/Case/Create"
)

TIMEOUT_MS = 120_000

CREDENTIAL_NAME = "DIRXSDA"


# ------------------------------------------------------------
# TESTVÆRDIER
# ------------------------------------------------------------

TEST_CASE_TITLE = "Nicolai's testsag 2"

EXPECTED_RESPONSIBLE_EMPLOYEE_TEXT = (
    "DINISNI - Nicolai Isager Nielsen"
)

TEST_CASE_TYPE = "EMSAG"

TEST_CASE_NOTE = (
    "Test bemærkning"
)

TEST_CASE_CONTENT = (
    "test test sagsindhold"
)

TEST_CASE_DATE = "03-11-2026"

TEST_SUBJECT_CODE = "00.01.00"

TEST_FACET_CODE = "G01"

# Sagsansvarlig-ID og ansvarlig enhed hentes nu via
# get_user_by_display_name() fra sager.py.
#
# Der hardkodes derfor ikke:
# - medarbejder-ID
# - afdelings-ID
# - afdelingsnavn


# ------------------------------------------------------------
# ACADRE-FELT-ID'ER
# ------------------------------------------------------------

FIELD_ID_CASE_STATUS = (
    "1de21e9e9a06480f845d3aaed2dfa078"
)

FIELD_ID_TITLE = (
    "ca88abe83c46415ca6586127a2c252f7"
)

FIELD_ID_CASE_TYPE = (
    "821439535b1c400a9ea2d572363257ab"
)

FIELD_ID_NOTE = (
    "99a116a85a8642e1a3c083de0ec57342"
)

FIELD_ID_CASE_CONTENT = (
    "ee1cc61d0bdb48459ecb9b371614c256"
)

FIELD_ID_CASE_DATE = (
    "1e9dce31c21c4d4bb85a627520075fa9"
)

FIELD_ID_SUBJECT = (
    "8f82f00aa13d4dedba31fcae4d6ced67"
)

FIELD_ID_FACET = (
    "eecf954b9e654d5395c9c5e0c82e3945"
)

FIELD_ID_PUBLIC_ACCESS = (
    "f6832745b50f4a82bb1bbfd7be0feab0"
)

FIELD_ID_PRINCIPLE_CASE = (
    "ed962f6479044f658a642bfb78a87eda"
)

FIELD_ID_RESPONSIBLE_EMPLOYEE = (
    "2441e634a72144b081e5fc3af2342a7f"
)

FIELD_ID_RESPONSIBLE_UNIT = (
    "0eee4063baf3412cb7a10a3890c58bb8"
)

FIELD_ID_RETENTION_CODE = (
    "00217b9c8bd347c8b76299d453796b9c"
)

FIELD_ID_DELETION_CODE = (
    "3e4da631f8f74b709b39933b170f859f"
)

FIELD_ID_PUBLIC_ACCESS_CASE = (
    "81cb80f253ed43b88d257bbe02a94edd"
)


# ============================================================
# START: AcadreCreateFormParser
# ============================================================
class AcadreCreateFormParser(HTMLParser):
    """
    Finder Acadres Create-formular og samler inputfelterne.

    Output:
        form_action:
            Formularens action-adresse.

        fields:
            Dictionary med inputfelternes name og value.

    Parseren bevarer samme inputbaserede tilgang som den
    tidligere test. Den kører ikke JavaScript og indsamler
    ikke select- eller textarea-elementer.
    """

    def __init__(self) -> None:
        super().__init__()

        self.form_action = ""
        self.fields: dict[str, str] = {}

        self._in_create_form = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag_name = tag.casefold()
        attributes = dict(attrs)

        if tag_name == "form":
            action = str(
                attributes.get("action") or ""
            ).strip()

            if "/Frontend/CM/Case/Create" in action:
                self._in_create_form = True
                self.form_action = action

            return

        if not self._in_create_form:
            return

        if tag_name != "input":
            return

        field_name = str(
            attributes.get("name") or ""
        ).strip()

        if not field_name:
            return

        field_type = str(
            attributes.get("type") or "text"
        ).casefold()

        # Browseren sender normalt ikke umarkerede
        # checkboxes eller radioknapper.
        if field_type in {"checkbox", "radio"}:
            if "checked" not in attributes:
                return

        field_value = str(
            attributes.get("value") or ""
        )

        self.fields[field_name] = field_value

    def handle_endtag(self, tag: str) -> None:
        if (
            tag.casefold() == "form"
            and self._in_create_form
        ):
            self._in_create_form = False


# ============================================================
# SLUT: AcadreCreateFormParser
# ============================================================


# ============================================================
# START: hent_credential
# ============================================================
def hent_credential() -> Credential:
    """
    Henter Acadre-login fra Automation Server.

    Returnerer:
        Credential med username og password.

    Login er fortsat DIRXSDA. Den ønskede sagsansvarlige
    vælges separat gennem brugeropslaget.
    """

    AutomationServer.from_environment()

    credential = Credential.get_credential(
        CREDENTIAL_NAME
    )

    if credential is None:
        raise RuntimeError(
            f"Credential '{CREDENTIAL_NAME}' "
            "blev ikke fundet i Automation Server."
        )

    if (
        not credential.username
        or not credential.password
    ):
        raise RuntimeError(
            f"Credential '{CREDENTIAL_NAME}' mangler "
            "username eller password."
        )

    return credential


# ============================================================
# SLUT: hent_credential
# ============================================================


# ============================================================
# START: find_entity_profile_instance_id
# ============================================================
def find_entity_profile_instance_id(
    form_data: dict[str, str],
) -> str:
    """
    Henter og validerer den dynamiske profilinstans.

    Bevarer kontrollen af positioningEntityProfileInstanceId.

    Returnerer:
        Den aktuelle entityProfileInstanceId.
    """

    entity_profile_instance_id = str(
        form_data.get(
            "entityProfileInstanceId",
            "",
        )
    ).strip()

    if not entity_profile_instance_id:
        raise RuntimeError(
            "Acadre-formularen indeholder ikke "
            "entityProfileInstanceId."
        )

    positioning_profile_id = str(
        form_data.get(
            "positioningEntityProfileInstanceId",
            "",
        )
    ).strip()

    if not positioning_profile_id:
        raise RuntimeError(
            "Acadre-formularen indeholder ikke "
            "positioningEntityProfileInstanceId."
        )

    if (
        positioning_profile_id
        != entity_profile_instance_id
    ):
        raise RuntimeError(
            "Acadre returnerede forskellige profil-id'er.\n"
            "entityProfileInstanceId: "
            f"{entity_profile_instance_id}\n"
            "positioningEntityProfileInstanceId: "
            f"{positioning_profile_id}"
        )

    return entity_profile_instance_id


# ============================================================
# SLUT: find_entity_profile_instance_id
# ============================================================


# ============================================================
# START: byg_profile_field_name
# ============================================================
def byg_profile_field_name(
    *,
    entity_profile_instance_id: str,
    field_id: str,
) -> str:
    """
    Bygger et Acadre-feltnavn ud fra den aktuelle profilinstans.

    Returnerer:
        profile_<profil-id>_field_<felt-id>
    """

    return (
        f"profile_{entity_profile_instance_id}"
        f"_field_{field_id}"
    )


# ============================================================
# SLUT: byg_profile_field_name
# ============================================================


# ============================================================
# START: find_companion_text_field
# ============================================================
def find_companion_text_field(
    *,
    form_data: dict[str, str],
    value_field_name: str,
) -> tuple[str, str] | None:
    """
    Finder Acadres dynamiske tekstfelt til et lookup-felt.

    Returnerer:
        Tuple med tekstfeltets navn og værdi.

        None hvis tekstfeltet ikke findes.
    """

    expected_prefix = (
        f"{value_field_name}-text-"
    )

    matches = [
        (
            field_name,
            str(field_value),
        )
        for field_name, field_value in form_data.items()
        if field_name.startswith(expected_prefix)
    ]

    if not matches:
        return None

    if len(matches) > 1:
        matching_names = [
            field_name
            for field_name, _ in matches
        ]

        raise RuntimeError(
            "Der blev fundet flere companion-tekstfelter "
            "til det samme Acadre-felt.\n"
            f"Værdifelt: {value_field_name}\n"
            f"Tekstfelter: {matching_names}"
        )

    return matches[0]


# ============================================================
# SLUT: find_companion_text_field
# ============================================================


# ============================================================
# START: normalize_lookup_text
# ============================================================
def normalize_lookup_text(value: str) -> str:
    """
    Normaliserer tekst før sammenligning.

    Flere mellemrum samles, og store/små bogstaver ignoreres.
    """

    return " ".join(
        str(value or "").split()
    ).casefold()


# ============================================================
# SLUT: normalize_lookup_text
# ============================================================


# ============================================================
# START: resolve_responsible_employee
# ============================================================
async def resolve_responsible_employee(
    *,
    page: Page,
    form_data: dict[str, str],
    entity_profile_instance_id: str,
) -> dict[str, str]:
    """
    Slår den ønskede sagsansvarlige op gennem sager.py.

    Ændring fra den tidligere test:
        Formularens standardbruger skal ikke længere matche
        den ønskede sagsansvarlige.

        Standardværdien læses kun til debug.

        Den nye sagsansvarlige og ansvarlige enhed kommer fra:
            get_user_by_display_name()

    Returnerer:
        Feltnavne, nye værdier og oprindelige standardværdier.
    """

    responsible_employee_field_name = (
        byg_profile_field_name(
            entity_profile_instance_id=(
                entity_profile_instance_id
            ),
            field_id=(
                FIELD_ID_RESPONSIBLE_EMPLOYEE
            ),
        )
    )

    default_employee_id = str(
        form_data.get(
            responsible_employee_field_name,
            "",
        )
    ).strip()

    companion_field = find_companion_text_field(
        form_data=form_data,
        value_field_name=(
            responsible_employee_field_name
        ),
    )

    if companion_field is None:
        raise RuntimeError(
            "Det dynamiske tekstfelt til sagsansvarlig blev "
            "ikke fundet i Acadres Create-formular.\n"
            f"Værdifelt: {responsible_employee_field_name}\n"
            f"Standard-ID fra Acadre: {default_employee_id!r}"
        )

    (
        responsible_employee_text_field_name,
        default_employee_text,
    ) = companion_field

    print()
    print("Slår den ønskede sagsansvarlige op via API:")
    print(
        "  Visningsnavn: "
        f"{EXPECTED_RESPONSIBLE_EMPLOYEE_TEXT}"
    )

    user = await get_user_by_display_name(
        page=page,
        display_name=(
            EXPECTED_RESPONSIBLE_EMPLOYEE_TEXT
        ),
        timeout_ms=TIMEOUT_MS,
    )

    print()
    print("JSON-resultat fra brugeropslaget:")

    pprint(
        user,
        width=140,
        sort_dicts=False,
    )

    if not isinstance(user, dict):
        raise RuntimeError(
            "Brugeropslaget returnerede ikke en dictionary."
        )

    raw_employee_id = user.get("id")
    raw_department_id = user.get("departmentId")
    raw_department_name = user.get("departmentName")

    if (
        raw_employee_id is None
        or isinstance(raw_employee_id, bool)
    ):
        raise RuntimeError(
            "Brugeropslaget returnerede ikke et gyldigt id."
        )

    employee_id = str(
        raw_employee_id
    ).strip()

    if (
        not employee_id.isdigit()
        or int(employee_id) <= 0
    ):
        raise RuntimeError(
            "Brugeropslaget returnerede et ugyldigt id.\n"
            f"Modtaget: {raw_employee_id!r}"
        )

    if (
        raw_department_id is None
        or isinstance(raw_department_id, bool)
    ):
        raise RuntimeError(
            "Brugeropslaget returnerede ikke et gyldigt "
            "departmentId."
        )

    department_id = str(
        raw_department_id
    ).strip()

    if (
        not department_id.isdigit()
        or int(department_id) <= 0
    ):
        raise RuntimeError(
            "Brugeropslaget returnerede et ugyldigt "
            "departmentId.\n"
            f"Modtaget: {raw_department_id!r}"
        )

    department_name = str(
        raw_department_name or ""
    ).strip()

    if not department_name:
        raise RuntimeError(
            "Brugeropslaget returnerede et tomt "
            "departmentName."
        )

    return {
        "field_name": (
            responsible_employee_field_name
        ),
        "employee_id": employee_id,
        "text_field_name": (
            responsible_employee_text_field_name
        ),
        "employee_text": (
            EXPECTED_RESPONSIBLE_EMPLOYEE_TEXT
        ),
        "department_id": department_id,
        "department_name": department_name,
        "default_employee_id": default_employee_id,
        "default_employee_text": default_employee_text,
    }


# ============================================================
# SLUT: resolve_responsible_employee
# ============================================================


# ============================================================
# START: set_lookup_text_if_present
# ============================================================
def set_lookup_text_if_present(
    *,
    form_data: dict[str, str],
    value_field_name: str,
    display_text: str,
) -> str | None:
    """
    Opdaterer companion-tekstfeltet, hvis Acadre har leveret det.

    Returnerer:
        Tekstfeltets navn eller None.
    """

    companion_field = find_companion_text_field(
        form_data=form_data,
        value_field_name=value_field_name,
    )

    if companion_field is None:
        return None

    text_field_name, _ = companion_field

    form_data[text_field_name] = display_text

    return text_field_name


# ============================================================
# SLUT: set_lookup_text_if_present
# ============================================================


# ============================================================
# START: byg_test_payload
# ============================================================
def byg_test_payload(
    *,
    base_form_data: dict[str, str],
    entity_profile_instance_id: str,
    responsible_employee: dict[str, str],
) -> dict[str, str]:
    """
    Bygger payloaden til testsagen.

    Standardværdierne fra GET Create kopieres først.

    Sagsansvarlig og ansvarlig enhed overskrives derefter
    med værdierne fra brugeropslaget.

    Returnerer:
        Dictionary til Playwrights form-parameter.
    """

    form_data = dict(base_form_data)

    def profile_field(field_id: str) -> str:
        return byg_profile_field_name(
            entity_profile_instance_id=(
                entity_profile_instance_id
            ),
            field_id=field_id,
        )

    responsible_unit_field_name = profile_field(
        FIELD_ID_RESPONSIBLE_UNIT
    )

    form_data.update(
        {
            "refresh": "false",

            "entityProfileInstanceId": (
                entity_profile_instance_id
            ),

            "positioningEntityProfileInstanceId": (
                entity_profile_instance_id
            ),

            # Sagsstatus
            profile_field(
                FIELD_ID_CASE_STATUS
            ): "B",

            # Titel
            profile_field(
                FIELD_ID_TITLE
            ): TEST_CASE_TITLE,

            # Sagstype
            profile_field(
                FIELD_ID_CASE_TYPE
            ): TEST_CASE_TYPE,

            # Bemærkning
            profile_field(
                FIELD_ID_NOTE
            ): TEST_CASE_NOTE,

            # Sagsindhold
            profile_field(
                FIELD_ID_CASE_CONTENT
            ): TEST_CASE_CONTENT,

            # Sagsdato
            profile_field(
                FIELD_ID_CASE_DATE
            ): TEST_CASE_DATE,

            # Emne
            profile_field(
                FIELD_ID_SUBJECT
            ): json.dumps(
                [
                    {
                        "principleId": "KL Koder",
                        "categoryId": (
                            TEST_SUBJECT_CODE
                        ),
                    }
                ],
                ensure_ascii=False,
                separators=(",", ":"),
            ),

            # Facet
            profile_field(
                FIELD_ID_FACET
            ): json.dumps(
                [
                    {
                        "principleId": "Facetter",
                        "categoryId": (
                            TEST_FACET_CODE
                        ),
                    }
                ],
                ensure_ascii=False,
                separators=(",", ":"),
            ),

            # Aktindsigt
            profile_field(
                FIELD_ID_PUBLIC_ACCESS
            ): "3",

            # Principsag
            profile_field(
                FIELD_ID_PRINCIPLE_CASE
            ): "false",

            # Sagsansvarlig-ID fra brugeropslaget
            responsible_employee["field_name"]: (
                responsible_employee["employee_id"]
            ),

            # Sagsansvarligs visningstekst
            responsible_employee["text_field_name"]: (
                responsible_employee["employee_text"]
            ),

            # Ansvarlig enhed fra brugeropslaget
            responsible_unit_field_name: (
                responsible_employee["department_id"]
            ),

            # Bekræftelsesfelter
            "shouldShowAttachMultiCaseConfirmation": (
                "False"
            ),

            "shouldShowCreateMultiCaseConfirmation": (
                "False"
            ),

            (
                "shouldShowCreateMultiCaseConfirmation"
                "WithPartyWarning"
            ): "False",

            # Kassationskode
            profile_field(
                FIELD_ID_RETENTION_CODE
            ): "B",

            # Slettekode
            profile_field(
                FIELD_ID_DELETION_CODE
            ): "P1825D",

            # Aktindsigtssag
            profile_field(
                FIELD_ID_PUBLIC_ACCESS_CASE
            ): "false",
        }
    )

    # Enhedens tekstfelt bruger nu departmentName
    # fra det samme brugeropslag.
    set_lookup_text_if_present(
        form_data=form_data,
        value_field_name=(
            responsible_unit_field_name
        ),
        display_text=(
            responsible_employee["department_name"]
        ),
    )

    # Kontrollér overskrivningen før POST.
    actual_employee_id = form_data.get(
        responsible_employee["field_name"],
        "",
    )

    actual_employee_text = form_data.get(
        responsible_employee["text_field_name"],
        "",
    )

    if (
        actual_employee_id
        != responsible_employee["employee_id"]
    ):
        raise RuntimeError(
            "Sagsansvarlig-ID blev ikke indsat korrekt "
            "i POST-payloaden."
        )

    if (
        normalize_lookup_text(actual_employee_text)
        != normalize_lookup_text(
            responsible_employee["employee_text"]
        )
    ):
        raise RuntimeError(
            "Sagsansvarligs tekst blev ikke indsat korrekt "
            "i POST-payloaden."
        )

    if (
        form_data.get(responsible_unit_field_name)
        != responsible_employee["department_id"]
    ):
        raise RuntimeError(
            "Ansvarlig enhed blev ikke indsat korrekt "
            "i POST-payloaden."
        )

    return form_data


# ============================================================
# SLUT: byg_test_payload
# ============================================================


# ============================================================
# START: opret_testsag_via_api
# ============================================================
async def opret_testsag_via_api(
    page: Page,
) -> dict[str, Any]:
    """
    Henter en frisk Create-formular og opretter en testsag.

    Sagsansvarlig og enhed hentes gennem funktionen i sager.py.

    Returnerer:
        Dictionary med caseId, URL, profilinstans,
        sagsansvarlig og ansvarlig enhed.
    """

    print()
    print("=" * 70)
    print("TRIN 1: HENTER FRISK ACADRE CREATE-FORMULAR")
    print("=" * 70)

    get_response = await page.context.request.get(
        ACADRE_CREATE_CASE_URL,
        headers={
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Referer": (
                f"{ACADRE_BASE_URL}/Frontend/CM/"
            ),
        },
        timeout=TIMEOUT_MS,
    )

    print(
        "HTTP-status fra GET Create: "
        f"{get_response.status}"
    )

    if not get_response.ok:
        response_text = await get_response.text()

        raise RuntimeError(
            "Acadres Create-formular kunne ikke hentes.\n"
            f"HTTP-status: {get_response.status}\n"
            f"Svar:\n{response_text[:5_000]}"
        )

    html = await get_response.text()

    parser = AcadreCreateFormParser()
    parser.feed(html)

    if not parser.form_action:
        raise RuntimeError(
            "Create-formularens action blev ikke fundet "
            "i HTML-svaret."
        )

    if not parser.fields:
        raise RuntimeError(
            "Der blev ikke fundet nogen inputfelter "
            "i Acadres Create-formular."
        )

    entity_profile_instance_id = (
        find_entity_profile_instance_id(
            parser.fields
        )
    )

    print(
        "Aktuel entityProfileInstanceId: "
        f"{entity_profile_instance_id}"
    )

    print(
        "Antal inputfelter fundet i formularen: "
        f"{len(parser.fields)}"
    )

    # Funktionen er nu async, fordi den foretager brugeropslaget.
    responsible_employee = (
        await resolve_responsible_employee(
            page=page,
            form_data=parser.fields,
            entity_profile_instance_id=(
                entity_profile_instance_id
            ),
        )
    )

    print()
    print("Oprindelig sagsansvarlig fra GET Create:")
    print(
        "  Teknisk ID: "
        f"{responsible_employee['default_employee_id']}"
    )
    print(
        "  Visningstekst: "
        f"{responsible_employee['default_employee_text']}"
    )

    print()
    print("Sagsansvarlig efter overskrivning:")
    print(
        "  Teknisk ID: "
        f"{responsible_employee['employee_id']}"
    )
    print(
        "  Visningstekst: "
        f"{responsible_employee['employee_text']}"
    )

    print()
    print("Ansvarlig enhed fra brugeropslaget:")
    print(
        "  Teknisk ID: "
        f"{responsible_employee['department_id']}"
    )
    print(
        "  Navn: "
        f"{responsible_employee['department_name']}"
    )

    post_url = urljoin(
        ACADRE_CREATE_CASE_URL,
        parser.form_action,
    )

    print()
    print(f"Formularens POST-adresse: {post_url}")

    form_data = byg_test_payload(
        base_form_data=parser.fields,
        entity_profile_instance_id=(
            entity_profile_instance_id
        ),
        responsible_employee=(
            responsible_employee
        ),
    )

    print()
    print("=" * 70)
    print("TRIN 2: OPRETTER DEN RIGTIGE TESTSAG")
    print("=" * 70)

    print(f"Titel: {TEST_CASE_TITLE}")
    print(
        "Sagsansvarlig: "
        f"{responsible_employee['employee_text']}"
    )
    print(
        "Sagsansvarlig ID: "
        f"{responsible_employee['employee_id']}"
    )
    print(
        "Ansvarlig enhed: "
        f"{responsible_employee['department_name']}"
    )
    print(
        "Ansvarlig enhed ID: "
        f"{responsible_employee['department_id']}"
    )
    print(
        "Antal felter i POST-payload: "
        f"{len(form_data)}"
    )

    create_response = await page.context.request.post(
        post_url,
        headers={
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Origin": ACADRE_BASE_URL,
            "Referer": ACADRE_CREATE_CASE_URL,
        },
        form=form_data,
        max_redirects=0,
        timeout=TIMEOUT_MS,
    )

    print(
        "HTTP-status fra POST Create: "
        f"{create_response.status}"
    )

    location = str(
        create_response.headers.get(
            "location",
            "",
        )
        or ""
    ).strip()

    if location:
        print(f"Location-header: {location}")

    if create_response.status not in {
        301,
        302,
        303,
        307,
        308,
    }:
        response_text = await create_response.text()

        raise RuntimeError(
            "Acadre returnerede ikke et redirect efter "
            "sagsoprettelsen.\n"
            f"HTTP-status: {create_response.status}\n"
            f"POST-adresse: {post_url}\n"
            "EntityProfileInstanceId: "
            f"{entity_profile_instance_id}\n"
            "Sagsansvarlig ID: "
            f"{responsible_employee['employee_id']}\n"
            "Sagsansvarlig tekst: "
            f"{responsible_employee['employee_text']}\n"
            f"HTML-svar:\n{response_text[:10_000]}"
        )

    if not location:
        raise RuntimeError(
            "Acadre returnerede et redirect, men "
            "Location-headeren mangler."
        )

    case_url = urljoin(
        ACADRE_BASE_URL,
        location,
    )

    parsed_case_url = urlparse(case_url)

    case_ids = parse_qs(
        parsed_case_url.query
    ).get(
        "caseId",
        [],
    )

    if not case_ids:
        raise RuntimeError(
            "Redirectet indeholder ikke caseId.\n"
            f"Location: {location}"
        )

    case_id = str(case_ids[0]).strip()

    if not case_id:
        raise RuntimeError(
            "Redirectet indeholder et tomt caseId.\n"
            f"Location: {location}"
        )

    if not case_id.isdigit():
        raise RuntimeError(
            "Det returnerede caseId er ikke numerisk.\n"
            f"CaseId: {case_id!r}\n"
            f"Location: {location}"
        )

    return {
        "case_id": case_id,
        "case_url": case_url,
        "redirect_location": location,
        "entity_profile_instance_id": (
            entity_profile_instance_id
        ),
        "responsible_employee_id": (
            responsible_employee["employee_id"]
        ),
        "responsible_employee_text": (
            responsible_employee["employee_text"]
        ),
        "responsible_unit_id": (
            responsible_employee["department_id"]
        ),
        "responsible_unit_text": (
            responsible_employee["department_name"]
        ),
        "title": TEST_CASE_TITLE,
        "post_url": post_url,
        "http_status": create_response.status,
    }


# ============================================================
# SLUT: opret_testsag_via_api
# ============================================================


# ============================================================
# START: test_create_case_via_api
# ============================================================
async def test_create_case_via_api() -> None:
    """
    Integrationstest af sagsoprettelse via Acadre HTTP-kald.

    Testen opretter en rigtig sag.

    Login foretages som DIRXSDA.
    Sagsansvarlig vælges via brugeropslaget.
    """

    credential = hent_credential()

    session = BrowserSession(
        headless=False,
        debug=True,
        video=False,
        http_credentials={
            "username": credential.username,
            "password": credential.password,
        },
    )

    await session.start()

    page = await session.new_page()

    try:
        page = await launch_acadre(
            page=page,
            session=session,
        )

        print()
        print("=" * 70)
        print("ADVARSEL")
        print("=" * 70)
        print(
            "Testen opretter en rigtig sag i Acadre."
        )
        print(f"Titel: {TEST_CASE_TITLE}")
        print(
            "Ønsket sagsansvarlig: "
            f"{EXPECTED_RESPONSIBLE_EMPLOYEE_TEXT}"
        )
        print(
            "Sagsansvarlig-ID og ansvarlig enhed "
            "hentes via API."
        )
        print("=" * 70)

        await asyncio.to_thread(
            input,
            (
                "Tryk Enter for at fortsætte, "
                "eller stop testen med Ctrl+C..."
            ),
        )

        result = await opret_testsag_via_api(
            page=page,
        )

        print()
        print("=" * 70)
        print("SAGEN BLEV OPRETTET")
        print("=" * 70)
        print(f"Titel: {result['title']}")
        print(f"Case ID: {result['case_id']}")
        print(f"Case URL: {result['case_url']}")
        print(
            "Sagsansvarlig: "
            f"{result['responsible_employee_text']}"
        )
        print(
            "Sagsansvarlig ID: "
            f"{result['responsible_employee_id']}"
        )
        print(
            "Ansvarlig enhed: "
            f"{result['responsible_unit_text']}"
        )
        print(
            "Ansvarlig enhed ID: "
            f"{result['responsible_unit_id']}"
        )
        print(
            "Entity profile instance ID: "
            f"{result['entity_profile_instance_id']}"
        )
        print(
            f"HTTP-status: {result['http_status']}"
        )
        print("=" * 70)

        print()
        print("Samlet resultat:")

        pprint(
            result,
            width=140,
            sort_dicts=False,
        )

        # Åbn den oprettede sag, så resultatet
        # kan kontrolleres visuelt.
        await page.goto(
            result["case_url"],
            wait_until="domcontentloaded",
            timeout=TIMEOUT_MS,
        )

        await session.screenshot(
            page=page,
            name=(
                f"ACADRE_API_TEST_CASE_"
                f"{result['case_id']}"
            ),
            always=True,
        )

        await asyncio.to_thread(
            input,
            "\nTryk Enter for at lukke browseren...",
        )

    except Exception:
        logger.exception(
            "API-testen af Acadre-sagsoprettelse fejlede."
        )

        if not page.is_closed():
            await session.screenshot(
                page=page,
                name="ACADRE_CREATE_CASE_API_ERROR",
                always=True,
            )

        raise

    finally:
        await session.close()


# ============================================================
# SLUT: test_create_case_via_api
# ============================================================


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s [%(levelname)s] "
            "%(name)s: %(message)s"
        ),
        force=True,
    )

    asyncio.run(
        test_create_case_via_api()
    )