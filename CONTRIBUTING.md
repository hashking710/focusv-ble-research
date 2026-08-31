← [Back to README](README.md)

# Contributing

This is a living reference, not a finished document — corrections, live-capture confirmations,
and progress on anything in [`docs/open-questions.md`](docs/open-questions.md) are genuinely
welcome, not just tolerated.

## What's useful

- **A live capture** that confirms, corrects, or contradicts something documented here.
- **A decompiled function** (Ghidra output, with the address) that resolves one of the open
  items.
- **A cross-reference in the app's own source** (a line number in the official app's JS bundle)
  that confirms a byte's meaning.
- **Hardware you have that this project doesn't** — see the [README's Roadmap](README.md#roadmap)
  for what's specifically being looked for (a BLE sniffer, a logic analyzer). If you already have
  either and want to collaborate rather than wait for this project to acquire one, open a
  Discussion or an Issue and say so.

Vague "I think X" without something backing it up is fine as a Discussion topic, but probably not
a PR to the docs yet — the existing docs deliberately avoid stating anything as confirmed unless
it actually is (see [Open Questions](docs/open-questions.md) for what's explicitly still a
theory).

## How to contribute a finding

1. Open an issue first if you're not sure where a finding belongs, or if it contradicts something
   already documented — worth discussing before a PR, since a correction usually needs the
   surrounding text updated too, not just the one fact.
2. For a straightforward addition/correction, a PR is fine directly. Cite your evidence in the PR
   description the same way the docs cite theirs (an address, a line number, what you observed
   and how).
3. Keep the docs' existing tone: confirmed facts stated plainly, anything uncertain flagged as
   such. Don't upgrade a "likely" to a certainty without something that actually proves it.

## Looking for something to work on?

Check [`docs/open-questions.md`](docs/open-questions.md) — it's a live punch list, not a wishlist.
Items tagged 📡 or 🔬 there are specifically waiting on hardware (see the
[Roadmap](README.md#roadmap)); everything else is fair game for pure software/analysis work right
now. Issues labeled `help wanted` on the repo's Issues tab track the same list in GitHub's own
searchable format.

## Code of conduct

No formal document for a repo this size — the expectation is the same as anywhere else: be
straightforward about what you know versus what you're guessing, credit sources, and keep
disagreements about the actual evidence, not the person presenting it.
