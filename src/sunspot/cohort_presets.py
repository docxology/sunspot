"""
Built-in login lists for :func:`sunspot.cohort.run_cohort_report` and the
``cohort`` CLI. Curated public GitHub usernames. Invalid or empty accounts
fail at fetch time; trim locally as needed.
"""

# Previous sunspot single-user / compare panel
SUNSPOT_PANEL: tuple[str, ...] = (
    "4dsolutions",
    "AiwonA1",
    "antirez",
    "docxology",
    "gvanrossum",
    "karpathy",
)

# Active-inference--adjacent (PyMDP, variational, neural active inference)
ACTIVE_INFERENCE: tuple[str, ...] = (
    "conorheins",
    "BerenMillidge",
    "alec-tschantz",
)

# Extra high-signal OSS (optional bundles)
FAMOUS_OSS: tuple[str, ...] = (
    "soumith",
    "fchollet",
    "bordaigorl",
)

# ``--preset full``: panel + AI + a few extras (de-duplicated order-preserving)
BUILTIN: tuple[str, ...] = tuple(
    dict.fromkeys([*SUNSPOT_PANEL, *ACTIVE_INFERENCE, *FAMOUS_OSS]),
)


def expand_preset(name: str) -> tuple[str, ...]:
    """
    Return a login tuple for a named bundle.

    * ``panel`` / ``sunspot`` — the six logins from earlier sunspot runs
    * ``ai`` / ``aif`` / ``active`` — active-inference--adjacent
    * ``famous`` / ``oss`` — FAMOUS_OSS
    * ``wide`` — union of all three
    * ``full`` / ``default`` / ``all`` / ``builtin`` — BUILTIN
    """
    k = (name or "").strip().lower()
    if k in ("panel", "sunspot"):
        return SUNSPOT_PANEL
    if k in ("ai", "aif", "active", "active-inference", "eai"):
        return ACTIVE_INFERENCE
    if k in ("famous", "oss", "famous-oss"):
        return FAMOUS_OSS
    if k in ("wide", "union"):
        return tuple(
            {u: None for u in [*SUNSPOT_PANEL, *ACTIVE_INFERENCE, *FAMOUS_OSS]}
        )
    if k in ("full", "builtin", "default", "all", "list", ""):
        return BUILTIN
    raise KeyError(
        f"unknown cohort preset {name!r} (use: panel, ai, famous, wide, full)",
    )
