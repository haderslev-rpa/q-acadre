import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from automation_server_client import AutomationServer, Credential
from dotenv import load_dotenv
from playwright.async_api import Page

from q_acadre.functionality.launch import launch_acadre
from q_haderslev_vbo.playwright.browser_session import BrowserSession


# Selvstændig integrationstest, ikke en proces.
CREDENTIAL_NAME = "DIRXSDA"
DISPLAY_NAME = "DINISNI - Nicolai Isager Nielsen"
BASE_URL = "https://udcdokwebfront.intern.udcit.dk"
TIMEOUT_MS = 120_000

logger = logging.getLogger(__name__)


async def get_user_by_display_name(
    page: Page,
    display_name: str,
) -> dict[str, Any]:
    """Returnerer Acadres JSON-svar med id og afdelingsoplysninger."""
    if not display_name.strip():
        raise ValueError("Visningsnavnet må ikke være tomt.")

    # Brug en dictionary, ikke listen fra mit tidligere svar.
    # Send almindelig tekst. Playwright foretager URL-encoding.
    form_data = {
        "IncludeUnroledUsers": "false",
        "IncludeInactiveUsers": "false",
        "AreDynamicOperatorsSupported": "false",
        "SupportedEntityTypes[]": "0",
        "displayName": display_name,
    }

    logger.info("Slår brugeren op: %s", display_name)

    response = await page.context.request.post(
        f"{BASE_URL}/Frontend/CM/User/GetUserByDisplayName",
        form=form_data,
        headers={
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/Frontend/CM/",
        },
        max_redirects=0,
        timeout=TIMEOUT_MS,
        fail_on_status_code=False,
    )

    try:
        logger.info("HTTP-status: %s", response.status)

        if not response.ok:
            raise RuntimeError(
                f"Brugeropslaget returnerede HTTP {response.status}. "
                "Kontrollér login og Request Method i Network-fanen."
            )

        try:
            result = await response.json()
        except ValueError as error:
            raise RuntimeError(
                "Svaret er ikke gyldig JSON. "
                "Kontrollér Acadre-sessionen og endpointet."
            ) from error

        print("\nJSON-svar fra Acadre:")
        print(json.dumps(result, ensure_ascii=False, indent=2))

        if not isinstance(result, dict):
            raise RuntimeError("Forventede et JSON-objekt fra Acadre.")

        user_id = result.get("id")
        if (
            isinstance(user_id, bool)
            or not isinstance(user_id, (int, str))
            or not str(user_id).isdigit()
            or int(user_id) <= 0
        ):
            raise RuntimeError("Svaret indeholder ikke et gyldigt bruger-ID.")

        for key in ("departmentId", "departmentName"):
            if key not in result:
                raise RuntimeError(f"Svaret mangler feltet {key!r}.")

        return result
    finally:
        await response.dispose()


async def test_get_user_by_display_name() -> None:
    """Logger ind som DIRXSDA og tester kun brugeropslaget."""
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")

    AutomationServer.from_environment()
    credential = Credential.get_credential(CREDENTIAL_NAME)

    if credential is None or not credential.username or not credential.password:
        raise RuntimeError(
            f"Credential {CREDENTIAL_NAME!r} mangler eller er ufuldstændigt."
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

    try:
        await session.start()
        page = await session.new_page()
        page = await launch_acadre(page=page, session=session)

        user = await get_user_by_display_name(
            page=page,
            display_name=DISPLAY_NAME,
        )

        print("\nBrugeropslaget lykkedes.")
        print(f"Søgt visningsnavn: {DISPLAY_NAME}")
        print(f"Bruger-ID: {user['id']}")
        print(f"Afdelings-ID: {user['departmentId']}")
        print(f"Afdelingsnavn: {user['departmentName']}")
        print("Der er ikke oprettet nogen sag.")

    except Exception:
        logger.exception("Testen af brugeropslaget fejlede.")
        raise
    finally:
        await session.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(test_get_user_by_display_name())
