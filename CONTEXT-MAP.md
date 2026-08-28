# Context Map — The Ninth Room

Two repos, two contexts, one domain. The engine owns the domain; the Studio
is a view over it and writes nothing to disk itself.

## Contexts

- **[Engine](./CONTEXT.md)** (`~/Projects/the-ninth-room`) — the Python
  pipeline. Owns footage, transcription, story, the cut, baking, Resolve,
  and every file under `work/<slug>/`.
- **[Studio](../the-ninth-room-studio/CONTEXT.md)**
  (`~/Projects/the-ninth-room-studio`) — the Next.js app. Renders engine
  state and posts back. Every write is an engine POST.

## Relationships

- **Studio → Engine**: all I/O through `src/lib/engine.ts`. One documented
  exception — uploads use `XMLHttpRequest` direct to `:8765`, because the
  Next proxy cannot report upload progress.
- **Engine → Studio**: the engine is authoritative on whether an action can
  run. The Studio renders that readiness; it never derives it.

## The vocabularies differ on purpose

The Studio's labels are the **outsider vocabulary**. Hrefs, JSON keys and
engine terms did not change when the labels did, so links, tests and muscle
memory survived. The translation is deliberate and is recorded in the
Studio's `CONTEXT.md`. The most load-bearing pair:

| Engine | Studio |
|---|---|
| takes | Library |
| edit plan | the cut |
| deliver | Export |

A term that means the *same* thing in both is defined in the engine's
`CONTEXT.md` and not repeated.

## Decisions

Decisions live in the engine's `docs/` as `decisions-<topic>.md`, including
decisions that span both repos — the engine owns the domain, so it owns the
record. The format predates this map (`decisions-agent-topology.md`,
2026-08-24) and is deliberately not the numbered `docs/adr/` convention:
it leads with the decision as a sentence and shows alternatives as measured
columns, which is better than the template it would have been renamed into.
