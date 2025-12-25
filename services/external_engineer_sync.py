import httpx
from config import EXTERNAL_ENGINEER_API


async def sync_engineer_to_external(payload: dict):
    if not EXTERNAL_ENGINEER_API:
        raise RuntimeError("EXTERNAL_ENGINEER_API is not configured")

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            EXTERNAL_ENGINEER_API,
            json=payload,
            headers={"Content-Type": "application/json"}
        )

    if response.status_code not in (200, 201):
        raise Exception(
            f"External API failed: {response.status_code} - {response.text}"
        )

    return response.json()
print("Loaded EXTERNAL_ENGINEER_API:", EXTERNAL_ENGINEER_API)
