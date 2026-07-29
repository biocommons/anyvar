"""Sets configuration options for alembic"""

from alembic.config import Config

from anyvar.anyvar import get_storage_uri


def configure_alembic(config: Config, db_url_override: str | None = None) -> None:
    """Set configuration options on an Alembic `config` object"""
    config.set_main_option(
        name="sqlalchemy.url",
        value=get_storage_uri(uri_override=db_url_override),
    )
