"""About / authorship strings for the desktop app."""

from src.metadata import AUTHOR_EMAIL, AUTHOR_NAME, AUTHOR_URL

CREDIT_HTML = (
    f'Desarrollado por<br><a href="{AUTHOR_URL}" style="text-decoration: none;">'
    f"{AUTHOR_NAME}</a><br>"
    f'<a href="mailto:{AUTHOR_EMAIL}" style="text-decoration: none;">'
    f"{AUTHOR_EMAIL}</a>"
)
