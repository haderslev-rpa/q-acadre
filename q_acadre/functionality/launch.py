import asyncio

from playwright.async_api import Page


ACADRE_BASE_URL = "https://udcdokwebfront.intern.udcit.dk"

ACADRE_URL = (
    "https://udcdokwebfront.intern.udcit.dk/Frontend/CM/"
)

ACADRE_COOKIE_NAME = ".acadre_st"


async def launch_acadre(
    page: Page,
    session,
    cookie_timeout_seconds: int = 30,
) -> Page:
    """
    Åbner Acadre i en eksisterende BrowserSession.

    BrowserSession skal være oprettet af processen eller testfilen.
    HTTP-credentials skal være sendt til BrowserSession, inden
    session.new_page() bliver kaldt.

    Args:
        page:
            Playwright-siden, som processen har oprettet.

        session:
            Den eksisterende BrowserSession. Bruges til screenshots.

        cookie_timeout_seconds:
            Maksimal ventetid på Acadre-cookien.

    Returns:
        Page:
            Den aktive Acadre-side.

            Siden bruger samme BrowserContext som processen.
            page.context.request kan derfor anvendes til API-kald.

    Raises:
        RuntimeError:
            Hvis Acadre ikke kan åbnes, eller hvis Acadre-cookien
            ikke bliver fundet.
    """

    print(f"Åbner Acadre: {ACADRE_URL}")

    try:
        response = await page.goto(
            ACADRE_URL,
            wait_until="domcontentloaded",
            timeout=120_000,
        )
    except Exception as error:
        await _take_screenshot_safely(
            session=session,
            page=page,
            name="ACADRE_ERROR_navigation",
        )

        raise RuntimeError(
            f"Acadre kunne ikke åbnes på {ACADRE_URL}"
        ) from error

    if response is not None:
        print(f"HTTP-status fra Acadre: {response.status}")

    try:
        await page.wait_for_load_state(
            "networkidle",
            timeout=30_000,
        )
    except Exception:
        print(
            "Acadre blev ikke networkidle inden timeout. "
            "Cookiekontrollen fortsætter."
        )

    cookie_found = await _wait_for_acadre_cookie(
        page=page,
        timeout_seconds=cookie_timeout_seconds,
    )

    if not cookie_found:
        await _print_cookie_names(page)

        await _take_screenshot_safely(
            session=session,
            page=page,
            name="ACADRE_ERROR_cookie_mangler",
        )

        raise RuntimeError(
            f"Cookien '{ACADRE_COOKIE_NAME}' blev ikke fundet. "
            "Kontrollér, at BrowserSession blev oprettet med "
            "HTTP-credentials, før session.new_page() blev kaldt."
        )

    await _take_screenshot_safely(
        session=session,
        page=page,
        name="ACADRE_STEP_1_efter_login",
    )

    print("Login til Acadre blev gennemført.")
    print(f"Aktiv adresse: {page.url}")
    print(f"Cookien '{ACADRE_COOKIE_NAME}' blev fundet.")

    return page


async def _wait_for_acadre_cookie(
    page: Page,
    timeout_seconds: int,
) -> bool:
    """
    Venter på Acadre-sessionens cookie.

    Returns:
        bool:
            True, hvis cookien findes, ellers False.
    """

    attempts = timeout_seconds * 2

    for _ in range(attempts):
        cookies = await page.context.cookies(
            [ACADRE_BASE_URL]
        )

        if any(
            cookie["name"] == ACADRE_COOKIE_NAME
            for cookie in cookies
        ):
            return True

        await asyncio.sleep(0.5)

    return False


async def _print_cookie_names(page: Page) -> None:
    """
    Udskriver kun cookienavne, aldrig cookieindhold.

    Returns:
        None
    """

    cookies = await page.context.cookies(
        [ACADRE_BASE_URL]
    )

    if not cookies:
        print("Der blev ikke fundet cookies for Acadre.")
        return

    print("Følgende cookienavne blev fundet:")

    for cookie in cookies:
        print(f"  - {cookie['name']}")


async def _take_screenshot_safely(
    session,
    page: Page,
    name: str,
) -> None:
    """
    Forsøger at gemme et screenshot.

    Screenshotfejl stopper ikke processen.

    Returns:
        None
    """

    try:
        await session.screenshot(
            page=page,
            name=name,
        )
    except Exception:
        pass