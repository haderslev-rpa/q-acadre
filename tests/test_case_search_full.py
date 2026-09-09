import asyncio
from pprint import pprint

from automation_server_client import AutomationServer, Credential
from dotenv import load_dotenv

from q_acadre.functionality.launch import launch_acadre
from q_acadre.functionality.sager import case_search_full
from q_haderslev_vbo.playwright.browser_session import BrowserSession


load_dotenv()


async def test_case_search_full() -> None:
    """
    Tester Acadre full search.

    Processen:
    1. Henter credential fra ATS.
    2. Opretter BrowserSession.
    3. Åbner Acadre.
    4. Kalder case_search_full én gang.
    5. case_search_full henter selv alle resultatsider.
    6. Resultatet printes i terminalen.

    Output:
        Funktionen returnerer ikke data.

        Resultatet fra case_search_full indeholder:
        - items
        - total_count
        - pages_fetched
        - page_size
        - raw_first_response

        Der oprettes ingen JSON-fil.
    """

    AutomationServer.from_environment()

    credential = Credential.get_credential(
        "DIRXMCM"
    )

    if credential is None:
        raise RuntimeError(
            "Credential 'DIRXMCM' blev ikke fundet i ATS."
        )

    if not credential.username or not credential.password:
        raise RuntimeError(
            "Credential 'DIRXMCM' mangler username eller password."
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

        print()
        print("Kalder case_search_full...")

        result = await case_search_full(
            page=page,
            page_size=50,
            start_page_index=0,
            case_type="PERSAG",
            active_case="true",
            favorite_case="false",
            own_case="false",
            is_insight="false",
        )

        items = result["items"]

        print()
        print("=" * 60)
        print("CASE_SEARCH_FULL LYKKEDES")
        print("=" * 60)
        print(
            f"Samlet antal ifølge Acadre: "
            f"{result['total_count']}"
        )
        print(
            f"Antal hentede resultater: "
            f"{len(items)}"
        )
        print(
            f"Antal udførte API-kald: "
            f"{result['pages_fetched']}"
        )
        print(
            f"Page size: "
            f"{result['page_size']}"
        )
        print("=" * 60)

        print()
        print("Hentede sager:")
        print()

        pprint(
            items,
            width=140,
            sort_dicts=False,
        )

        await asyncio.to_thread(
            input,
            "\nTryk Enter for at lukke browseren..."
        )

    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(test_case_search_full())