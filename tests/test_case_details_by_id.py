from __future__ import annotations

import asyncio
from pprint import pprint
from typing import Any

from automation_server_client import (
    AutomationServer,
    Credential,
)
from dotenv import load_dotenv

from q_acadre.functionality.launch import launch_acadre
from q_acadre.functionality.sager import get_case_details_by_id
from q_haderslev_vbo.playwright.browser_session import BrowserSession


# Ret kun denne værdi, når du vil teste et andet Acadre-caseId.
CASE_ID = "761608"

# True kører uden synlig browser.
# False åbner browseren under testen.
HEADLESS = False

# Udvidet timeout til langsomme Acadre-kald.
TIMEOUT_MS = 120_000


async def test_get_case_details_by_id() -> None:
    """
    Henter og udskriver oplysninger for ét konkret Acadre-caseId.

    Testen kontrollerer kun den tekniske struktur og sammenligner ikke
    med hardkodede adresser, titler eller andre sagsværdier.

    Output:
        Udskriver case_id, titel, status og alle fundne Acadre-felter.
        Funktionen returnerer ikke data.
    """
    load_dotenv()
    AutomationServer.from_environment()

    case_id = _valider_case_id(CASE_ID)
    credential = Credential.get_credential("DIRXSDA")

    if credential is None:
        raise RuntimeError(
            "Credential 'DIRXSDA' blev ikke fundet i Automation Server."
        )

    username = str(credential.username or "").strip()
    password = str(credential.password or "")

    if not username or not password:
        raise RuntimeError(
            "Credential 'DIRXSDA' mangler username eller password."
        )

    session = BrowserSession(
        headless=HEADLESS,
        debug=False,
        video=False,
        http_credentials={
            "username": username,
            "password": password,
        },
    )

    page = None

    try:
        await session.start()
        page = await session.new_page()

        page = await launch_acadre(
            page=page,
            session=session,
        )

        browser_url_before_request = page.url

        print()
        print("=" * 80)
        print("HENTER ACADRE-SAG VIA CASE ID")
        print("=" * 80)
        print(f"Case ID: {case_id}")

        result = await get_case_details_by_id(
            page=page,
            case_id=case_id,
            timeout_ms=TIMEOUT_MS,
        )

        _valider_resultat(
            result=result,
            forventet_case_id=case_id,
        )

        if page.url != browser_url_before_request:
            raise AssertionError(
                "Browserfanen blev navigeret under GET-kaldet.\n"
                f"Før: {browser_url_before_request}\n"
                f"Efter: {page.url}"
            )

        print()
        print("=" * 80)
        print("ACADRE-SAGEN BLEV HENTET")
        print("=" * 80)
        print(f"Case ID: {result['case_id']}")
        print(f"HTTP-status: {result['http_status']}")
        print(f"Content-Type: {result['content_type']}")
        print(f"Sidetitel: {result['page_title']}")
        print(f"Sagstitel: {result['title']}")
        print(f"Sagsstatus: {result['case_status']}")
        print(f"Antal felter: {len(result['fields'])}")
        print(
            "Manglende forventede felter: "
            f"{result.get('missing_expected_fields', [])}"
        )
        print(
            "Browserfanen blev ikke navigeret: "
            f"{page.url}"
        )
        print("=" * 80)

        print()
        print("FUNDNE SAGSOPLYSNINGER")
        print("-" * 80)
        pprint(
            result["fields"],
            width=140,
            sort_dicts=False,
        )

        print()
        print("RÅT SAMLET RESULTAT")
        print("-" * 80)
        pprint(
            result,
            width=140,
            sort_dicts=False,
        )

        if not HEADLESS:
            await asyncio.to_thread(
                input,
                "\nTryk Enter for at lukke browseren...",
            )

    finally:
        if page is not None and not page.is_closed():
            await session.close_page(page)

        await session.close()


def _valider_case_id(value: str | int) -> str:
    """Returnerer caseId som valideret tekst."""
    if isinstance(value, bool):
        raise ValueError("CASE_ID må ikke være boolsk.")

    case_id = str(value or "").strip()

    if not case_id.isdigit() or int(case_id) <= 0:
        raise ValueError("CASE_ID skal være et positivt heltal.")

    return case_id


def _valider_resultat(
    *,
    result: dict[str, Any],
    forventet_case_id: str,
) -> None:
    """Kontrollerer den tekniske struktur i Acadre-resultatet."""
    if not isinstance(result, dict):
        raise AssertionError(
            "get_case_details_by_id returnerede ikke en dictionary."
        )

    if result.get("http_status") != 200:
        raise AssertionError(
            "Forventede HTTP-status 200, men modtog "
            f"{result.get('http_status')!r}."
        )

    if result.get("case_id") != forventet_case_id:
        raise AssertionError(
            "Det returnerede caseId stemmer ikke med det forventede. "
            f"Forventet={forventet_case_id!r}, "
            f"modtog={result.get('case_id')!r}."
        )

    if not str(result.get("title") or "").strip():
        raise AssertionError("Acadre-resultatet mangler title.")

    if not str(result.get("case_status") or "").strip():
        raise AssertionError("Acadre-resultatet mangler case_status.")

    if not isinstance(result.get("fields"), dict):
        raise AssertionError(
            "Acadre-resultatets fields er ikke en dictionary."
        )


if __name__ == "__main__":
    asyncio.run(test_get_case_details_by_id())
