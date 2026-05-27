from __future__ import annotations

import argparse
import asyncio
import base64
from typing import Any

import httpx


def _auth_header(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {token}"}


async def run_once(base_url: str, admin_user: str, admin_pass: str, label: str) -> dict[str, Any]:
    headers = _auth_header(admin_user, admin_pass)
    async with httpx.AsyncClient(base_url=base_url, timeout=20.0) as client:
        health = await client.get("/health")
        health.raise_for_status()

        created = await client.post(
            "/admin/sessions",
            headers=headers,
            json={"label": label, "rotation_id": 1, "subject_count": 8},
        )
        created.raise_for_status()
        sid = created.json()["session_id"]

        for market_number in [1]:
            r = await client.post(
                f"/admin/sessions/{sid}/markets",
                headers=headers,
                json={"market_number": market_number},
            )
            r.raise_for_status()
            r = await client.post(
                f"/admin/sessions/{sid}/rounds",
                headers=headers,
                json={"round_number": 1},
            )
            r.raise_for_status()
            r = await client.post(f"/admin/sessions/{sid}/rounds/1/end", headers=headers)
            r.raise_for_status()

        export = await client.get(f"/admin/sessions/{sid}/export.json", headers=headers)
        export.raise_for_status()
        payload = export.json()
        return {"session_id": sid, "markets": len(payload["markets"]), "rounds": len(payload["rounds"])}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backend/API smoke test for pre-session checks.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--admin-user", default="admin")
    parser.add_argument("--admin-pass", default="admin")
    parser.add_argument("--runs", type=int, default=2)
    args = parser.parse_args()

    async def _runner() -> None:
        for i in range(args.runs):
            result = await run_once(
                base_url=args.base_url,
                admin_user=args.admin_user,
                admin_pass=args.admin_pass,
                label=f"smoketest-{i}",
            )
            print(result)

    asyncio.run(_runner())


if __name__ == "__main__":
    main()
