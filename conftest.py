"""Pytest configuration.

Market data and broker conditions are NOT shipped with this repository (provider rights; see
docs/SOURCES_DES_DONNEES.md). Tests that need them are reported as SKIPPED (not failed) when the files are missing,
so `pytest` gives a clean result on a fresh clone. `tests/` runs entirely on synthetic data.
"""
import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if call.excinfo is not None and call.excinfo.errisinstance(FileNotFoundError) and rep.when in ("setup", "call"):
        rep.outcome = "skipped"
        rep.longrepr = (str(item.fspath), item.location[1] or 0,
                        f"Skipped: local data missing ({call.excinfo.value.filename})")
