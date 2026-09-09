import asyncio

from automation_server_client import AutomationServer, Credential
from dotenv import load_dotenv

from q_acadre.functionality.launch import launch_acadre
from q_haderslev_vbo.playwright.browser_session import BrowserSession


load_dotenv()


async def test_launch_acadre() -> None:
    """
    Tester automatisk login til Acadre.

    Processen i testen er:

    1. Hent credential fra ATS.
    2. Opret BrowserSession med HTTP-credentials.
    3. Opret en Playwright-side.
    4. Kald launch_acadre med siden og sessionen.
    5. Kontrollér Acadre-cookien.
    6. Luk BrowserSession.

    Output:
        Funktionen returnerer ikke data.

        Ved succes står browseren på Acadre, og browser-contexten
        indeholder cookien '.acadre_st'.
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

        cookies = await page.context.cookies(
            [
                "https://udcdokwebfront.intern.udcit.dk"
            ]
        )

        cookie_names = {
            cookie["name"]
            for cookie in cookies
        }

        if ".acadre_st" not in cookie_names:
            raise RuntimeError(
                "Launch-testen afsluttede uden "
                "Acadre-cookien '.acadre_st'."
            )

        print()
        print("=" * 60)
        print("LAUNCH-TESTEN LYKKEDES")
        print("=" * 60)
        print(f"Aktiv adresse: {page.url}")
        print("Cookien '.acadre_st' blev fundet.")
        print("Browser-sessionen er klar til API-kald.")
        print("=" * 60)

        await asyncio.to_thread(
            input,
            "\nTryk Enter for at lukke browseren..."
        )

    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(test_launch_acadre())