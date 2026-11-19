"""Mirror one collector's published metadata to its private hosted dashboard."""

import asyncio
import hashlib
import json
import logging

import httpx

log = logging.getLogger("uvicorn.error")


async def publish(collector, origin: str, service_token: str, write_key: str) -> None:
    if not origin.startswith("https://") or not service_token or not write_key:
        raise ValueError(
            "A private HTTPS site and both server-side credentials are required"
        )
    headers = {
        "OAI-Sites-Authorization": f"Bearer {service_token}",
        "X-Radar-Writer": write_key,
    }
    directory_version = ""
    async with httpx.AsyncClient(
        timeout=20, follow_redirects=False, headers=headers
    ) as client:
        while True:
            try:
                data = json.dumps(collector.directory.data, separators=(",", ":"))
                version = hashlib.sha256(data.encode()).hexdigest()
                if version != directory_version:
                    response = await client.put(
                        origin.rstrip("/") + "/api/directory",
                        content=data,
                        headers={"Content-Type": "application/json"},
                    )
                    response.raise_for_status()
                    directory_version = version
                response = await client.put(
                    origin.rstrip("/") + "/api/live", json=collector.snapshot()
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                log.warning(
                    "Hosted mirror update deferred (%s)",
                    getattr(
                        getattr(exc, "response", None),
                        "status_code",
                        type(exc).__name__,
                    ),
                )
            await asyncio.sleep(15)
