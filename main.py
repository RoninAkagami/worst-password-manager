import hashlib
import os
import json
import string
import secrets
import math
import base64
import requests

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Button, Input, Label,
    Static, RichLog, DataTable, TextArea
)
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.screen import Screen, ModalScreen
from textual import on
from textual.binding import Binding

# ── paths ──────────────────────────────────────────────────────────────────────
DATA_DIR       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MASTER_FILE    = os.path.join(DATA_DIR, "master.json")
PASSWORDS_FILE = os.path.join(DATA_DIR, "passwords.json")
CUSTOM_DIR     = os.path.join(DATA_DIR, "custom")

os.makedirs(DATA_DIR,   exist_ok=True)
os.makedirs(CUSTOM_DIR, exist_ok=True)


# ── crypto helpers ─────────────────────────────────────────────────────────────
def _make_cipher(master: str, salt: bytes) -> Fernet:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100_000)
    key = base64.urlsafe_b64encode(kdf.derive(master.encode()))
    return Fernet(key)

def _hash_master(master: str, salt: bytes) -> str:
    return hashlib.sha3_512(master.encode() + salt).hexdigest()

def _check_password(master: str) -> tuple[bool, bytes]:
    with open(MASTER_FILE) as f:
        data = json.load(f)
    salt = base64.b64decode(data["salt"])
    return _hash_master(master, salt) == data["master"], salt

def _save_master(master: str):
    salt = os.urandom(16)
    data = {"master": _hash_master(master, salt), "salt": base64.b64encode(salt).decode()}
    with open(MASTER_FILE, "w") as f:
        json.dump(data, f, indent=4)

def _load_passwords() -> dict:
    if os.path.exists(PASSWORDS_FILE):
        with open(PASSWORDS_FILE) as f:
            return json.load(f)
    return {}

def _save_passwords(passwords: dict):
    with open(PASSWORDS_FILE, "w") as f:
        json.dump(passwords, f, indent=4)

def _password_strength(pswd: str) -> tuple[float, str, str]:
    N = 0
    if any(c.isupper()     for c in pswd): N += 26
    if any(c.islower()     for c in pswd): N += 26
    if any(c.isdigit()     for c in pswd): N += 10
    if any(c.isspace()     for c in pswd): N += 1
    if any(not c.isalnum() for c in pswd): N += 32
    L = len(pswd)
    if N == 0 or L == 0:
        return 0.0, "Ghost password. Spooky but useless.", "red"
    bits = math.log2(N ** L)
    if   bits < 28:  label, color = "Cracked before you finish blinking",          "red"
    elif bits < 36:  label, color = "My grandma guessed this in 3 tries",          "dark_orange"
    elif bits < 60:  label, color = "Passable. Like a C- on a Friday afternoon.",  "yellow"
    elif bits < 80:  label, color = "Solid. You are not totally cooked.",          "green"
    elif bits < 100: label, color = "Very strong. Hacker cries. Goes home.",       "bright_green"
    else:            label, color = "FORTRESS. Even the NSA is tired just looking.","bright_cyan"
    return bits, label, color


# ══════════════════════════════════════════════════════════════════════════════
# MODAL: simple message
# ══════════════════════════════════════════════════════════════════════════════
class MsgModal(ModalScreen):
    DEFAULT_CSS = """
    MsgModal { align: center middle; }
    MsgModal #dialog {
        background: $surface; border: heavy $primary;
        padding: 2 4; width: 58; height: auto;
    }
    MsgModal #msg { margin-bottom: 1; }
    MsgModal #ok  { width: 100%; }
    """
    def __init__(self, message: str):
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._message, id="msg")
            yield Button("Understood. Moving on.", id="ok", variant="primary")

    @on(Button.Pressed, "#ok")
    def close(self): self.dismiss()


# ══════════════════════════════════════════════════════════════════════════════
# MODAL: Add password
# ══════════════════════════════════════════════════════════════════════════════
class AddPasswordModal(ModalScreen):
    DEFAULT_CSS = """
    AddPasswordModal { align: center middle; }
    #dialog {
        background: $surface; border: heavy $primary;
        padding: 2 4; width: 68; height: auto;
    }
    #dialog Label   { margin-bottom: 1; }
    #dialog Input   { margin-bottom: 1; }
    #tabs-row       { layout: horizontal; height: 3; margin-bottom: 1; }
    #tab-gen        { width: 1fr; }
    #tab-own        { width: 1fr; }
    #strength-lbl   { margin: 1 0; }
    #breach-lbl     { margin-bottom: 1; }
    #gen-result     { margin: 1 0; }
    #btn-row        { layout: horizontal; height: 3; }
    #btn-row Button { width: 1fr; margin: 0 1; }
    #err            { color: $error; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("-- ADD PASSWORD --  Pick your poison below:")
            with Horizontal(id="tabs-row"):
                yield Button("Generate one for me",      id="tab-gen", variant="primary")
                yield Button("I'll type my own (brave)", id="tab-own", variant="default")

            yield Input(placeholder="What hellsite is this password for?", id="title")

            with Vertical(id="pane-gen"):
                yield Input(placeholder="Length? (default 16, the coward's choice)", id="length")
                yield Label("", id="gen-result")
                yield Button("Roll the dice", id="do-gen", variant="success")

            with Vertical(id="pane-own"):
                yield Input(placeholder="Type your password, hero", password=True, id="own-pw")
                yield Button("Analyse it", id="do-analyse", variant="warning")
                yield Label("", id="breach-lbl")
                yield Label("", id="strength-lbl")

            yield Label("", id="err")
            with Horizontal(id="btn-row"):
                yield Button("Save it already", id="save",   variant="primary", disabled=True)
                yield Button("Never mind",       id="cancel", variant="default")

        self._value = ""
        self._mode  = "gen"

    def on_mount(self):
        self._show_mode("gen")

    def _show_mode(self, mode: str):
        self._mode = mode
        self.query_one("#pane-gen").display = (mode == "gen")
        self.query_one("#pane-own").display = (mode == "own")
        self.query_one("#tab-gen", Button).variant = "primary" if mode == "gen" else "default"
        self.query_one("#tab-own", Button).variant = "default" if mode == "gen" else "primary"
        self.query_one("#save", Button).disabled = True
        self._value = ""

    @on(Button.Pressed, "#tab-gen")
    def switch_gen(self): self._show_mode("gen")

    @on(Button.Pressed, "#tab-own")
    def switch_own(self): self._show_mode("own")

    @on(Button.Pressed, "#do-gen")
    def do_generate(self):
        raw    = self.query_one("#length", Input).value.strip()
        length = int(raw) if raw.isdigit() else 16
        chars  = string.ascii_letters + string.digits + string.punctuation
        self._value = ''.join(secrets.choice(chars) for _ in range(length))
        from rich.markup import escape
        self.query_one("#gen-result", Label).update(
            f"Here you go: [bold]{escape(self._value)}[/bold]\n"
            "(You will forget this in 4 seconds. That is literally my whole reason to exist.)"
        )
        self.query_one("#save", Button).disabled = False

    @on(Button.Pressed, "#do-analyse")
    def do_analyse(self):
        pw = self.query_one("#own-pw", Input).value
        if not pw:
            return
        self._value = pw
        h = hashlib.sha1(pw.encode()).hexdigest().upper()
        try:
            resp  = requests.get(f"https://api.pwnedpasswords.com/range/{h[:5]}", timeout=5)
            found = next(
                (ln.split(":")[1] for ln in resp.text.splitlines() if ln.split(":")[0] == h[5:]),
                None
            )
            b_txt = (
                f"[red]Found in breaches {found} times. Bold choice.[/red]"
                if found else
                "[green]Not in any known breach. Congrats, you are original.[/green]"
            )
        except Exception:
            b_txt = "[dim]Could not reach breach API. Living dangerously, are we.[/dim]"

        self.query_one("#breach-lbl",   Label).update(b_txt)
        bits, label, color = _password_strength(pw)
        self.query_one("#strength-lbl", Label).update(
            f"[{color}]{bits:.1f} bits -- {label}[/{color}]"
        )
        self.query_one("#save", Button).disabled = False

    @on(Button.Pressed, "#save")
    def do_save(self):
        title = self.query_one("#title", Input).value.strip()
        if not title:
            self.query_one("#err", Label).update("A password without a title is just vibes.")
            return
        if not self._value:
            self.query_one("#err", Label).update("Generate or type a password first, champ.")
            return
        enc = self.app.cipher.encrypt(self._value.encode()).decode()
        pws = _load_passwords()
        pws[title] = enc
        _save_passwords(pws)
        self.dismiss("saved")

    @on(Button.Pressed, "#cancel")
    def do_cancel(self): self.dismiss(None)


# ══════════════════════════════════════════════════════════════════════════════
# MODAL: Add custom data
# ══════════════════════════════════════════════════════════════════════════════
class AddCustomModal(ModalScreen):
    DEFAULT_CSS = """
    AddCustomModal { align: center middle; }
    #dialog {
        background: $surface; border: heavy $primary;
        padding: 2 4; width: 68; height: auto;
    }
    #dialog Label    { margin-bottom: 1; }
    #dialog Input    { margin-bottom: 1; }
    #dialog TextArea { height: 8; margin-bottom: 1; }
    #btn-row         { layout: horizontal; height: 3; }
    #btn-row Button  { width: 1fr; margin: 0 1; }
    #err { color: $error; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("-- STASH CUSTOM DATA --")
            yield Label("Anything goes. Passwords, secrets, grocery lists, existential dread.")
            yield Input(placeholder="Title (keep it clean, no spaces)", id="title")
            yield TextArea(id="data")
            yield Label("", id="err")
            with Horizontal(id="btn-row"):
                yield Button("Encrypt and hide it", id="save",   variant="primary")
                yield Button("Actually, no",         id="cancel", variant="default")

    @on(Button.Pressed, "#save")
    def do_save(self):
        title = self.query_one("#title", Input).value.strip()
        data  = self.query_one("#data",  TextArea).text
        if not title:
            self.query_one("#err", Label).update("Title? You need a title. Come on.")
            return
        fpath = os.path.join(CUSTOM_DIR, title + ".enc")
        if os.path.exists(fpath):
            self.query_one("#err", Label).update(
                "That title already exists. Originality is free, use it."
            )
            return
        enc = self.app.cipher.encrypt(data.encode())
        with open(fpath, "wb") as f:
            f.write(enc)
        self.dismiss("saved")

    @on(Button.Pressed, "#cancel")
    def do_cancel(self): self.dismiss(None)


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN: Setup master password (first run)
# ══════════════════════════════════════════════════════════════════════════════
class SetupScreen(Screen):
    DEFAULT_CSS = """
    SetupScreen { align: center middle; }
    #box {
        width: 62; height: auto;
        background: $surface; border: heavy $primary; padding: 2 4;
    }
    #box Label  { margin-bottom: 1; }
    #box Input  { margin-bottom: 1; }
    #box Button { width: 100%; }
    #err { color: $error; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Label("RONIN PASSWORD MANAGER -- FIRST TIME SETUP")
            yield Label("Welcome. You have no passwords and no data. Blank slate. Beautiful.")
            yield Label("Pick a master password. Forget it and your vault becomes modern art.")
            yield Input(placeholder="Master password",                  password=True, id="pw1")
            yield Input(placeholder="Confirm it (yes, again, I know)", password=True, id="pw2")
            yield Label("", id="err")
            yield Button("Forge the key and begin", variant="primary", id="set")

    @on(Button.Pressed, "#set")
    def do_set(self):
        pw1 = self.query_one("#pw1", Input).value
        pw2 = self.query_one("#pw2", Input).value
        if not pw1:
            self.query_one("#err", Label).update("Empty password. Very mysterious. Also completely useless.")
            return
        if pw1 != pw2:
            self.query_one("#err", Label).update("These do not match. You had ONE job.")
            return
        _save_master(pw1)
        self.app.push_screen(MsgModal(
            "Master password set.\n"
            "Restart the program and log in.\n"
            "And please, for the love of all things holy, remember it."
        ))
        self.app.exit()


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN: Login
# ══════════════════════════════════════════════════════════════════════════════
class LoginScreen(Screen):
    DEFAULT_CSS = """
    LoginScreen { align: center middle; }
    #box {
        width: 62; height: auto;
        background: $surface; border: heavy $primary; padding: 2 4;
    }
    #box Label  { margin-bottom: 1; }
    #box Input  { margin-bottom: 1; }
    #box Button { width: 100%; }
    #tagline { color: $text-muted; }
    #err     { color: $error; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Label("RONIN PASSWORD MANAGER")
            yield Label("Your secrets are in here. They are judging you.", id="tagline")
            yield Input(
                placeholder="Master password (the one you definitely remembered)",
                password=True, id="pw"
            )
            yield Label("", id="err")
            yield Button("Let me in", variant="primary", id="login")

    @on(Input.Submitted, "#pw")
    def on_enter(self, _): self._attempt()

    @on(Button.Pressed, "#login")
    def do_login(self): self._attempt()

    def _attempt(self):
        pw = self.query_one("#pw", Input).value
        ok, salt = _check_password(pw)
        if ok:
            self.app.cipher = _make_cipher(pw, salt)
            self.app.switch_screen(DashScreen())
        else:
            self.query_one("#err", Label).update(
                "Wrong. Try again. Or cry. Both are valid responses."
            )


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN: Main dashboard -- two-panel layout
# ══════════════════════════════════════════════════════════════════════════════
class DashScreen(Screen):
    DEFAULT_CSS = """
    DashScreen { layout: vertical; }

    #top-bar {
        height: 3;
        background: $primary;
        layout: horizontal;
        padding: 0 2;
    }
    #app-title {
        width: 1fr;
        content-align: left middle;
        color: $background;
        text-style: bold;
    }
    #quit-btn { width: auto; min-width: 18; }

    #panels { layout: horizontal; height: 1fr; }

    /* ── LEFT: Passwords ── */
    #pw-panel {
        width: 1fr;
        border-right: heavy $primary;
        layout: vertical;
    }
    #pw-header {
        height: 3;
        background: $boost;
        layout: horizontal;
        padding: 0 1;
        border-bottom: solid $primary;
    }
    #pw-header-label {
        width: 1fr;
        content-align: left middle;
        text-style: bold;
    }
    #add-pw-btn { width: auto; min-width: 20; height: 3; }
    #pw-scroll  { height: 1fr; }
    #pw-inner   { padding: 1; }
    DataTable   { height: auto; }
    #pw-empty   { margin: 1; color: $text-muted; }

    /* ── RIGHT: Custom Data ── */
    #cd-panel {
        width: 1fr;
        layout: vertical;
    }
    #cd-header {
        height: 3;
        background: $boost;
        layout: horizontal;
        padding: 0 1;
        border-bottom: solid $primary;
    }
    #cd-header-label {
        width: 1fr;
        content-align: left middle;
        text-style: bold;
    }
    #add-cd-btn { width: auto; min-width: 20; height: 3; }
    #cd-scroll  { height: 1fr; }
    #cd-inner   { padding: 1; }
    #cd-empty   { margin: 1; color: $text-muted; }
    .cd-entry   { border: solid $boost; padding: 1; margin-bottom: 1; }
    .cd-title   { text-style: bold; color: $primary; }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="top-bar"):
            yield Label(
                "RONIN PASSWORD MANAGER  |  You're in. Try not to break anything.",
                id="app-title"
            )
            yield Button("Log out & flee", id="quit-btn", variant="error")

        with Horizontal(id="panels"):

            # LEFT panel
            with Vertical(id="pw-panel"):
                with Horizontal(id="pw-header"):
                    yield Label("PASSWORDS", id="pw-header-label")
                    yield Button("+ Add password", id="add-pw-btn", variant="primary")
                with ScrollableContainer(id="pw-scroll"):
                    with Container(id="pw-inner"):
                        yield DataTable(id="pw-table")
                        yield Label(
                            "No passwords yet.\n"
                            "Either you have great memory or zero accounts.\n"
                            "Respect either way.",
                            id="pw-empty"
                        )

            # RIGHT panel
            with Vertical(id="cd-panel"):
                with Horizontal(id="cd-header"):
                    yield Label("CUSTOM DATA", id="cd-header-label")
                    yield Button("+ Add custom data", id="add-cd-btn", variant="primary")
                with ScrollableContainer(id="cd-scroll"):
                    with Vertical(id="cd-inner"):
                        yield Label(
                            "No custom data yet.\n"
                            "Your secrets are safe.\n"
                            "(Because they do not exist.)",
                            id="cd-empty"
                        )

        yield Footer()

    def on_mount(self):
        self._refresh_passwords()
        self._refresh_custom()

    # ── passwords ──────────────────────────────────────────────────────────────
    def _refresh_passwords(self):
        table = self.query_one("#pw-table", DataTable)
        table.clear(columns=True)
        pws = _load_passwords()

        if not pws:
            table.display = False
            self.query_one("#pw-empty", Label).display = True
            return

        self.query_one("#pw-empty", Label).display = False
        table.display = True
        table.add_columns("Site / Title", "Password")
        for title, enc in pws.items():
            dec = self.app.cipher.decrypt(enc.encode()).decode()
            table.add_row(title, dec)

    # ── custom data ────────────────────────────────────────────────────────────
    def _refresh_custom(self):
        inner = self.query_one("#cd-inner", Vertical)
        for child in list(inner.children):
            if child.id != "cd-empty":
                child.remove()

        files = sorted(f for f in os.listdir(CUSTOM_DIR) if f.endswith(".enc"))

        if not files:
            self.query_one("#cd-empty", Label).display = True
            return

        self.query_one("#cd-empty", Label).display = False
        for fname in files:
            title = os.path.splitext(fname)[0]
            with open(os.path.join(CUSTOM_DIR, fname), "rb") as f:
                raw = f.read()
            body  = self.app.cipher.decrypt(raw).decode()
            entry = Vertical(
                Label(title, classes="cd-title"),
                Label(body,  classes="cd-body"),
                classes="cd-entry"
            )
            inner.mount(entry)

    # ── handlers ───────────────────────────────────────────────────────────────
    @on(Button.Pressed, "#add-pw-btn")
    def open_add_pw(self):
        def refresh(result):
            if result == "saved":
                self._refresh_passwords()
                self.app.push_screen(
                    MsgModal("Saved. You are now 1% more secure than you were 30 seconds ago.")
                )
        self.app.push_screen(AddPasswordModal(), refresh)

    @on(Button.Pressed, "#add-cd-btn")
    def open_add_cd(self):
        def refresh(result):
            if result == "saved":
                self._refresh_custom()
                self.app.push_screen(
                    MsgModal("Encrypted and stashed. Sleep tight. Your secrets are safe-ish.")
                )
        self.app.push_screen(AddCustomModal(), refresh)

    @on(Button.Pressed, "#quit-btn")
    def do_quit(self): self.app.exit()


# ══════════════════════════════════════════════════════════════════════════════
# APP
# ══════════════════════════════════════════════════════════════════════════════
class RoninApp(App):
    TITLE   = "RONIN"
    BINDINGS = [Binding("ctrl+q", "quit", "Quit")]

    def __init__(self):
        super().__init__()
        self.cipher = None

    def on_mount(self):
        if os.path.exists(MASTER_FILE):
            self.push_screen(LoginScreen())
        else:
            self.push_screen(SetupScreen())


if __name__ == "__main__":
    RoninApp().run()
