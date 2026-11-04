"""
Manuel integrationstest af search_department().

Kør fra projektets rod:
    uv run python tests/test_search_department.py

Forudsætning:
    search_department() findes i:
    q_acadre/functionality/sager.py

Testen foretager kun afdelingssøgning.
Den opretter eller ændrer ingen sager.
"""

import asyncio
import logging
from pathlib import Path
from pprint import pprint
from typing import Any

from automation_server_client import AutomationServer, Credential
from dotenv import load_dotenv
from playwright.async_api import Page

from q_acadre.functionality.launch import launch_acadre
from q_acadre.functionality.sager import search_department
from q_haderslev_vbo.playwright.browser_session import BrowserSession


# ------------------------------------------------------------
# INDSTILLINGER TIL DENNE LOKALE OBJECT-TEST
# ------------------------------------------------------------

CREDENTIAL_NAME = "DIRXSDA"

TEST_FILTER_KEY = "*Økonomi og Løn*"

IS_ADMIN_UNITS_FOR_CASE_CREATING = False

TIMEOUT_MS = 120_000

HEADLESS = False

WAIT_BEFORE_CLOSE = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]


logger = logging.getLogger(__name__)


# ============================================================
# START: hent_credential
# ============================================================
def hent_credential() -> Credential:
    """Henter login til Acadre fra Automation Server."""

    load_dotenv(PROJECT_ROOT / ".env")

    AutomationServer.from_environment()

    credential = Credential.get_credential(
        CREDENTIAL_NAME
    )

    if credential is None:
        raise RuntimeError(
            f"Credential {CREDENTIAL_NAME!r} blev ikke fundet."
        )

    if not credential.username or not credential.password:
        raise RuntimeError(
            f"Credential {CREDENTIAL_NAME!r} mangler "
            "username eller password."
        )

    return credential


# ============================================================
# SLUT: hent_credential
# ============================================================


# ============================================================
# START: validate_department_result
# ============================================================
def validate_department_result(
    result: dict[str, Any],
) -> None:
    """
    Kontrollerer resultatets struktur og afdelingernes værdier.

    Testen forventer mindst én afdeling ved søgning på *teknik*.
    Den kræver ikke præcis otte resultater, da data kan ændre sig.
    """

    if not isinstance(result, dict):
        raise AssertionError(
            "search_department() skal returnere en dictionary."
        )

    if result.get("filter_key") != TEST_FILTER_KEY.strip():
        raise AssertionError(
            "Det returnerede søgefilter matcher ikke testen.\n"
            f"Forventet: {TEST_FILTER_KEY.strip()!r}\n"
            f"Modtaget: {result.get('filter_key')!r}"
        )

    items = result.get("items")

    if not isinstance(items, list):
        raise AssertionError(
            "Resultatet mangler en gyldig items-liste."
        )

    total_count = result.get("total_count")

    if (
        isinstance(total_count, bool)
        or not isinstance(total_count, int)
        or total_count < 0
    ):
        raise AssertionError(
            "total_count skal være et ikke-negativt heltal."
        )

    is_limited = result.get(
        "found_items_more_than_limit"
    )

    if not isinstance(is_limited, bool):
        raise AssertionError(
            "found_items_more_than_limit skal være en bool."
        )

    if not items:
        raise AssertionError(
            "Kaldet returnerede ingen afdelinger.\n"
            f"Søgefilter: {TEST_FILTER_KEY!r}\n"
            "Kontrollér filteret og resultatet i Acadre."
        )

    for index, department in enumerate(items, start=1):
        if not isinstance(department, dict):
            raise AssertionError(
                f"Resultat {index} er ikke en dictionary."
            )

        department_id = department.get("id")
        department_name = department.get("name")

        if (
            not isinstance(department_id, str)
            or not department_id.isdigit()
            or int(department_id) <= 0
        ):
            raise AssertionError(
                f"Resultat {index} har et ugyldigt afdelings-ID: "
                f"{department_id!r}"
            )

        if (
            not isinstance(department_name, str)
            or not department_name.strip()
        ):
            raise AssertionError(
                f"Resultat {index} har et ugyldigt afdelingsnavn: "
                f"{department_name!r}"
            )

    # Navnene filtreres ikke lokalt på ordet "teknik".
    # Dit observerede Acadre-svar indeholdt også HB#-navne.


# ============================================================
# SLUT: validate_department_result
# ============================================================


# ============================================================
# START: run_department_search
# ============================================================
async def run_department_search(
    page: Page,
) -> dict[str, Any]:
    """
    Kalder den faktiske funktion fra sager.py og viser resultatet.

    Returnerer:
        Resultatet fra search_department() uændret.
    """

    print()
    print("=" * 70)
    print("TESTER SEARCH_DEPARTMENT")
    print("=" * 70)
    print(f"Søgefilter: {TEST_FILTER_KEY}")
    print(
        "IsAdminUnitsForCaseCreating: "
        f"{IS_ADMIN_UNITS_FOR_CASE_CREATING}"
    )
    print("Testen opretter eller ændrer ingen sager.")
    print("=" * 70)

    result = await search_department(
        page=page,
        filter_key=TEST_FILTER_KEY,
        is_admin_units_for_case_creating=(
            IS_ADMIN_UNITS_FOR_CASE_CREATING
        ),
        timeout_ms=TIMEOUT_MS,
    )

    # Vis hele resultatet før validering, så det også
    # kan bruges til fejlsøgning ved en valideringsfejl.
    print()
    print("Samlet resultat fra search_department():")

    pprint(
        result,
        width=140,
        sort_dicts=False,
    )

    validate_department_result(result)

    print()
    print("=" * 70)
    print("FUNDNE AFDELINGER")
    print("=" * 70)

    for department in result["items"]:
        print(
            f"Afdelingsnr.: {department['id']} | "
            f"Navn: {department['name']}"
        )

    print("=" * 70)
    print(
        "Afdelinger i det returnerede svar: "
        f"{len(result['items'])}"
    )
    print(
        "Serverens TotalCount: "
        f"{result['total_count']}"
    )
    print(
        "Resultatet er begrænset: "
        f"{result['found_items_more_than_limit']}"
    )

    if result["found_items_more_than_limit"]:
        print(
            "BEMÆRK: Serveren har begrænset resultatet. "
            "Brug et mere præcist søgefilter."
        )

    print("=" * 70)

    return result


# ============================================================
# SLUT: run_department_search
# ============================================================


# ============================================================
# START: test_search_department
# ============================================================
async def test_search_department() -> None:
    """
    Starter sessionen, logger ind og tester afdelingssøgningen.

    Denne test ejer browserens livscyklus.
    search_department() genbruger blot den eksisterende session.
    """

    credential = hent_credential()

    session = BrowserSession(
        headless=HEADLESS,
        debug=True,
        video=False,
        http_credentials={
            "username": credential.username,
            "password": credential.password,
        },
    )

    page = None

    try:
        logger.info(
            "Starter Acadre-test med credential %s.",
            CREDENTIAL_NAME,
        )

        await session.start()

        page = await session.new_page()

        page = await launch_acadre(
            page=page,
            session=session,
        )

        logger.info(
            "Acadre-sessionen er klar. Starter afdelingssøgning."
        )

        await run_department_search(
            page=page,
        )

        print()
        print("TESTEN BLEV GENNEMFØRT.")
        print(
            "Afdelingssøgningen returnerede resultater "
            "med gyldige ID'er og navne."
        )
        print("Der er ikke oprettet eller ændret nogen sag.")

        if WAIT_BEFORE_CLOSE:
            await asyncio.to_thread(
                input,
                "\nTryk Enter for at lukke browseren...",
            )

    except Exception:
        logger.exception(
            "Testen af search_department() fejlede."
        )

        if page is not None and not page.is_closed():
            try:
                await session.screenshot(
                    page=page,
                    name="ACADRE_SEARCH_DEPARTMENT_ERROR",
                    always=True,
                )
            except Exception:
                logger.warning(
                    "Fejlscreenshot kunne ikke gemmes.",
                    exc_info=True,
                )

        raise

    finally:
        logger.info("Lukker browsersessionen.")

        await session.close()


# ============================================================
# SLUT: test_search_department
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
        test_search_department()
    )