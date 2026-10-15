import asyncio
from pprint import pprint

from automation_server_client import (
    AutomationServer,
    Credential,
)
from dotenv import load_dotenv

from q_acadre.functionality.launch import launch_acadre
from q_acadre.functionality.sager import (
    get_case_details_by_id,
)
from q_haderslev_vbo.playwright.browser_session import (
    BrowserSession,
)


load_dotenv()


async def test_get_case_details_by_id() -> None:
    """
    Integrationstest af Acadre GET-kaldet til en sag.

    Testen:
    1. Henter Acadre-credential fra Automation Server.
    2. Starter BrowserSession med HTTP-credentials.
    3. Logger ind i Acadre med launch_acadre().
    4. Henter caseId 761319 via page.context.request.get().
    5. Parser HTML-svaret.
    6. Kontrollerer konkrete forventede værdier.
    7. Udskriver resultatet i terminalen.

    Browserfanen navigeres ikke til sagens Details-side.
    """
    case_id = 761319

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

        print()
        print(
            "Henter sag via autentificeret GET-kald..."
        )

        result = await get_case_details_by_id(
            page=page,
            case_id=case_id,
        )

        if result["http_status"] != 200:
            raise AssertionError(
                "Forventede HTTP-status 200, men modtog "
                f"{result['http_status']}."
            )

        if result["case_id"] != str(case_id):
            raise AssertionError(
                "Det returnerede caseId stemmer ikke med "
                f"det forventede caseId {case_id}."
            )

        if page.url != browser_url_before_request:
            raise AssertionError(
                "Browserfanen blev navigeret under API-kaldet.\n"
                f"Før: {browser_url_before_request}\n"
                f"Efter: {page.url}"
            )

        expected_values = {
            "Sagsnummer": "26/20991",
            "Sagstype": "EJSAG - Ejendomssag",
            "Ejendomsnummer": (
                "JENS HOLMS VEJ 8B, 6510 Gram - "
                "Opførelse af 23 almennyttige boliger"
            ),
            "Matrikelnummer": (
                "1531 Gram Ejerlav, Gram"
            ),
            "Sagsindhold": (
                "Opførelse af 23 almennyttige boliger"
            ),
            "Sagsansvarlig": (
                "Marianne Kryger Olsen"
            ),
            "Sagsdato": "14-10-2026",
            "Journaldato": "15-10-2026",
            "Oprettelsesdato": "15-10-2026",
            "Ændringsdato": "15-10-2026",
            "Sagsansvarlig enhed": (
                "Teknik og Klima"
            ),
            "Emne": (
                "02.34.02 - Byggetilladelse"
            ),
            "Facet": "P19 - Godkendelser",
            "Aktindsigt": "Åben",
            "Principsag": "Nej",
            "Kassationskode": "B - Bevares",
            "Aktindsigtssag": "Nej",
            "Sagsstatus": "B",
        }

        fields = result["fields"]
        errors = []

        for field_name, expected_value in expected_values.items():
            actual_value = fields.get(field_name)

            if actual_value != expected_value:
                errors.append(
                    f"{field_name!r}: "
                    f"forventede {expected_value!r}, "
                    f"men modtog {actual_value!r}"
                )

        expected_title = (
            "JENS HOLMS VEJ 8B, 6510 Gram"
        )

        if result["title"] != expected_title:
            errors.append(
                "'title': "
                f"forventede {expected_title!r}, "
                f"men modtog {result['title']!r}"
            )

        if errors:
            print()
            print("=" * 60)
            print("AFVIGELSER I TESTRESULTATET")
            print("=" * 60)

            for error in errors:
                print(f"- {error}")

            raise AssertionError(
                "Et eller flere Acadre-felter havde "
                "uventede værdier."
            )

        print()
        print("=" * 60)
        print("GET_CASE_DETAILS_BY_ID LYKKEDES")
        print("=" * 60)
        print(f"Case ID: {result['case_id']}")
        print(f"HTTP-status: {result['http_status']}")
        print(f"Content-Type: {result['content_type']}")
        print(f"Sidetitel: {result['page_title']}")
        print(f"Sagstitel: {result['title']}")
        print(f"Sagsstatus: {result['case_status']}")
        print(
            f"Antal fundne felter: "
            f"{len(result['fields'])}"
        )
        print(
            "Browserfanen blev ikke navigeret: "
            f"{page.url}"
        )
        print("=" * 60)

        print()
        print("Fundne sagsoplysninger:")
        print()

        pprint(
            result["fields"],
            width=140,
            sort_dicts=False,
        )

        print()
        print("Råt samlet resultat:")
        print()

        pprint(
            result,
            width=140,
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
        test_get_case_details_by_id()
    )
