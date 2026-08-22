"""File-pattern classification of PR changesets for qa_gate_mode
``merge-restricted-classes``.

See ``docs/superpowers/specs/2026-08-22-qa-merge-restricted-classes-design.md``
section 3.
"""

import fnmatch


_DOCS_ONLY_EXCLUDE = ("project-docs/.synlynk_config.json",)


def is_docs_only_change(changed_files: list) -> bool:
    """Return whether every changed file is documentation and the list is non-empty.

    Documentation files match ``docs/**``, ``*.md`` at any path, or
    ``project-docs/**``, except for ``project-docs/.synlynk_config.json``.
    Any non-documentation file disqualifies the whole changeset.
    """
    if not changed_files:
        return False

    for path in changed_files:
        if path in _DOCS_ONLY_EXCLUDE:
            return False
        if fnmatch.fnmatch(path, "docs/*") or fnmatch.fnmatch(path, "docs/**/*"):
            continue
        if fnmatch.fnmatch(path, "*.md") or fnmatch.fnmatch(path, "**/*.md"):
            continue
        if fnmatch.fnmatch(path, "project-docs/*") or fnmatch.fnmatch(path, "project-docs/**/*"):
            continue
        return False

    return True
