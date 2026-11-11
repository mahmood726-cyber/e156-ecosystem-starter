"""Collect the established recall suite in the ordinary CI tests/ command.

Keep its canonical location and test identities for the protective-state ratchet.
Use a distinct filename so default pytest import modes can collect both suites.
"""
from scripts.test_recall import *  # noqa: F401,F403
