"""HTTP layer over the screening API.

    uvicorn ccs_screen.web.app:app

Importing this package pulls in FastAPI, which is an optional dependency:
install with ``pip install '.[web]'``.
"""

from ccs_screen.web.app import API_VERSION, create_app
from ccs_screen.web.settings import Settings

__all__ = ["API_VERSION", "Settings", "create_app"]
