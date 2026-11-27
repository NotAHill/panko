"""Panko: language-learning sources in, verified Anki cards out."""

# How Panko names itself to the sites it reads. Wikimedia refuses a vague name from a server (403, "robot policy"):
# it wants a way to reach the tool's authors, so the name carries the project's address.
SOURCE = "https://github.com/NotAHill/panko"
USER_AGENT = f"panko ({SOURCE})"
# Panko's name on PyPI ("panko" there is another project); the command and the module stay `panko`.
DIST = "pankohub"
# How a person installs Panko on their own computer (the install page, docs/ROADMAP.md track D): from GitHub until
# the first release is on PyPI, then `uv tool install pankohub`.
INSTALL = f"uv tool install git+{SOURCE}"
UPGRADE = f"uv tool upgrade {DIST}"


def version() -> str:
    """This Panko's version, or "" when it isn't installed as a package."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as v
    try:
        return v(DIST)
    except PackageNotFoundError:
        return ""
