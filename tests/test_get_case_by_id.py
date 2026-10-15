import asyncio
from pprint import pprint

from automation_server_client import AutomationServer, Credential
from dotenv import load_dotenv

from q_acadre.functionality.launch import launch_acadre
from q_acadre.functionality.sager import get_case_by_id
from q_haderslev_vbo.playwright.browser_session import BrowserSession


load_dotenv()


async def test_get_case_by_id() -> None:
    """
    Tester hentning af en Acadre-sag direkte via caseId.

    Testen:
    1. Henter Acadre-credential fra Automation Server.
    2. Opretter BrowserSession med HTTP-credentials.
    3. Logger ind i Acadre.
    4. Henter sagen med caseId 761319.
    5. Kontrollerer det returnerede caseId.
    6. Udskriver sagens oplysninger i terminalen.

    Output:
        Funktionen returnerer ikke data.
        Resultatet fra get_case_by_id() udskrives i terminalen.
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

    if not credential.username or not credential.password:
        raise RuntimeError(
            "Credential 'DIRXSDA' mangler username eller password."
        )

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
        print(
            f"Henter Acadre-sag med caseId {case_id}..."
        )

        result = await get_case_by_id(
            page=page,
            case_id=case_id,
        )

        if str(result["case_id"]) != str(case_id):
            raise AssertionError(
                "Det returnerede caseId stemmer ikke med "
                f"det forventede caseId {case_id}. "
                f"Modtog: {result['case_id']}"
            )

        print()
        print("=" * 60)
        print("GET_CASE_BY_ID LYKKEDES")
        print("=" * 60)
        print(f"Case ID: {result['case_id']}")
        print(f"URL: {result['case_url']}")
        print(f"Sidetitel: {result['title']}")
        print(f"Antal fundne felter: {len(result['fields'])}")
        print("=" * 60)
        print()
        print("Fundne sagsoplysninger:")
        print()

        pprint(
            result["fields"],
            width=140,
            sort_dicts=False,
        )

        await session.screenshot(
            page=page,
            name="ACADRE_TEST_CASE_761319",
            always=True,
        )

        await asyncio.to_thread(
            input,
            "\nTryk Enter for at lukke browseren...",
        )

    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(test_get_case_by_id())