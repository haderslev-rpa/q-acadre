import asyncio
from pprint import pprint

from automation_server_client import (
    AutomationServer,
    Credential,
)
from dotenv import load_dotenv

from q_acadre.functionality.launch import (
    launch_acadre,
)
from q_acadre.functionality.sager import (
    search_case_by_number,
)
from q_haderslev_vbo.playwright.browser_session import (
    BrowserSession,
)


load_dotenv()


async def test_search_case_by_number() -> None:
    """
    Integrationstest af Acadre-søgning efter sagsnummer.

    Testen:
    1. Henter credential fra Automation Server.
    2. Starter BrowserSession med HTTP-credentials.
    3. Logger ind i Acadre.
    4. Søger efter sagsnummer 26/20909 via API.
    5. Kontrollerer, at det præcise sagsnummer findes.
    6. Kontrollerer konkrete værdier fra søgeresultatet.
    7. Udskriver resultatet i terminalen.

    Browserfanen navigeres ikke under søgningen.
    """
    case_number = "26/20909"

    AutomationServer.from_environment()

    credential = Credential.get_credential(
        "DIRXSDA"
    )

    if credential is None:
        raise RuntimeError(
            "Credential 'DIRXSDA' blev ikke fundet i ATS."
        )

    if (
        not credential.username
        or not credential.password
    ):
        raise RuntimeError(
            "Credential 'DIRXSDA' mangler username "
            "eller password."
        )

    session = BrowserSession(
        headless=False,
        debug=False,
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

        browser_url_before_request = page.url

        result = await search_case_by_number(
            page=page,
            case_number=case_number,
            page_size=20,
            page_index=0,
        )

        if page.url != browser_url_before_request:
            raise AssertionError(
                "Browserfanen blev navigeret under API-kaldet.\n"
                f"Før: {browser_url_before_request}\n"
                f"Efter: {page.url}"
            )

        if result["result_count"] < 1:
            raise AssertionError(
                f"Acadre returnerede ingen resultater for "
                f"sagsnummer '{case_number}'."
            )

        exact_matches = result["exact_matches"]

        if not exact_matches:
            print()
            print("Alle returnerede resultater:")
            pprint(
                result["items"],
                width=160,
                sort_dicts=False,
            )

            raise AssertionError(
                "Acadre returnerede søgeresultater, men ingen "
                f"havde præcis sagsnummeret '{case_number}'."
            )

        if len(exact_matches) > 1:
            print()
            print("Præcise matches:")
            pprint(
                exact_matches,
                width=160,
                sort_dicts=False,
            )

            raise AssertionError(
                "Acadre returnerede mere end ét præcist match "
                f"for sagsnummer '{case_number}'."
            )

        case = exact_matches[0]

        expected_values = {
            "case_id": "761237",
            "case_number": "26/20909",
            "case_type": "EJSAG",
            "description": (
                "BRUNBJERG 72, 6100 Haderslev - "
                "Forhåndsdialog vedr. inst. af solceller"
            ),
            "status": "B - Under behandling",
            "title": (
                "BRUNBJERG 72, 6100 Haderslev"
            ),
        }

        errors = []

        for field_name, expected_value in (
            expected_values.items()
        ):
            actual_value = case.get(field_name)

            if actual_value != expected_value:
                errors.append(
                    f"{field_name!r}: "
                    f"forventede {expected_value!r}, "
                    f"men modtog {actual_value!r}"
                )

        expected_url = (
            "https://udcdokwebfront.intern.udcit.dk"
            "/Frontend/CM/Case/Details?caseId=761237"
        )

        if case["case_url"] != expected_url:
            errors.append(
                "'case_url': "
                f"forventede {expected_url!r}, "
                f"men modtog {case['case_url']!r}"
            )

        if errors:
            print()
            print("=" * 60)
            print("AFVIGELSER I TESTRESULTATET")
            print("=" * 60)

            for error in errors:
                print(f"- {error}")

            print()
            print("Returneret sag:")
            pprint(
                case,
                width=160,
                sort_dicts=False,
            )

            raise AssertionError(
                "Den fundne sag indeholdt uventede værdier."
            )

        print()
        print("=" * 60)
        print("SEARCH_CASE_BY_NUMBER LYKKEDES")
        print("=" * 60)
        print(
            f"Søgt sagsnummer: "
            f"{result['case_number']}"
        )
        print(
            f"Antal søgeresultater: "
            f"{result['result_count']}"
        )
        print(
            f"Antal præcise matches: "
            f"{result['exact_match_count']}"
        )
        print(f"Case ID: {case['case_id']}")
        print(f"Sagsnummer: {case['case_number']}")
        print(f"Sagstype: {case['case_type']}")
        print(f"Titel: {case['title']}")
        print(f"Beskrivelse: {case['description']}")
        print(f"Status: {case['status']}")
        print(f"URL: {case['case_url']}")
        print(
            "Browserfanen blev ikke navigeret: "
            f"{page.url}"
        )
        print("=" * 60)

        print()
        print("Normaliseret søgeresultat:")
        print()

        pprint(
            case,
            width=160,
            sort_dicts=False,
        )

        print()
        print("Alle søgeresultater:")
        print()

        pprint(
            result["items"],
            width=160,
            sort_dicts=False,
        )

        print()
        print("Råt JSON-svar fra Acadre:")
        print()

        pprint(
            result["raw_response"],
            width=180,
            sort_dicts=False,
        )

        await asyncio.to_thread(
            input,
            "\nTryk Enter for at lukke browseren...",
        )

    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(
        test_search_case_by_number()
    )