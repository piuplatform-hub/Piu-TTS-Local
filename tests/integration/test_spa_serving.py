"""
Test Frontend Static SPA Serving & Fallback in FastAPI
"""

import pytest


@pytest.mark.asyncio
async def test_spa_index_and_assets(client):
    # Test root serves SPA index.html
    res = await client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "AI Voice Studio" in res.text

    # Test unknown client-side route falls back to index.html (SPA routing)
    res_spa = await client.get("/dashboard/speech-studio")
    assert res_spa.status_code == 200
    assert "text/html" in res_spa.headers.get("content-type", "")
    assert '<div id="root">' in res_spa.text
