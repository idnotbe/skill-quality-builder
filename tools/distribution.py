"""Validate the shared distribution contract and evaluate real installer behavior.

Python 3.10+, standard library. --smoke explicitly runs installed third-party CLIs
in a disposable home; it does not invoke a model or establish skill effectiveness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

MANIFESTS = ('.claude-plugin/plugin.json', '.codex-plugin/plugin.json')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def inventory(root: Path) -> dict[str, str]:
    require(root.is_dir() and not root.is_symlink(), f'Invalid bundle: {root}')
    files: dict[str, str] = {}
    seen: set[str] = set()
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root).as_posix()
        require(not path.is_symlink(), f'Symlink: {rel}')
        require(path.is_file() or path.is_dir(), f'Special file: {rel}')
        key = unicodedata.normalize('NFC', rel).casefold()
        require(key not in seen, f'Case/normalization collision: {rel}')
        seen.add(key)
        for part in path.relative_to(root).parts:
            stem = part.split('.')[0].upper()
            require(not (part.endswith((' ', '.'))
                         or re.search(r'[<>:"\\|?*\x00-\x1f]', part)
                         or stem in {'CON', 'PRN', 'AUX', 'NUL'}
                         or re.fullmatch(r'(COM|LPT)[1-9¹²³]', stem)),
                    f'Nonportable name: {rel}')
        if path.is_file():
            files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    require('SKILL.md' in files, 'Missing SKILL.md')
    return files


def validate(root: Path) -> tuple[dict, dict[str, str]]:
    manifests = [json.loads((root / p).read_text(encoding='utf-8')) for p in MANIFESTS]
    require(manifests[0] == manifests[1], 'Host manifests must agree')
    manifest = manifests[0]
    name = manifest.get('name', '')
    require(isinstance(name, str) and bool(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name)),
            'Invalid name')
    require(bool(re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)',
                             str(manifest.get('version', '')))), 'Invalid release version')
    require(manifest.get('skills') == './.agents/skills/', 'Noncanonical skills path')
    require(manifest.get('repository') == f'https://github.com/idnotbe/{name}',
            'Wrong repository identity')
    require(isinstance(manifest.get('description'), str) and bool(manifest['description'].strip()),
            'Missing description')
    require(not (root / 'plugin.json').exists(), 'Portable root manifest would override custom layout')
    require(not (root / 'skills').exists(), 'Duplicate root skills directory')
    base = root / '.agents/skills'
    require(base.is_dir() and not base.is_symlink() and not (root / '.agents').is_symlink(),
            'Invalid skills directory')
    require([p.name for p in base.iterdir()] == [name], 'Expected one canonical skill')
    bundle = base / name
    files = inventory(bundle)
    text = (bundle / 'SKILL.md').read_text(encoding='utf-8')
    front = re.match(r'\A---\n(.*?)\n---(?:\n|$)', text, re.S)
    require(front is not None, 'Missing frontmatter')
    require(bool(re.search(r'^name: ' + re.escape(name) + r'\s*$', front[1], re.M)),
            'Skill/manifest name mismatch')
    require(bool(re.search(r'^description: .+', front[1], re.M)), 'Missing skill description')
    require((bundle / 'agents/openai.yaml').is_file(), 'Missing Codex skill metadata')
    return manifest, files


def catalogs(name: str) -> tuple[dict, dict]:
    common = {'name': 'distribution-smoke', 'owner': {'name': 'idnotbe'},
              'description': 'Disposable installer compatibility evaluation.'}
    claude_market = dict(common, plugins=[{'name': name, 'source': f'./plugins/{name}'}])
    codex_market = {'name': 'distribution-smoke', 'interface': {'displayName': 'Distribution Smoke'},
                   'plugins': [{'name': name, 'source': {'source': 'local', 'path': f'./plugins/{name}'},
                                'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'},
                                'category': 'Productivity'}]}
    return claude_market, codex_market


def configure_stdio() -> None:
    # Native Windows redirected stdout may default to a legacy code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')


def smoke(root: Path, report: dict) -> None:
    manifest, expected = validate(root)
    name = manifest['name']
    executables = {}
    for command in ('npx', 'claude', 'codex'):
        path = shutil.which(command + '.cmd') if os.name == 'nt' else None
        executables[command] = path or shutil.which(command)
        require(bool(executables[command]), f'Install {command} before --smoke')
    with tempfile.TemporaryDirectory(prefix='distribution smoke ') as temporary:
        scratch = Path(temporary)
        home, project = scratch / 'home', scratch / 'project with spaces'
        home.mkdir()
        (home / '.codex').mkdir()
        (home / '.claude').mkdir()
        project.mkdir()
        env = dict(os.environ)
        env.update(HOME=str(home), USERPROFILE=str(home),
                   CLAUDE_CONFIG_DIR=str(home / '.claude'), CODEX_HOME=str(home / '.codex'),
                   XDG_CONFIG_HOME=str(home / '.config'), DISABLE_TELEMETRY='1',
                   DO_NOT_TRACK='1', CI='1')
        for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN'):
            env.pop(key, None)

        def run(command: str, *args: str) -> str:
            completed = subprocess.run([executables[command], *args], cwd=project,
                                       env=env, text=True, encoding='utf-8', errors='replace',
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       timeout=240, check=False)
            print(completed.stdout, flush=True)
            require(completed.returncode == 0, f'{command} {args}: exit {completed.returncode}')
            return completed.stdout

        report['versions'] = {
            'skills': run('npx', '--yes', 'skills@latest', '--version').strip(),
            'claude': run('claude', '--version').strip(),
            'codex': run('codex', '--version').strip(),
        }
        listing = run('npx', '--yes', 'skills@latest', 'add', str(root), '--list')
        require(name in listing, 'Installer did not discover the skill')
        report['checks'].append('skills-discovery')
        for global_install in (False, True):
            scope = 'global' if global_install else 'project'
            for attempt in (1, 2):
                args = ['--yes', 'skills@latest', 'add', str(root), '--skill', name,
                        '--agent', 'codex', 'claude-code', '--copy', '--yes']
                if global_install:
                    args.append('--global')
                run('npx', *args)
                destination = home if global_install else project
                for host in ('.agents', '.claude'):
                    require(inventory(destination / host / 'skills' / name) == expected,
                            f'{scope}/{host} install differs from source')
                report['checks'].append(f'skills-{scope}-copy-{attempt}')

        # A local marketplace loads only the reviewed bundle, not eval fixtures.
        market = scratch / 'marketplace with spaces'
        plugin = market / 'plugins' / name
        for relative in ('.agents/skills', '.claude-plugin', '.codex-plugin'):
            shutil.copytree(root / relative, plugin / relative)
        for relative in ('.claude-plugin', '.agents/plugins'):
            (market / relative).mkdir(parents=True, exist_ok=True)
        claude_market, codex_market = catalogs(name)
        (market / '.claude-plugin/marketplace.json').write_text(json.dumps(claude_market), encoding='utf-8')
        (market / '.agents/plugins/marketplace.json').write_text(json.dumps(codex_market), encoding='utf-8')
        run('claude', 'plugin', 'validate', str(plugin), '--strict')
        run('claude', 'plugin', 'validate', str(market), '--strict')
        run('claude', 'plugin', 'marketplace', 'add', str(market))
        run('claude', 'plugin', 'install', f'{name}@distribution-smoke')
        registry = json.loads((home / '.claude/plugins/installed_plugins.json').read_text(encoding='utf-8'))
        records = registry['plugins'][f'{name}@distribution-smoke']
        require(bool(records), 'Claude did not record plugin installation')
        installed = Path(records[0]['installPath'])
        require(inventory(installed / '.agents/skills' / name) == expected, 'Claude plugin bundle drift')
        report['checks'].append('claude-plugin-validate-install-integrity')
        run('codex', 'plugin', 'marketplace', 'add', str(market))
        catalog = run('codex', 'plugin', 'marketplace', 'list')
        require('distribution-smoke' in catalog, 'Codex did not register the marketplace')
        report['checks'].append('codex-marketplace-registration')
        # GUI/workspace installation and authenticated model use are separate gates.
        report['codex_plugin_gui_install'] = 'not_run'
        report['chatgpt_web_workspace_import'] = 'not_run'
        report['model_behavior'] = 'not_run'


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = {'scope': 'distribution_not_model_effectiveness', 'checks': [], 'platform': os.name,
              'revision': os.environ.get('GITHUB_SHA'), 'model_behavior': 'not_run'}
    try:
        manifest, files = validate(args.root.resolve())
        report.update(name=manifest['name'], version=manifest['version'], inventory=files)
        report['checks'].append('distribution-contract')
        if args.smoke:
            smoke(args.root.resolve(), report)
        report['status'] = 'pass'
    except (ValueError, OSError, KeyError, IndexError, subprocess.SubprocessError) as exc:
        report.update(status='fail', error=str(exc))
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + '\n', encoding='utf-8')
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
