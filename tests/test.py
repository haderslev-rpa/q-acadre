import asyncio
import json

from dotenv import load_dotenv
from q_haderslev_vbo.playwright.browser_session import BrowserSession


# Indlæs miljøvariabler fra .env
load_dotenv()


BASE_URL = "https://udcdokwebfront.intern.udcit.dk"

API_URL = (
    f"{BASE_URL}/Frontend/CM/Case/GetGridContextData"
)


async def vent_paa_manuelt_login() -> None:
    """
    Stopper processen, mens brugeren logger ind manuelt.

    Output:
        Funktionen returnerer ikke data.
        Når brugeren trykker Enter i terminalen, fortsætter processen.
    """

    print()
    print("==================================================")
    print("🔐 Log nu ind i Acadre i den åbne browser.")
    print("Når du er færdig med login, skal du vende tilbage")
    print("til VS Code-terminalen og trykke Enter.")
    print("==================================================")
    print()

    await asyncio.to_thread(
        input,
        "▶ Tryk Enter for at fortsætte med API-kaldet..."
    )


async def kontroller_acadre_cookie(context) -> None:
    """
    Kontrollerer, at Acadre-sessionens cookie findes.

    Input:
        context:
            Den aktive Playwright BrowserContext.

    Output:
        Funktionen returnerer ikke cookien.
        Den afsluttes normalt, hvis '.acadre_st' findes.

    Fejl:
        Rejser RuntimeError, hvis cookien ikke findes.
    """

    cookies = await context.cookies([BASE_URL])

    acadre_cookie = next(
        (
            cookie
            for cookie in cookies
            if cookie["name"] == ".acadre_st"
        ),
        None,
    )

    if acadre_cookie is None:
        print()
        print("❌ Cookien '.acadre_st' blev ikke fundet.")

        if cookies:
            print("Følgende cookies blev fundet:")

            # Vi viser kun cookienavne, aldrig følsomme værdier.
            for cookie in cookies:
                print(f"  - {cookie['name']}")
        else:
            print("Der blev ikke fundet nogen cookies for Acadre.")

        raise RuntimeError(
            "Acadre-cookien blev ikke fundet. "
            "Kontrollér, at du er logget helt ind i Acadre, "
            "før du trykker Enter."
        )

    print()
    print("✅ Acadre-cookien '.acadre_st' blev fundet.")
    print("🔒 Cookieværdien bliver ikke udskrevet.")


async def hent_acadre_sager(
    context,
    page_index: int = 1,
) -> dict:
    """
    Sender API-kaldet til Acadre med browser-sessionens cookies.

    Input:
        context:
            Den aktive Playwright BrowserContext.

        page_index:
            Indeks på resultatsiden, der skal hentes.
            0 er første side, og 1 er anden side.

    Output:
        Returnerer Acadres JSON-svar som en dictionary.
        Hvis API'et returnerer en liste, returneres listen direkte.

    Fejl:
        Rejser RuntimeError ved HTTP-fejl eller ugyldigt JSON.
    """

    request_body = {
        "Identifier": "SearchCases",
        "PageSize": 50,
        "PageIndex": page_index,
        "SortingColumns": [
            {
                "ColumnKey": "case-last-modification-date",
                "Direction": "desc",
            }
        ],
        "IsFullSearch": False,
        "CaseType": "",
        "FilterKey": "aktindsigt",
        "ResponsibleUnit": "",
    }

    print()
    print(
        f"📡 Sender API-kald til Acadre med "
        f"PageIndex={page_index}..."
    )

    # context.request deler cookies med browser-contexten.
    # Derfor behøver vi ikke selv at bygge Cookie-headeren.
    response = await context.request.post(
        API_URL,
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/json; charset=UTF-8",
            "Origin": BASE_URL,
            "Referer": BASE_URL,
            "X-Requested-With": "XMLHttpRequest",
        },
        data=request_body,
        timeout=120_000,
    )

    print(f"📨 HTTP-status: {response.status}")

    if not response.ok:
        response_text = await response.text()

        raise RuntimeError(
            "Acadre API-kaldet fejlede.\n"
            f"HTTP-status: {response.status}\n"
            f"Svar fra serveren:\n{response_text}"
        )

    try:
        return await response.json()
    except Exception as error:
        response_text = await response.text()

        raise RuntimeError(
            "Acadre returnerede HTTP-success, men svaret "
            "kunne ikke læses som JSON.\n"
            f"Svar fra serveren:\n{response_text}"
        ) from error


async def test_acadre_api() -> None:
    """
    Starter jeres BrowserSession og tester Acadre-API'et.

    Proces:
        1. Starter jeres egen Playwright BrowserSession.
        2. Åbner Acadres grundadresse.
        3. Stopper, så brugeren kan logge ind manuelt.
        4. Kontrollerer Acadre-cookien.
        5. Sender API-kaldet med PageIndex 1.
        6. Udskriver JSON-svaret.

    Output:
        Funktionen returnerer ikke data.
        Resultatet bliver skrevet i terminalen.
    """

    session = BrowserSession(
        headless=False,
        debug=True,
        video=True,
    )

    await session.start()

    page = await session.new_page()
    context = page.context

    try:
        print("🌐 Åbner Acadre...")

        # Åbn kun Acadres grundadresse.
        # Ingen søge-URL og ingen SearchKey på dette tidspunkt.
        await page.goto(
            BASE_URL,
            wait_until="domcontentloaded",
            timeout=120_000,
        )

        print(f"📍 Browseren står nu på: {page.url}")

        # Stop her, så login kan gennemføres manuelt.
        await vent_paa_manuelt_login()

        print()
        print("▶ Fortsætter efter manuelt login...")
        print(f"📍 Aktuel browseradresse: {page.url}")

        # Cookie findes først efter manuelt login.
        await kontroller_acadre_cookie(context)

        # Send det ønskede API-kald med PageIndex 1.
        response_data = await hent_acadre_sager(
            context=context,
            page_index=1,
        )

        print()
        print("✅ API-kaldet lykkedes.")
        print("📄 JSON-svar:")

        print(
            json.dumps(
                response_data,
                indent=2,
                ensure_ascii=False,
            )
        )

    except Exception as error:
        print()
        print("❌ Testen fejlede:")
        print(error)

        try:
            await page.screenshot(
                path="ERROR_acadre_api.png",
                full_page=True,
            )
            print(
                "📸 Screenshot gemt som "
                "'ERROR_acadre_api.png'."
            )
        except Exception as screenshot_error:
            print(
                "⚠️ Screenshot kunne ikke gemmes:"
            )
            print(screenshot_error)

        raise

    finally:
        print()
        print("🧹 Lukker BrowserSession...")
        await session.close()


if __name__ == "__main__":
    asyncio.run(test_acadre_api())