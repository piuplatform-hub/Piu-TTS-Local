"""
AI Voice Studio — Server Module CLI Entrypoint
Enforces UVICORN_PROXY_HEADERS=False and empty forwarded_allow_ips.
"""

import uvicorn
from .config import settings

if __name__ == "__main__":
    uvicorn.run(
        "apps.server.src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        proxy_headers=settings.UVICORN_PROXY_HEADERS,
        forwarded_allow_ips=settings.UVICORN_FORWARDED_ALLOW_IPS,
    )
