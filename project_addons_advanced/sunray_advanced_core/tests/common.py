# -*- coding: utf-8 -*-
"""Shared helpers for sunray_advanced_core tests.

Not imported by `tests/__init__.py`: it holds no test case, only helpers.
"""


def assert_raises_keeping_writes(test, exception, func, *args, **kwargs):
    """Assert `func` raises `exception`, without discarding what it wrote.

    `self.assertRaises` cannot be used when the assertions that follow are
    about records the failing code wrote on its way out. Odoo overrides it to
    wrap the block in a savepoint and roll that savepoint back as soon as the
    expected exception fires (`odoo/tests/common.py::BaseCase._assertRaises`,
    "Context manager that clears the environment upon failure"), so every write
    made by the exception handler is undone before the test can look at it.

    That rollback is a test-harness behaviour, not production behaviour: the IMQ
    worker answers an `IMQError` with `run_cursor.commit()`, and `Cursor.commit`
    flushes the pending updates first — so `last_error`, `scp_setup_error`, the
    audit event and the lockdown all persist for real.

    Args:
        test: the TestCase instance, for `fail()`
        exception: the exception class expected to be raised
        func: callable to invoke
    """
    try:
        func(*args, **kwargs)
    except exception:
        return
    test.fail(f"{exception.__name__} was not raised")
