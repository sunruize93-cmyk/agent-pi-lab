#!/usr/bin/env python3
"""Offline documentation and accounting checks; never executes research tasks."""
from pathlib import Path
import csv
import json
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
errors = []

def require(condition, message):
    if not condition:
        errors.append(message)

required = [
    'README.md', 'README.en.md', 'CHARTER.md', 'GOVERNANCE.md',
    'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md', 'SECURITY.md', 'LICENSE',
    'docs/pilot.md', 'docs/acceptance.md', 'docs/budget.md', 'docs/budget.json',
    'docs/sponsorship.md', 'docs/related-work.md', 'docs/roadmap.md',
    'docs/assets/proposal-20261113.pdf',
    'templates/task-brief.md', 'templates/decision-record.md',
    'templates/experiment-record.md', 'templates/cost-ledger.csv',
    '.github/ISSUE_TEMPLATE/join.yml', '.github/ISSUE_TEMPLATE/task.yml',
    '.github/ISSUE_TEMPLATE/sponsorship.yml',
]
for name in required:
    require((ROOT / name).is_file(), f'Missing community file: {name}')

markdown = sorted(ROOT.rglob('*.md'))
checked_links = 0
for path in markdown:
    if '.git' in path.relative_to(ROOT).parts:
        continue
    text = path.read_text(encoding='utf-8')
    require('/Users/' not in text and '/var/folders/' not in text,
            f'Local machine path in {path.relative_to(ROOT)}')
    for target in re.findall(r'\[[^\]\n]+\]\(([^)\s]+)\)', text):
        parsed = urlsplit(target)
        if parsed.scheme or target.startswith('#'):
            continue
        resolved = (path.parent / unquote(parsed.path)).resolve()
        require(resolved.is_relative_to(ROOT), f'Link escapes repository: {target}')
        require(resolved.exists(), f'Broken link in {path.relative_to(ROOT)}: {target}')
        checked_links += 1

budget_file = ROOT / 'docs/budget.json'
if budget_file.exists():
    try:
        b = json.loads(budget_file.read_text(encoding='utf-8'))
        require(b['status'] == 'proposed', 'Budget status changed; verify commitments before changing check')
        require(b['currency'] == 'CNY', 'Budget currency mismatch')
        for row in b['base'] + b['extension']:
            require(row['amount'] >= 0, f'Negative amount: {row["name"]}')
            if 'quantity' in row:
                require(row['quantity'] * row['rate'] == row['amount'],
                        f'Quantity/rate mismatch: {row["name"]}')
        require(sum(r['amount'] for r in b['base']) == b['base_subtotal'], 'Base subtotal mismatch')
        require(b['base_subtotal'] + b['contingency'] == b['base_ceiling'], 'Base ceiling mismatch')
        require(sum(b['base_tranches']) == b['base_ceiling'], 'Tranche mismatch')
        require(sum(r['amount'] for r in b['extension']) == b['extension_ceiling'], 'Extension mismatch')
        require(b['base_ceiling'] + b['extension_ceiling'] == b['total_ceiling'], 'Total ceiling mismatch')
        by_name = {r['name']: r for r in b['base']}
        require(b['task_runs'] * b['run_researcher_hours'] + b['shared_preparation_researcher_hours']
                == by_name['research_contributors']['quantity'], 'Researcher-hour accounting mismatch')
        require(b['task_runs'] * b['run_model_cloud_ceiling'] + b['shared_model_cloud_budget']
                == by_name['model_api']['amount'] + by_name['cloud_compute']['amount'],
                'Model/compute allocation mismatch')
        require(b['base_weeks'] + b['extension_weeks'] == 12, 'Pilot duration mismatch')
        require(b['run_researcher_hours'] * by_name['research_contributors']['rate']
                + 8 * by_name['human_pi_baseline']['rate'] + b['run_model_cloud_ceiling']
                <= b['run_ceiling'], 'Per-run resource caps exceed total ceiling')
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(f'Invalid budget data: {exc}')

ledger = ROOT / 'templates/cost-ledger.csv'
if ledger.exists():
    with ledger.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.reader(stream))
    require(len(rows) == 1, 'Blank cost template must not contain fabricated expense rows')
    require(len(rows[0]) == len(set(rows[0])) if rows else False, 'Missing or duplicate ledger columns')

if errors:
    print('\n'.join(f'ERROR: {message}' for message in errors), file=sys.stderr)
    sys.exit(1)
print(f'PASS: {len(required)} community files, {checked_links} local links, budget and resource accounting.')
print('Scope: offline structural checks only; no external-link, research-result or funding verification.')
