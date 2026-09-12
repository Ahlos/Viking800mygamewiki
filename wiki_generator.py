#!/usr/bin/env python3
"""Build a static offline wiki from a STATSSPELET FULLSAVE folder."""

import argparse
import json
from pathlib import Path
import sys
import tempfile

from statwiki import __version__
from statwiki.model import DataError, load_model
from statwiki.render import render_site


def build(source, output, strict=False):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise DataError('FULLSAVE och utdatamappen måste vara separata och får inte ligga inuti varandra.')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise DataError('Utdatamappen måste vara ny eller tom. Välj en ny mapp med --output.')
    model = load_model(source)
    if strict and model.warnings:
        raise DataError('Strikt kontroll stoppade bygget:\n' + '\n'.join(model.warnings))
    output.parent.mkdir(parents=True, exist_ok=True)
    # Build beside the destination, then publish only a complete directory.
    with tempfile.TemporaryDirectory(prefix='.statwiki-', dir=output.parent) as temp:
        staging = Path(temp) / 'site'
        staging.mkdir()
        render_site(model, staging)
        report = {
            'generator_version': __version__, 'article_count': len(model.records),
            'loaded_files': [name + '.json' for name in model.sources],
            'missing_files': model.missing, 'warnings': model.warnings,
            'source_sha256': model.hashes,
        }
        (staging / 'build_report.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        if output.exists():
            output.rmdir()  # Only the previously checked empty destination; fails if it gained files.
        staging.rename(output)
    return report


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='Skapa en lokal STATSSPELET-wiki från FULLSAVE.')
    parser.add_argument('fullsave', help='Mappen som direkt innehåller JSON-filerna')
    parser.add_argument('-o', '--output', required=True, help='Ny eller tom utdatamapp, separat från FULLSAVE')
    parser.add_argument('--strict', action='store_true', help='Stoppa även vid varningar och saknade filer')
    parser.add_argument('--version', action='version', version=__version__)
    args = parser.parse_args(argv)
    try:
        report = build(args.fullsave, args.output, args.strict)
    except (DataError, OSError, RecursionError) as exc:
        print(f'Fel: {exc}', file=sys.stderr)
        return 2
    print(f'Klart: {report["article_count"]} artiklar. Öppna {Path(args.output).resolve() / "index.html"}')
    for warning in report['warnings']:
        print('Varning: ' + warning, file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
