---
name: python-runner
description: Solve the user's task by writing Python; the harness runs it in an isolated sandbox and returns stdout.
---

# python-runner

When the user asks for a computation or transformation:

1. Write a short, self-contained Python script that prints its result to stdout.
2. Call the `run_code` tool with that script as `code`.
3. Report the stdout back to the user as the answer.

Constraints (the sandbox enforces these structurally):
- No network access. Standard library only unless the runtime image provides a package.
- The script must `print()` its text result — stdout is returned.
- Files you write to the working directory are returned to the user as attachments; for
  binary results (images, etc.) write a file rather than printing bytes.
- Uploaded files are available by name (e.g. `open("data.csv")`). Never hardcode or reconstruct
  a file's contents from memory — if a file you need isn't in the working directory, ask the user
  to attach it rather than inventing the data.
- If run_code returns an error, read it, fix the script, and call run_code again.
- Keep scripts short and deterministic.

