# Security notes (what this skill does and does NOT guarantee)

This skill controls **what executes and what it produces**. It does **not** and
**cannot** guarantee containment. That is the harness's job (see HARNESS_SPEC).

What the skill does for safety:
- Defaults to **PNG** — no JavaScript in the artifact, so nothing to inject.
- Reads data as **JSON** and never string-concatenates data values into markup.
- The HTML variant only embeds a base64 image; it adds no scripts.

What the skill explicitly relies on the harness to enforce (do not duplicate
here, and never assume a SKILL.md instruction is a security boundary):
- Sandbox provisioned with **no network egress** and **no production
  credentials**.
- Sandbox **region/project** pinned to satisfy data-residency policy.
- Any HTML output displayed inside a **sandboxed iframe** (`allow-scripts`
  only; NOT `allow-same-origin`) with a **no-egress CSP**.

Test for any new rule: "if a malicious or buggy skill were loaded, would this
still protect me?" If no, it must live in the harness, not in a skill.
