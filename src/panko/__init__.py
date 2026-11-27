"""Panko: language-learning sources in, verified Anki cards out."""

# How Panko names itself to the sites it reads. Wikimedia refuses a vague name from a server (403, "robot policy"):
# it wants a way to reach the tool's authors, so the name carries the project's address.
SOURCE = "https://github.com/NotAHill/panko"
USER_AGENT = f"panko ({SOURCE})"
# How a person installs Panko on their own computer (the install page, docs/ROADMAP.md track D). From GitHub until
# Panko is on PyPI under a name of its own ("panko" there is another project).
INSTALL = f"uv tool install git+{SOURCE}"
UPGRADE = "uv tool upgrade panko"
