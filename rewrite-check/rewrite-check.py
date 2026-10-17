"""rewrite-check.py: did the fields the study counts survive the upstream rewrites? Corpus-wide.

The September 2025 PR #106 (f293c236, 74bdcdca, 3c0a92c4) and the November 2025 cleanup (5ffee225)
rewrote every workflow file in Zie619/n8n-workflows. This script compares every file at the last
main commit before those rewrites (f8639776, 2025-09-28) with the commit the study pinned
(94007c14), node by node, and then steps through each rewrite commit against its parent.

It reads JSON blobs with git and executes nothing. Needs a full clone (not --depth 1):

    git clone https://github.com/Zie619/n8n-workflows.git corpus-full
    python rewrite-check.py corpus-full          # writes rewrite-check.json next to this script

Measured fields are the ones the published counts read: retryOnFail, onError, continueOnFail
(plus maxTries and waitBetweenTries for completeness), node types ending in errorTrigger,
n8n-nodes-base.googleSheets nodes with their operation and matching column.
"""
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

FIRST = '84c802cb'  # 2025-05-14 "adding the workflow collection to git"
BASE = 'f8639776'  # main on 2025-09-28, before PR #106 merged the rewrites
STEPS = ['f293c236', '74bdcdca', '3c0a92c4', '5ffee225']
PIN = '94007c1445d9258a7da116646b79473e7c7c3282'
FIELDS = ('retryOnFail', 'onError', 'continueOnFail', 'maxTries', 'waitBetweenTries')
VOLATILE = {'id', 'versionId', 'webhookId', 'position', 'createdAt', 'updatedAt',
            'meta', 'tags', 'pinData', 'active', 'instanceId'}

REPO = Path(sys.argv[1] if len(sys.argv) > 1 else 'corpus-full')


def git(*args):
    return subprocess.run(['git', '-C', str(REPO), *args], capture_output=True, check=True).stdout


def tree(commit):
    """{path: blob_sha} for every .json under workflows/ (recursive, as the study read it)."""
    out = {}
    for line in git('ls-tree', '-r', commit, '--', 'workflows/').decode().splitlines():
        meta, path = line.split('\t', 1)
        if path.endswith('.json'):
            out[path] = meta.split()[2]
    return out


_blobs = {}
_batch = None


def load(sha):
    """Parsed JSON of one blob, through a single `git cat-file --batch` process."""
    global _batch
    if sha not in _blobs:
        if _batch is None:
            _batch = subprocess.Popen(['git', '-C', str(REPO), 'cat-file', '--batch'],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        _batch.stdin.write(sha.encode() + b'\n')
        _batch.stdin.flush()
        size = int(_batch.stdout.readline().split()[2])
        body = _batch.stdout.read(size)
        _batch.stdout.read(1)  # trailing newline
        _blobs[sha] = json.loads(body)
    return _blobs[sha]


def nodes_of(data):
    return [n for n in (data.get('nodes') or []) if isinstance(n, dict)]


def match_column(node):
    p = node.get('parameters') or {}
    cols = p.get('columns')
    mc = cols.get('matchingColumns') if isinstance(cols, dict) else None
    return mc if mc is not None else (p.get('columnToMatchOn') or p.get('key'))


def measured(node):
    """What the study reads from one node."""
    t = node.get('type') or ''
    out = {f: node.get(f) for f in FIELDS}
    out['errorTrigger'] = t.endswith('errorTrigger')
    out['googleSheets'] = t == 'n8n-nodes-base.googleSheets'
    if out['googleSheets']:
        out['sheets_operation'] = (node.get('parameters') or {}).get('operation')
        out['sheets_match_column'] = match_column(node)
    return out


def carries_signal(node):
    m = measured(node)
    return bool(m['retryOnFail'] is True or m['onError'] or m['continueOnFail'] is True
                or m['errorTrigger'] or m['googleSheets'])


def flags(data):
    """The workflow-level signals behind the published counts (same rules as reproduce-corpus.py)."""
    ns = nodes_of(data)
    retry = any(n.get('retryOnFail') is True for n in ns)
    error_output = any(n.get('onError') == 'continueErrorOutput' for n in ns)
    regular = any(n.get('onError') == 'continueRegularOutput' for n in ns)
    legacy = any(n.get('continueOnFail') is True for n in ns)
    error_trigger = any((n.get('type') or '').endswith('errorTrigger') for n in ns)
    upsert = any(n.get('type') == 'n8n-nodes-base.googleSheets'
                 and (n.get('parameters') or {}).get('operation') in ('appendOrUpdate', 'upsert') for n in ns)
    basic = retry or error_output or error_trigger
    return {'retry_on_fail_true': retry, 'on_error_continue_error_output': error_output,
            'on_error_continue_regular_output': regular, 'continue_on_fail_true_legacy': legacy,
            'contains_error_trigger': error_trigger, 'sheets_append_or_update': upsert,
            'no_error_handling_field_of_any_kind': not (basic or regular or legacy),
            'no_retry_no_error_output_no_error_trigger': not basic}


def by_name(data):
    named, dupes = {}, 0
    for n in nodes_of(data):
        key = n.get('name')
        if key in named:
            dupes += 1
        named[key] = n
    return named, dupes


def compare(old_tree, new_tree):
    """Node-by-node comparison of files present at both commits, matched by path and node name."""
    tally = Counter()
    field_diffs, type_diffs, examples = Counter(), Counter(), []
    flag_diffs = Counter()
    for path in sorted(set(old_tree) & set(new_tree)):
        tally['files_compared'] += 1
        if old_tree[path] == new_tree[path]:
            tally['files_byte_identical'] += 1
        a, b = load(old_tree[path]), load(new_tree[path])
        old_nodes, d1 = by_name(a)
        new_nodes, d2 = by_name(b)
        tally['duplicate_node_names'] += d1 + d2
        for name in old_nodes.keys() & new_nodes.keys():
            tally['nodes_in_both'] += 1
            m1, m2 = measured(old_nodes[name]), measured(new_nodes[name])
            for key in m1.keys() | m2.keys():
                if m1.get(key) != m2.get(key):
                    field_diffs[key] += 1
                    if len(examples) < 10:
                        examples.append({'path': path, 'node': name, 'field': key,
                                         'old': m1.get(key), 'new': m2.get(key)})
            t1, t2 = old_nodes[name].get('type') or '', new_nodes[name].get('type') or ''
            if t1 != t2:
                type_diffs[f'{t1} -> {t2}' if t1.startswith('@n8n/') and t2 == 'n8n-nodes-base.noOp'
                           else 'other type change'] += 1
        added = [new_nodes[k] for k in new_nodes.keys() - old_nodes.keys()]
        removed = [old_nodes[k] for k in old_nodes.keys() - new_nodes.keys()]
        tally['nodes_added'] += len(added)
        tally['nodes_removed'] += len(removed)
        tally['added_nodes_carrying_a_measured_field'] += sum(carries_signal(n) for n in added)
        tally['removed_nodes_carrying_a_measured_field'] += sum(carries_signal(n) for n in removed)
        if (a.get('connections') or {}) != (b.get('connections') or {}):
            tally['files_connections_changed'] += 1
        if a.get('settings') != b.get('settings'):
            tally['files_settings_changed'] += 1
        if a.get('meta') != b.get('meta'):
            tally['files_meta_changed'] += 1
        f1, f2 = flags(a), flags(b)
        for key in f1:
            if f1[key] != f2[key]:
                flag_diffs[key] += 1
    # Field-diff keys: retryOnFail, onError, ... errorTrigger, googleSheets, sheets_*. A type change
    # from a scoped @n8n/ type to noOp does not alter errorTrigger or googleSheets.
    return {'tally': dict(tally), 'measured_field_differences': dict(field_diffs),
            'type_changes_on_matched_nodes': dict(type_diffs),
            'workflow_signal_flips': dict(flag_diffs), 'examples': examples}


def added_node_types(old_tree, new_tree):
    kinds = Counter()
    for path in set(old_tree) & set(new_tree):
        old_nodes, _ = by_name(load(old_tree[path]))
        new_nodes, _ = by_name(load(new_tree[path]))
        for k in new_nodes.keys() - old_nodes.keys():
            kinds[new_nodes[k].get('type')] += 1
    return dict(kinds.most_common(6))


def norm(value):
    if isinstance(value, dict):
        return {k: norm(v) for k, v in sorted(value.items()) if k not in VOLATILE}
    if isinstance(value, list):
        return [norm(v) for v in value]
    return value


def published_counts(t):
    """The study's own pipeline (grouping + counts) at any commit."""
    groups = {}
    for path in sorted(t):
        data = load(t[path])
        core = {'nodes': sorted(json.dumps(norm(n), sort_keys=True) for n in nodes_of(data)),
                'connections': json.dumps(norm(data.get('connections') or {}), sort_keys=True)}
        groups.setdefault(hashlib.sha1(json.dumps(core, sort_keys=True).encode()).hexdigest(), path)
    counts = Counter({'files': len(t), 'groups': len(groups)})
    sizes = []
    for path in groups.values():
        counts.update({k: int(v) for k, v in flags(load(t[path])).items()})
        sizes.append(len(nodes_of(load(t[path]))))
    sizes.sort()
    counts.update({'nodes_per_workflow_median': sizes[len(sizes) // 2] if len(sizes) % 2 else
                   (sizes[len(sizes) // 2 - 1] + sizes[len(sizes) // 2]) / 2,
                   'nodes_per_workflow_max': sizes[-1]})
    return dict(counts)


def renames_and_injections(old_tree, new_tree):
    """Pair each vanished node name with a same-type node that appeared in the same file (a rename);
    what is left over after pairing is what the rewrites added."""
    tally, injected = Counter(), Counter()
    for path in set(old_tree) & set(new_tree):
        old_nodes, _ = by_name(load(old_tree[path]))
        new_nodes, _ = by_name(load(new_tree[path]))
        pool = [new_nodes[k] for k in new_nodes.keys() - old_nodes.keys()]
        for gone in (old_nodes[k] for k in old_nodes.keys() - new_nodes.keys()):
            same = [a for a in pool if a.get('type') == gone.get('type')]
            hit = next((a for a in same if a.get('parameters') == gone.get('parameters')), None)
            if hit is not None:
                tally['renamed_identical_type_and_parameters'] += 1
                tally['renamed_with_same_measured_fields'] += measured(hit) == measured(gone)
            elif same:
                hit = same[0]
                tally['renamed_same_type_parameters_differ'] += 1
            else:
                tally['vanished_without_a_same_type_replacement'] += 1
                continue
            pool.remove(hit)
        injected.update(a.get('type') for a in pool)
        tally['files_with_injected_nodes'] += bool(pool)
        tally['injected_nodes_carrying_a_measured_field'] += sum(carries_signal(a) for a in pool)
    tally['injected_nodes'] = sum(injected.values())
    return {**dict(tally), 'injected_by_type': dict(injected.most_common(8))}


def main():
    first, base, pin = tree(FIRST), tree(BASE), tree(PIN)
    first_blobs = set(first.values())
    report = {
        'repo_head': git('rev-parse', 'HEAD').decode().strip(),
        'commits': {'first_upload': FIRST, 'pre_rewrite_base': BASE, 'rewrites': STEPS, 'pinned': PIN},
        'files': {'first_upload': len(first), 'pre_rewrite_base': len(base), 'pinned': len(pin),
                  'base_files_byte_identical_to_first_upload': sum(b in first_blobs for b in base.values()),
                  'in_base_and_pinned': len(set(base) & set(pin)),
                  'only_in_pinned (added after the rewrites)': sorted(set(pin) - set(base)),
                  'only_in_base': sorted(set(base) - set(pin))},
        'base_vs_pinned': compare(base, pin),
        'nodes_added_base_to_pinned_by_type': added_node_types(base, pin),
        'base_to_pinned_renames_and_injections': renames_and_injections(base, pin),
        'steps': {},
        'published_pipeline': {'pre_rewrite_base': published_counts(base), 'pinned': published_counts(pin)},
    }
    for sha in STEPS:
        parent = git('rev-parse', f'{sha}^').decode().strip()[:8]
        step = compare(tree(parent), tree(sha))
        step['parent'] = parent
        step['nodes_added_by_type'] = added_node_types(tree(parent), tree(sha))
        report['steps'][sha] = step
    out = Path(__file__).with_suffix('.json')
    out.write_text(json.dumps(report, indent=1, default=str) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=1, default=str))


if __name__ == '__main__':
    main()
