# SIL Loop R

**[Português](README.md) · [English](README.en.md) · [Español](README.es.md)**

A local framework for turning occurrences into lessons you can review: record evidence, propose improvements, decide in batches, and track whether rules remain valid.

[Usage guide](https://inematds.github.io/sil-loop-r/guia/en/) · [Architecture and decisions (in Portuguese)](docs/architecture.md) · [Skill (in Portuguese)](skills/sil-loop-r/SKILL.md)

## What is implemented

- Python CLI with no external dependencies or API calls.
- Occurrences, proposals, time-limited experiments, and permanent rules requiring an explicit decision.
- Approval requests triggered by days, releases, or the number of proposals.
- Review triggered by age, missing citations, and changes to associated files.
- Promotion of binding rules into a delimited block in AGENTS.md (or another instruction file), watched by `check`; protection rung and known leak per rule (v1.1).
- Decision and evidence history, transactional SQLite storage, and JSON export.
- Skill and templates distributed in the repository, without automatic installation.

## Get started

Requires Python 3.10 or later and Git to clone. No server, account, or key is required.

```bash
git clone https://github.com/inematds/sil-loop-r.git
cd sil-loop-r
python3 sil.py --help
python3 scripts/demo.py
python3 -m unittest discover -s tests -v
```

The demo uses a temporary directory and clearly labeled fictional decisions. It does not install or configure the framework in your projects.

To track a project of your choice:

```bash
python3 sil.py --project /caminho/do/projeto init
python3 sil.py --project /caminho/do/projeto occurrence \
  --title "Test accessed the wrong service" \
  --evidence "Local log: the port was already in use" \
  --cause "Server started without checking the port"
python3 sil.py --project /caminho/do/projeto lesson \
  --occurrence O0001 --proposal "Abort when the port is in use" \
  --scope "Test server startup"
python3 sil.py --project /caminho/do/projeto status
```

Use the IDs returned by the CLI; O0001 and L0001 are the first IDs in an empty project. Add `--watch caminho/relativo` when creating a lesson to monitor existing files. The framework detects content changes; it does not automatically judge their meaning.

## Approval and frequency

Default: request a decision after **7 days, 2 releases, or 5 new proposals**, whichever comes first. `request` prepares the batch and records the reminder; the agent presents the question to the user. There are no background notifications or outgoing messages.

```bash
python3 sil.py --project /caminho/do/projeto config \
  --approval-days 7 --approval-releases 2 --approval-batch 5 \
  --review-days 30 --uncited-releases 5
python3 sil.py --project /caminho/do/projeto request
```

Only after explicit approval for the proposal:

```bash
python3 sil.py --project /caminho/do/projeto decide L0001 adopt \
  --approved-by "Approver" --reason "Approved after reviewing the evidence"
```

Alternatives: `reject`, `defer --until YYYY-MM-DD`, or `trial --until YYYY-MM-DD --criterion "verifiable criterion"`. Dates must be in the future; an item becomes due on the specified day. An experiment remains labeled as provisional until adoption or rejection.

The name in `--approved-by` is a recorded declaration, not authentication. The skill must respect the human decision. Never approve through silence. Recording a reminder does not resolve a pending item or make `check` pass.

## Prevent outdated rules

Permanent rules are flagged for review after **30 days**, after **5 releases without a citation**, or when an associated file changes or disappears. Lack of use does not automatically retire a rule.

```bash
python3 sil.py --project /caminho/do/projeto context
python3 sil.py --project /caminho/do/projeto check
python3 sil.py --project /caminho/do/projeto review R0001 keep \
  --approved-by "Approver" --reason "Still protects a rare case; test reviewed"
```

`review` also accepts `revise --text "new rule"` and `retire`. Every decision preserves history. A review renews the date; changing the text or file fingerprints invalidates the previous verification record. Changes to `review-days` apply at the next adoption or review, without rewriting dates already recorded.

`cite` records an actual application of the rule. `verify` records positive and negative results from tests already run; it does not execute commands or certify that a report is true. See each subcommand’s help.

## How the agent participates

Read or optionally install [skills/sil-loop-r/SKILL.md (in Portuguese)](skills/sil-loop-r/SKILL.md) in your assistant. At the start, it checks `context`; during work, it records occurrences and proposes lessons; before finishing, it checks `status` and presents overdue approvals. The framework does not monitor conversations on its own or train models.

Rules do not change code, hooks, or CI. The instruction file only changes when you run `promote --write` (next section). A new rule cannot override the user’s higher-priority instructions.

## Promotion: the rule reaches the next session

A rule stored only in the database is not read by a new session. For each active rule, ask: *would breaking this rule in a session that never consults SIL cause real harm?* If yes, mark it as binding. Also record its protection rung (`prose`, `checklist`, `test`, `probe`, `hook`, `server`) and how it can be bypassed.

```bash
python3 sil.py --project /path/to/project enforce R0001 \
  --binding yes --rung hook --leak "git push --no-verify" \
  --approved-by "Owner" --reason "A wrong deploy breaks the app"
python3 sil.py --project /path/to/project promote          # shows the diff, writes nothing
python3 sil.py --project /path/to/project promote --write  # writes the block to AGENTS.md
```

The block sits between `<!-- sil-loop-r:begin … -->` and `<!-- sil-loop-r:end -->`; the rest of the file is preserved. Use `--file CLAUDE.md` (or another relative path) if you prefer; the last file written becomes the default. In Claude Code, a `CLAUDE.md` whose first line is `@AGENTS.md` loads the same block.

Once there is a binding rule, `check` returns 1 while the block is missing, outdated (rule revised, retired, or unbound) or corrupted, and when the file cannot be read. `status` lists in `prose_binding` the binding rules that still rely on text alone: candidates to climb a rung.

Optional, never installed automatically: `context --brief` prints a short summary for your agent’s session-start hook.

## Data and limits

State is stored in `.sil/state.sqlite3` inside the chosen project. This folder is private by convention and should be ignored in the consuming project’s Git repository. The `init` command does not change your `.gitignore`: check it before publishing. Store only appropriate evidence, never credentials or sensitive logs.

```bash
python3 sil.py --project /caminho/do/projeto export > historico-sil.json
```

Review the export before sharing. For a restorable backup, copy `.sil/state.sqlite3` while the CLI is stopped. JSON is an audit export; import and merging are not yet available. SQLite serializes local writes, but does not provide synchronization across machines or multiuser authentication.

`check` exit codes: **0** means no overdue items, flagged reviews, or outdated promotion; **1** requires a decision, a review, or `promote --write`; **2** indicates a storage, input, or configuration error. The CLI does not install publication blockers. Frequencies are evaluated when someone runs the commands; no daemon or scheduled task is installed.

## License

Original code and documentation are licensed under MIT. Private reference materials are not included in the distribution.
