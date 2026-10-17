"""Read a pinned public GitHub archive without extracting or executing its files.

Reproduce selected published aggregates using the historical normalization rule.
This checks the snapshot's declarations, not real execution behavior.
"""
import csv
import hashlib
import io
import json
import statistics
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
SHA = '94007c1445d9258a7da116646b79473e7c7c3282'
URL = f'https://codeload.github.com/Zie619/n8n-workflows/zip/{SHA}'
VOLATILE = {'id', 'versionId', 'webhookId', 'position', 'createdAt', 'updatedAt',
            'meta', 'tags', 'pinData', 'active', 'instanceId'}

def norm(value):
    if isinstance(value, dict):
        return {k: norm(v) for k, v in sorted(value.items()) if k not in VOLATILE}
    if isinstance(value, list):
        return [norm(v) for v in value]
    return value

with urlopen(URL, timeout=90) as response:
    archive = response.read()
groups = defaultdict(list)
raw_hashes = set()
with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
    prefix = f'n8n-workflows-{SHA}/workflows/'
    paths = sorted(p for p in zipped.namelist() if p.startswith(prefix) and p.endswith('.json'))
    case_groups = defaultdict(list)
    for path in paths:
        case_groups[path.casefold()].append(path)
    for path in paths:
        body = zipped.read(path)
        raw_hashes.add(hashlib.sha256(body).hexdigest())
        data = json.loads(body)
        nodes = [n for n in data.get('nodes', []) if isinstance(n, dict)]
        core = {'nodes': sorted(json.dumps(norm(n), sort_keys=True) for n in nodes),
                'connections': json.dumps(norm(data.get('connections') or {}), sort_keys=True)}
        fingerprint = hashlib.sha1(json.dumps(core, sort_keys=True).encode()).hexdigest()
        groups[fingerprint].append((path, nodes))

counts = Counter()
sizes = []
subgroup = Counter()
for group in groups.values():
    path, nodes = group[0]
    sizes.append(len(nodes))
    retry = any(n.get('retryOnFail') is True for n in nodes)
    error_output = any(n.get('onError') == 'continueErrorOutput' for n in nodes)
    regular = any(n.get('onError') == 'continueRegularOutput' for n in nodes)
    legacy = any(n.get('continueOnFail') is True for n in nodes)
    error_trigger = any((n.get('type') or '').endswith('errorTrigger') for n in nodes)
    basic = retry or error_output or error_trigger
    any_signal = basic or regular or legacy
    signals = {
        'retry_on_fail_true': retry, 'on_error_continue_error_output': error_output,
        'on_error_continue_regular_output': regular, 'continue_on_fail_true_legacy': legacy,
        'contains_error_trigger': error_trigger,
        'no_error_handling_field_of_any_kind': not any_signal,
        'no_retry_no_error_output_no_error_trigger': not basic,
        'suppression_only_errors_silently_swallowed': (regular or legacy) and not basic,
    }
    counts.update({key: int(value) for key, value in signals.items()})
    sheets = [n for n in nodes if n.get('type') == 'n8n-nodes-base.googleSheets']
    counts['google_sheets_nodes'] += len(sheets)
    counts['google_sheets_workflows'] += bool(sheets)
    upserts = [n for n in sheets if (n.get('parameters') or {}).get('operation') in ('appendOrUpdate', 'upsert')]
    counts['append_or_update_or_upsert_nodes'] += len(upserts)
    counts['append_or_update_or_upsert_workflows'] += bool(upserts)
    if not upserts:
        continue
    # Matches historical cross.py, including its broad non-manual trigger definition.
    automatic = any(('rigger' in (n.get('type') or '') or (n.get('type') or '').endswith('.webhook'))
                    and 'manualTrigger' not in (n.get('type') or '') for n in nodes)
    subset = {
        'upsert_wf_no_retry_no_error_branch_no_error_trigger': not basic,
        'upsert_wf_retry_on_fail_anywhere': retry,
        'upsert_wf_retry_on_fail_on_the_upsert_node': any(n.get('retryOnFail') is True for n in upserts),
        'upsert_wf_continue_error_output_anywhere': error_output,
        'upsert_wf_contains_error_trigger': error_trigger,
        'upsert_wf_error_suppression_present': regular or legacy,
        'upsert_wf_automatic_trigger': automatic,
        'upsert_wf_automatic_trigger_and_no_error_handling': automatic and not basic,
    }
    counts.update({key: int(value) for key, value in subset.items()})
    subgroup['automatic_and_no_any_of_five_signals'] += automatic and not any_signal
    subgroup['automatic_and_no_retry_error_output_error_trigger'] += automatic and not basic

counts.update({
    'corpus_files': len(paths), 'corpus_unique_workflows': len(groups),
    'corpus_duplicate_groups': sum(len(v) > 1 for v in groups.values()),
    'corpus_redundant_copies': len(paths) - len(groups),
    'nodes_per_workflow_median': statistics.median(sizes),
    'nodes_per_workflow_mean': round(statistics.mean(sizes), 1),
    'nodes_per_workflow_max': max(sizes),
})
with urlopen('https://noderecipe.com/data/n8n-error-handling-2026-09.csv', timeout=40) as response:
    published_bytes = response.read()
published = {r['metric']: r for r in csv.DictReader(io.StringIO(published_bytes.decode('utf-8-sig')))}
# Accept the documented September 29 rename once the corrected data is deployed.
old_key = 'upsert_wf_automatic_trigger_and_no_error_handling'
new_key = 'upsert_wf_non_manual_trigger_no_retry_no_error_output_no_error_trigger'
if new_key in published and old_key not in published:
    counts[new_key] = counts.pop(old_key)
checks = [dict(metric=key, computed=value, published=float(published[key]['count']),
               matches=value == float(published[key]['count'])) for key, value in sorted(counts.items())]
report = {
    'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'pinned_commit': SHA,
    'archive_url': URL, 'archive_sha256': hashlib.sha256(archive).hexdigest(),
    'published_csv_sha256': hashlib.sha256(published_bytes).hexdigest(),
    'raw_byte_unique_files': len(raw_hashes), 'normalized_unique_files': len(groups),
    'case_insensitive_path_collisions': [v for v in case_groups.values() if len(v) > 1],
    'checks': checks, 'mismatches': [row for row in checks if not row['matches']],
    'automatic_upsert_subgroup_definition_check': dict(subgroup),
    'limits': ['No workflow executed', 'No historical provenance comparison rerun',
               'Normalization recursively removes id keys, including nested parameters',
               'No runtime safety, error wiring, or production representativeness claim',
               'Only the metrics explicitly listed in checks were reproduced'],
}
(ROOT / 'corpus-validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k != 'checks'}, indent=2))
print(f'Compared {len(checks)} metrics; {len(report["mismatches"])} mismatches.')
