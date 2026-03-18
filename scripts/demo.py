"""Demo script: exercises the real Cognify API end-to-end.

Run with the backend already started on port 8000:
    conda run -n cognify python scripts/demo.py

This will:
1. Login as the editor dev user
2. Fetch real trending topics from Hacker News (live API, no key needed)
3. Rank and deduplicate the topics
4. Create a research session on the top topic (uses stub agents for now)
5. Check the research session status
"""

import asyncio
import json

import httpx

BASE = "http://localhost:8000/api/v1"


async def main() -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Login
        print("\n=== Step 1: Login ===")
        resp = await client.post(
            f"{BASE}/auth/login",
            json={"email": "editor@cognify.dev", "password": "editor123"},
        )
        if resp.status_code != 200:
            print(f"Login failed: {resp.status_code} {resp.text}")
            return
        tokens = resp.json()
        token = tokens["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"Logged in! Token: {token[:20]}...")

        # Step 2: Fetch real HN trends
        print("\n=== Step 2: Fetch Hacker News Trends (live!) ===")
        resp = await client.post(
            f"{BASE}/trends/hackernews/fetch",
            json={
                "domain_keywords": ["AI", "security", "programming"],
                "max_results": 10,
            },
            headers=headers,
        )
        if resp.status_code != 200:
            print(f"HN fetch failed: {resp.status_code} {resp.text}")
            return
        hn_data = resp.json()
        topics = hn_data.get("topics", [])
        print(f"Found {len(topics)} topics from Hacker News:")
        for t in topics[:5]:
            print(f"  - [{t.get('trend_score', 0):.0f}] {t['title']}")

        # Step 3: Rank topics
        if topics:
            print("\n=== Step 3: Rank & Deduplicate Topics ===")
            resp = await client.post(
                f"{BASE}/topics/rank",
                json={
                    "topics": topics,
                    "domain_keywords": ["AI", "security", "programming"],
                    "top_n": 5,
                },
                headers=headers,
            )
            if resp.status_code == 200:
                ranked = resp.json()
                ranked_topics = ranked.get("ranked_topics", [])
                print(f"Top {len(ranked_topics)} ranked topics:")
                for i, t in enumerate(ranked_topics):
                    print(f"  {i+1}. [{t.get('composite_score', 0):.2f}] {t['title']}")
            else:
                print(f"Ranking failed: {resp.status_code} {resp.text}")

        # Step 4: Create research session
        print("\n=== Step 4: Create Research Session ===")
        print("(Uses stub agents — real web search needs SERPAPI_API_KEY)")
        print("Note: research sessions require a topic_id from the database.")
        print("Since we use in-memory repos, we'd need to seed a topic first.")
        print("Skipping for now — try via Swagger UI at http://localhost:8000/docs")

        # Step 5: List research sessions
        print("\n=== Step 5: List Research Sessions ===")
        resp = await client.get(
            f"{BASE}/research/sessions",
            headers=headers,
        )
        if resp.status_code == 200:
            sessions = resp.json()
            print(f"Total sessions: {sessions.get('total', 0)}")
            for s in sessions.get("items", []):
                print(f"  - {s['session_id']}: {s['status']}")
        else:
            print(f"List failed: {resp.status_code} {resp.text}")

        print("\n=== Demo Complete ===")
        print("Try the Swagger UI at http://localhost:8000/docs for interactive testing!")


if __name__ == "__main__":
    asyncio.run(main())
