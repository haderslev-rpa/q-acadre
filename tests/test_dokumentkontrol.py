from __future__ import annotations

import asyncio
import logging
from pprint import pprint

from automation_server_client import AutomationServer, Credential
from dotenv import load_dotenv

from q_acadre.functionality.dokumentkontrol import (
    find_case_documents_by_title_and_date,
)
from q_acadre.functionality.launch import launch_acadre
from q_haderslev_vbo.playwright.browser_session import BrowserSession


# ------------------------------------------------------------
# Testdata
# ------------------------------------------------------------

CREDENTIAL_NAME = "DIRXSDA"
CASE_ID = "763145"
DOKUMENTTITEL = "Konfliktrapport"
DOKUMENTDATO = "16-11-2026"
DATE_FIELD = "main-document-journalization-date"

HEADLESS = False
DEBUG = True
VIDEO = False


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s [%(levelname)s] "
        "%(name)s: %(message)s"
    ),
)

logger = logging.getLogger(__name__)


async def test_find_case_documents_by_title_and_date() -> None:
    """
    Integrationstest af Acadre-dokumentkontrollen.

    Testen:
    1. Henter Acadre-credential fra Automation Server.
    2. Starter den fælles BrowserSession med HTTP-login.
    3. Åbner Acadre via launch_acadre().
    4. Henter alle hoveddokumenter på den valgte sag.
    5. Søger efter præcis titel og journaliseringsdato.
    6. Kontrollerer, at mindst ét dokument findes.
    7. Udskriver alle fundne dokumenter i terminalen.

    Testen er kun læsende. Den opretter, ændrer eller sletter ikke
    dokumenter i Acadre.
    """
    load_dotenv()
    AutomationServer.from_environment()

    credential = Credential.get_credential(
        CREDENTIAL_NAME
    )

    if credential is None:
        raise RuntimeError(
            f"Credential {CREDENTIAL_NAME!r} blev ikke fundet i ATS."
        )

    if not credential.username or not credential.password:
        raise RuntimeError(
            f"Credential {CREDENTIAL_NAME!r} mangler "
            "username eller password."
        )

    session = BrowserSession(
        headless=HEADLESS,
        debug=DEBUG,
        video=VIDEO,
        http_credentials={
            "username": credential.username,
            "password": credential.password,
        },
    )

    page = None

    try:
        logger.info("Starter BrowserSession til Acadre-testen.")

        await session.start()
        page = await session.new_page()

        page = await launch_acadre(
            page=page,
            session=session,
        )

        logger.info(
            "Søger efter dokument. caseId=%s, titel=%r, dato=%s.",
            CASE_ID,
            DOKUMENTTITEL,
            DOKUMENTDATO,
        )

        resultat = await find_case_documents_by_title_and_date(
            page=page,
            case_id=CASE_ID,
            title=DOKUMENTTITEL,
            document_date=DOKUMENTDATO,
            date_field=DATE_FIELD,
            page_size=50,
            folder_id="0",
            timeout_ms=120_000,
        )

        print()
        print("=" * 70)
        print("RESULTAT AF ACADRE-DOKUMENTKONTROL")
        print("=" * 70)
        print(f"Sags-id: {resultat['case_id']}")
        print(f"Søgt titel: {resultat['expected_title']}")
        print(f"Søgt dato: {resultat['expected_date']}")
        print(f"Datofelt: {resultat['date_field']}")
        print(
            "Dokumenter kontrolleret: "
            f"{resultat['documents_checked']}"
        )
        print(f"Sider hentet: {resultat['pages_fetched']}")
        print(f"Fundet: {resultat['found']}")
        print(f"Antal matches: {resultat['match_count']}")
        print("=" * 70)

        if not resultat["found"]:
            raise AssertionError(
                "Testen forventede mindst ét Acadre-dokument med "
                f"titlen {DOKUMENTTITEL!r} og datoen "
                f"{DOKUMENTDATO!r}, men fandt ingen."
            )

        for nummer, dokument in enumerate(
            resultat["matches"],
            start=1,
        ):
            print()
            print(f"MATCH {nummer}")
            print("-" * 70)
            print(
                f"Document ID: "
                f"{dokument['document_id']}"
            )
            print(f"Titel: {dokument['title']}")
            print(f"Dato: {dokument['matched_date']}")
            print(f"Filtype: {dokument['file_type']}")
            print(
                f"Sekvensnummer: "
                f"{dokument['sequence_number']}"
            )
            print(f"Status: {dokument['status']}")
            print(
                f"Dokument-URL: "
                f"{dokument['document_url']}"
            )

        print()
        print("Alle matches:")

        pprint(
            resultat["matches"],
            width=140,
            sort_dicts=False,
        )

        # Det viste eksempel indeholder tre Konfliktrapport-dokumenter.
        # Kontrollen afslører, hvis antallet ændres.
        forventet_antal_matches = 3

        assert resultat["match_count"] == forventet_antal_matches, (
            "Testen forventede "
            f"{forventet_antal_matches} matches, men fandt "
            f"{resultat['match_count']}."
        )

        fundne_document_ids = {
            dokument["document_id"]
            for dokument in resultat["matches"]
        }

        forventede_document_ids = {
            "7002051",
            "7001468",
            "7001395",
        }

        assert fundne_document_ids == forventede_document_ids, (
            "De fundne documentIds stemmer ikke med testdata. "
            f"Forventet={sorted(forventede_document_ids)}, "
            f"fundet={sorted(fundne_document_ids)}."
        )

        print()
        print("=" * 70)
        print("TEST LYKKEDES")
        print(
            "Funktionen fandt de tre forventede Konfliktrapport-"
            "dokumenter uden at ændre noget i Acadre."
        )
        print("=" * 70)

    finally:
        if page is not None and not page.is_closed():
            try:
                await session.close_page(page)

            except Exception:
                logger.exception(
                    "Acadre-siden kunne ikke lukkes separat."
                )

        logger.info("Lukker BrowserSession.")
        await session.close()


async def main() -> None:
    """
    Kører integrationstesten direkte fra VS Code eller terminalen.
    """
    await test_find_case_documents_by_title_and_date()


if __name__ == "__main__":
    asyncio.run(main())
