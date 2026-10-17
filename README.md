# n8n error-handling study: analysis scripts

The code behind [n8n Error Handling: Five Signals in Public Workflow Files](https://noderecipe.com/n8n-error-handling-data),
so the grouping and the signal counts can be checked by someone other than me.

Source corpus: [`Zie619/n8n-workflows`](https://github.com/Zie619/n8n-workflows) at commit
`94007c1445d9258a7da116646b79473e7c7c3282`. That is still the head of `main` (last push 24 June 2026);
check with `git ls-remote https://github.com/Zie619/n8n-workflows.git main` before you compare numbers.

There are three folders, from oldest to newest:

| folder | written | what it is |
|---|---|---|
| [`scripts/2026-09-12/`](scripts/2026-09-12) | 12–13 Sep 2026 | the scripts that produced the published counts, unedited |
| [`reproduce/`](reproduce) | 29 Sep 2026 | an independent rewrite from the documented method, checked against the live CSV |
| [`rewrite-check/`](rewrite-check) | 17 Oct 2026 | a corpus-wide test of whether the measured fields survived the upstream rewrites |

Everything reads JSON and nothing executes a workflow.

## 1. The scripts behind the published counts

The tag [`published-counts-2026-09`](https://github.com/noderecipe52/n8n-error-handling-data/tree/published-counts-2026-09) points at the commit that adds
them. They are byte-identical to the files I ran, and `.gitattributes` keeps Git from changing line
endings on checkout, so these hashes should match on any OS:

```
ede55b0af379fbaa744aacc063c3ea664efbdfb5ec4f1a3fe57899f896250d74  dedupe2.py
25aeeac3f913880205770ef1b41ecd75532b819018239c065189327e2b1a35a0  analyze2.py
66f3033eb5d71f9359501e942c65c5d9542f0348af690a4eefaec3f02ca9168a  sheets.py
dcd240baf3d3ae26817d972fa02ed0714f48b3c77e0dd1e828afe50de50d7266  cross.py
86696fb7ef091ff39473e10badee417ce4e88b203ac0eee9fe6d73b91624b1f7  fab.py
b507c550ec527b3a890f0696f307ef2ebd3313bf05b2c92303bedec0d8841b48  verify200.py
7987444fe77dc23c05cb674ae77d11977423944e100ffc0f5948ba0c7a2d7e70  risk.py
2752189c06497710f2654ca68f25ddeb090114a07e8baa31bc889676b67a8a38  provenance-check.py
```

They are short and were written for one run, so they expect to sit next to a clone called `corpus`:

```bash
git clone https://github.com/Zie619/n8n-workflows.git corpus
git -C corpus checkout 94007c1445d9258a7da116646b79473e7c7c3282
cp scripts/2026-09-12/*.py .
python dedupe2.py      # 2,061 files -> 2,030 groups; writes groups.json (one list of files per group)
python analyze2.py     # the eight error-handling rows, over the first file of each group
python sheets.py       # Google Sheets operations, Append or Update nodes, matching columns
python cross.py        # the 53 Append-or-Update workflows and their trigger subgroup
python fab.py          # the broken connections (matches issue #200)
python verify200.py    # scoped AI node types rewritten to noOp (also #200)
python risk.py         # no node named like an Error Trigger or Google Sheets node was mistyped
```

`provenance-check.py` reads one workflow at four upstream commits through the GitHub API and needs
`gh auth login`. `rewrite-check/` below replaces it with a check of every file.

Which script gives which row of the [published CSV](https://noderecipe.com/data/n8n-error-handling-2026-09.csv):

| CSV rows | script |
|---|---|
| `corpus_files`, `corpus_unique_workflows`, `corpus_duplicate_groups`, `corpus_redundant_copies` | `dedupe2.py` |
| the eight error-handling rows (`no_error_handling_field_of_any_kind` … `contains_error_trigger`) | `analyze2.py` |
| `google_sheets_*`, `sheets_op_*`, `append_or_update_*` | `sheets.py` |
| `upsert_wf_*` | `cross.py` |
| `nodes_per_workflow_*`, `node_type_*`, `trigger_*` | one-off commands that I did not keep; `reproduce/` re-derives the three size rows |

Metric names in the CSV are historical. The JSON next to it has the definitions and the two
corrections (29 Sep and 3 Oct 2026). The counts themselves have never changed.

## 2. Independent reproduction

`reproduce/reproduce-corpus.py` re-implements the documented grouping rule and signal definitions
from scratch, downloads the pinned archive from GitHub, recomputes 27 of the 47 CSV rows and compares
them with the CSV that is live on the site. All 27 match, on 29 September and again on 17 October 2026.
`corpus-validation.json` holds the result with the SHA-256 of the archive and of the CSV it compared
against.

```bash
cd reproduce && python reproduce-corpus.py
```

## 3. Did the measured fields survive the upstream rewrites?

The corpus was rewritten upstream twice: PR #106 on 29 September 2025 (commits `f293c236`,
`74bdcdca`, `3c0a92c4`) and the cleanup in `5ffee225` on 3 November 2025. Between them they changed
node types, connections, `settings`, `meta`, and added and removed nodes. Issue
[#200](https://github.com/Zie619/n8n-workflows/issues/200) documents the damage.

`rewrite-check/rewrite-check.py` compares every file at `f8639776` (main on 28 September 2025, the
day before the rewrites landed) with the pinned commit, matching files by path and nodes by name.
It also steps through each of the four rewrite commits against its parent. It needs a full clone:

```bash
git clone https://github.com/Zie619/n8n-workflows.git corpus-full
cd rewrite-check && python rewrite-check.py ../corpus-full
```

What it found (`rewrite-check.json` has every number):

- 2,057 of the 2,061 pinned files existed before the rewrites. The other four reached main in November 2025
  and never went through them.
- 29,363 nodes appear under the same name before and after. On every one of them `retryOnFail`,
  `onError`, `continueOnFail`, `maxTries`, `waitBetweenTries`, the Error Trigger type, the Google
  Sheets type and the Sheets operation are unchanged.
- Two values did change: on two Google Sheets **update** nodes a credential scrub replaced the v1
  `key` parameter `ID` with `YOUR_CREDENTIAL_HERE`. Neither is an Append-or-Update node, so no
  published figure reads them.
- 161 node names disappear. Each one comes back in the same file under a new name with the same type
  and identical parameters (`X` became `Twitter`, for example), so these are renames.
- The rewrites left 1,223 nodes behind in 1,124 files: 1,066 Stop and Error, 154 Manual Trigger and
  three others. One of them carries a measured field (a duplicated Google Sheets read node).
- At the workflow level, none of the 2,057 files changes on any of the eight signals the published
  counts use. The same holds for each rewrite commit taken on its own.

## Limits worth carrying with any number

**The grouping is not rewrite-proof, even though the fields are.** The fingerprint includes node
names and connections, and the rewrites changed both. Run on the pre-rewrite tree, the same rule
gives 1,974 groups from 2,057 files instead of 2,030 from 2,061, because injected nodes make some
former duplicates look different. The headline moves from 1,670 of 1,974 (84.6%) to the published
1,721 of 2,030 (84.8%). Error Triggers are 18 either way.

**The node-type and size rows include rewrite artifacts.** Across the 2,030 representatives,
1,035 of the 1,072 Stop and Error nodes and 142 of the 906 Manual Trigger nodes were injected, and
3,977 of the 4,363 noOp nodes had a different type before the rewrites. Before the rewrites the median
workflow had 11 nodes (8 without sticky notes) and the mean was 14.5; the published 12, 9 and 15.1
include the injected nodes. The maximum, 246, is the same.

**What the counts describe.** Five configuration signals in one public collection of workflow
files. Not production failure rates, and not whether any workflow handles errors correctly.

## Licence

Code: MIT ([LICENSE](LICENSE)). The study text and data on noderecipe.com: CC BY 4.0.
