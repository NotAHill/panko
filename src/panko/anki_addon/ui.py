"""Panko sync inside Anki: the Tools menu, the settings dialog, and the sync run in the background."""
from __future__ import annotations

from aqt import gui_hooks, mw
from aqt.operations import CollectionOp
from aqt.qt import QAction, QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QTimer, QVBoxLayout
from aqt.utils import showInfo, showWarning, tooltip

from . import core, net

ADDON = __name__.split(".")[0]
_busy = False


def _cfg() -> dict:
    return mw.addonManager.getConfig(ADDON) or {}


def settings(*_args) -> bool:
    """Where your Panko is and the device code made there. True when saved."""
    c = _cfg()
    d = QDialog(mw)
    d.setWindowTitle("Panko sync")
    box = QVBoxLayout(d)
    info = QLabel("In Panko, make a code for this computer: on a server, on your account page; on your own "
                  "computer (panko hub), on the sync page. Paste your Panko's address and the code here.")
    info.setWordWrap(True)
    box.addWidget(info)
    form = QFormLayout()
    server = QLineEdit(c.get("server", ""))
    server.setPlaceholderText("https://your-panko.example, or 127.0.0.1:8770 for panko hub")
    code = QLineEdit(c.get("code", ""))
    code.setEchoMode(QLineEdit.EchoMode.Password)
    form.addRow("Panko address", server)
    form.addRow("device code", code)
    box.addLayout(form)
    start = QCheckBox("sync when Anki opens")
    start.setChecked(bool(c.get("sync_on_start")))
    box.addWidget(start)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(d.accept)
    buttons.rejected.connect(d.reject)
    box.addWidget(buttons)
    d.resize(460, d.sizeHint().height())
    if not d.exec():
        return False
    c.update(server=server.text().strip(), code=code.text().strip(), sync_on_start=start.isChecked())
    mw.addonManager.writeConfig(ADDON, c)
    return True


def _summary(r: dict) -> str:
    done = [f"{r['added']} added" if r["added"] else "", f"{r['updated']} updated" if r["updated"] else ""]
    lines = [", ".join(x for x in done if x) or "Everything was up to date."]
    if r["media"]:
        lines.append(f"{r['media']} pictures and sounds downloaded.")
    if r["audio_not_made"]:
        lines.append(f"{r['audio_not_made']} audio clips aren't made yet: make them on Panko's sync page, then sync "
                     "again.")
    if r["media_missing"]:
        lines.append(f"{r['media_missing']} media files were missing on the server; those cards show without them.")
    if r["failed"]:
        lines.append(f"{len(r['failed'])} cards couldn't be added (no card type is switched on for them): "
                     + ", ".join(r["failed"][:8]))
    return "\n".join(lines)


def sync_now(quiet: bool = False) -> None:
    global _busy
    c = _cfg()
    if not (c.get("server") and c.get("code")):
        if quiet or not settings():
            return
        c = _cfg()
    if _busy or not mw.col:
        return
    _busy = True
    panko = net.Panko(c["server"], c["code"])
    got: dict = {}

    def show(text: str) -> None:
        try:
            mw.progress.update(label=f"Panko sync: {text}")
        except Exception:  # noqa: BLE001  the progress window already closed: nothing to show
            pass

    def say(text: str) -> None:
        mw.taskman.run_on_main(lambda: show(text))

    def op(col):
        r = core.run(col, panko, say=say, version=net.VERSION)
        got.update(r)
        return r["changes"]

    def ok(_changes) -> None:
        global _busy
        _busy = False
        text = _summary(got)
        tooltip("Panko: " + text.replace("\n", " "), period=6000) if quiet else showInfo(text, title="Panko sync")

    def failed(e: Exception) -> None:
        global _busy
        _busy = False
        if quiet and isinstance(e, net.PankoError) and e.unreachable:     # Anki opened while Panko wasn't running
            tooltip(f"Panko: {e}", period=6000)
        elif isinstance(e, (core.Refused, net.PankoError)):
            showWarning(str(e), title="Panko sync")
        else:
            showWarning(f"Panko sync stopped: {e!r}", title="Panko sync")

    CollectionOp(parent=mw, op=op).success(ok).failure(failed).run_in_background()   # it shows its own progress


def _on_open() -> None:
    if _cfg().get("sync_on_start"):
        QTimer.singleShot(2000, lambda: sync_now(quiet=True))


def setup() -> None:
    for label, fn in (("Panko: sync now", lambda: sync_now()), ("Panko: settings…", settings)):
        a = QAction(label, mw)
        a.triggered.connect(fn)
        mw.form.menuTools.addAction(a)
    mw.addonManager.setConfigAction(ADDON, settings)
    gui_hooks.profile_did_open.append(_on_open)
