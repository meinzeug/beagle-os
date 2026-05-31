# Projectleader

This directory is the project-lead memory for Beagle OS. It exists so every
agent run starts from the same operational state instead of rediscovering recent
decisions, live-host status and immediate risks.

Read order for every run:

1. `projectleader/state.md` - current memory, live status, recent fixes.
2. `projectleader/todo.md` - prioritized execution queue.
3. `docs/lasthope/README.md`, `docs/lasthope/02-execution-order.md`,
   `docs/lasthope/05-diamond-plan.md` - canonical product gates.
4. The specific files touched by the current task.

Rules:

- Keep this directory free of secrets, passwords, tokens and private keys.
- Record live hotfixes only after they are reproducible in the repo.
- Update `state.md` after meaningful runtime/release changes.
- Update `todo.md` at the end of a run so the next agent can continue directly.
- Do not let this replace the canonical `docs/lasthope/` and `docs/refactor/`
  documents; use it as the fast handoff layer.
