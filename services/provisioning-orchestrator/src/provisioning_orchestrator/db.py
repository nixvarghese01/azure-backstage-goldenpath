"""Engine and session factory. In Azure, PostgreSQL logins use Entra tokens from the workload identity."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from provisioning_orchestrator.config import Settings

_PG_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


def make_engine(url: str, *, entra_auth: bool = False, password_file: str | None = None) -> Engine:
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if entra_auth:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)

        @event.listens_for(engine, "do_connect")
        def _inject_token(dialect, conn_rec, cargs, cparams):  # type: ignore[no-untyped-def]
            # Short-lived token as the password; never logged, never stored.
            cparams["password"] = credential.get_token(_PG_SCOPE).token

    elif password_file:
        event.listen(engine, "do_connect", password_injector(password_file))

    return engine


def password_injector(path: str) -> Callable[..., None]:
    """A do_connect hook that reads the password file for each new connection, so a rotated Key Vault
    secret is picked up without a restart."""

    def _inject(dialect: Any, conn_rec: Any, cargs: Any, cparams: dict[str, Any]) -> None:
        cparams["password"] = read_password(path)

    return _inject


def read_password(path: str) -> str:
    """The password in a mounted secret file, without the trailing newline."""
    with open(path, encoding="utf-8") as fh:
        return fh.read().rstrip("\r\n")


def engine_from_settings(settings: Settings) -> Engine:
    """The engine for the configured database and login method. API, worker and migrations all use
    this, so they always authenticate the same way."""
    return make_engine(
        settings.database_url,
        entra_auth=settings.database_entra_auth,
        password_file=settings.database_password_file,
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transaction(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory() as session, session.begin():
        yield session
