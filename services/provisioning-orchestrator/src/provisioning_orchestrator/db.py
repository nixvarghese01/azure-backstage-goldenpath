"""Engine and session factory. In Azure, PostgreSQL logins use Entra tokens from the workload identity."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

_PG_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


def make_engine(url: str, *, entra_auth: bool = False) -> Engine:
    kwargs: dict = {"pool_pre_ping": True}
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

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transaction(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory() as session, session.begin():
        yield session
