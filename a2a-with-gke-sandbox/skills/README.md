# Skills

Skills are loaded with ADK's **`SkillToolset`** using **progressive disclosure**: only each
skill's name + description are in the prompt up front; the model fetches the full `SKILL.md` at
runtime via `load_skill` when it decides the skill is relevant. Every directory under `skills/` is
auto-registered — no code change to add one.

Shipped skills:

| Skill | Purpose |
|---|---|
| `python-runner/` | Generic: run model-written Python in the sandbox; write files for binary output. |
| `data-analysis/` | Analyze an uploaded CSV/Excel with pandas and return a **chart** (rendered inline in Gemini Enterprise via A2UI) or a report attachment. |

## Authoring a new skill

1. Create `skills/<name>/SKILL.md` with YAML frontmatter — `name` and `description` are what the
   model sees up front, so make the description a crisp "use this when…":

   ```markdown
   ---
   name: my-skill
   description: Use this when the user wants <X> — produces <Y>.
   ---

   # my-skill
   Steps the model should follow… (it `run_code`s Python in the sandbox).
   ```

2. That's it — it's picked up automatically. Keep instructions concrete and remember the sandbox
   constraints: no network, shell-less, write output files rather than printing bytes.

The chart-rendering contract (how to emit an A2UI surface so the image shows in Gemini Enterprise)
lives in `data-analysis/SKILL.md`; copy that pattern for any skill that produces a chart.
