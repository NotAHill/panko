"""Panko sync: your cards from your Panko into this Anki (Tools → Panko: sync now).

Made by Panko (https://github.com/NotAHill/panko). It writes only what your Panko renders: it adds and updates
Panko's notes, never your MyNotes field, never deletes anything and never touches review history."""
try:
    from aqt import mw
except ImportError:      # outside Anki: Panko's tests import core.py through this package
    mw = None

if mw is not None:
    from . import ui

    ui.setup()
