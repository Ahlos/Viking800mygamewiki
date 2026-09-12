"""Escape and render the model as self-contained, mutually linked HTML pages."""

from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import shutil

from .model import CATEGORIES, SOURCE_TITLES, TOKEN_PATTERN


FIELD_LABELS = {
    'id': 'ID', 'name': 'Namn', 'title': 'Titel', 'description': 'Beskrivning',
    'summary': 'Översikt', 'status': 'Status', 'role': 'Roll', 'date': 'Datum',
    'game_date': 'Speldatum', 'turn': 'Tur', 'source_id': 'Från', 'target_id': 'Till',
    'relation_type': 'Relation', 'organization_ids': 'Organisationer',
    'organization_id': 'Organisation', 'location_id': 'Plats', 'event_id': 'Händelse',
    'decision_id': 'Beslut', 'project_id': 'Projekt', 'character_id': 'Person',
    'person_id': 'Person', 'owner_id': 'Ägare', 'leader_id': 'Ledare',
    'member_ids': 'Medlemmar', 'related_ids': 'Relaterade poster', 'entity_id': 'Artikelobjekt',
    'start_date': 'Startdatum', 'end_date': 'Slutdatum', 'budget': 'Budget',
    'amount': 'Mängd', 'unit': 'Enhet', 'notes': 'Anteckningar', 'type': 'Typ',
}


def e(value):
    return escape(str(value), quote=True)


def relative(target, current):
    path, _, fragment = target.partition('#')
    rel = os.path.relpath(path, os.path.dirname(current) or '.').replace('\\', '/')
    return rel + ('#' + fragment if fragment else '')


class Renderer:
    def __init__(self, model, destination):
        self.model = model
        self.destination = destination
        self.current = 'index.html'

    def link(self, target, label):
        return f'<a href="{e(relative(target, self.current))}">{e(label)}</a>'

    def text(self, value):
        if value is None:
            return '<span class="unknown">Okänt / ej angivet</span>'
        if isinstance(value, bool):
            return 'Ja' if value else 'Nej'
        text = str(value)
        target = self.model.target(text)
        if target:
            record = self.model.records.get(text)
            label = f'{record.title} ({text})' if record else text
            return self.link(target, label)
        chunks, cursor = [], 0
        for match in TOKEN_PATTERN.finditer(text):
            chunks.append(e(text[cursor:match.start()]))
            target = self.model.target(match.group())
            chunks.append(self.link(target, match.group()) if target else e(match.group()))
            cursor = match.end()
        chunks.append(e(text[cursor:]))
        return ''.join(chunks)

    def value(self, value, depth=0, pointer='', anchors=False):
        if isinstance(value, dict):
            if not value:
                return '<span class="muted">Tomt objekt</span>'
            anchor = f' id="row-{sha256(pointer.encode()).hexdigest()[:16]}"' if anchors else ''
            rows = []
            for key, child in value.items():
                part = str(key).replace('~', '~0').replace('/', '~1')
                label = FIELD_LABELS.get(key, str(key).replace('_', ' ').capitalize())
                rows.append(f'<tr><th scope="row" title="{e(key)}">{e(label)}</th><td>'
                            + self.value(child, depth + 1, pointer + '/' + part, anchors) + '</td></tr>')
            return f'<div class="table-scroll"{anchor}><table class="facts"><tbody>' + ''.join(rows) + '</tbody></table></div>'
        if isinstance(value, list):
            if not value:
                return '<span class="muted">Inga poster angivna</span>'
            return '<ul class="values">' + ''.join(
                '<li>' + self.value(item, depth + 1, pointer + '/' + str(i), anchors) + '</li>'
                for i, item in enumerate(value)) + '</ul>'
        return '<span class="text-value">' + self.text(value) + '</span>'

    def page(self, path, title, content, eyebrow='Kampanjens uppslagsverk', search=False):
        # Callers set current before composing content, to get correct relative links.
        assert self.current == path
        counts = {name: sum(r.source == name for r in self.model.records.values()) for name in CATEGORIES}
        nav = ''.join('<li>' + self.link(f'categories/{slug}.html', label)
                      + f'<span>{counts[name]}</span></li>' for name, (slug, label) in CATEGORIES.items())
        source_nav = ''.join('<li>' + self.link(f'sources/{name}.html', SOURCE_TITLES[name]) + '</li>'
                             for name in self.model.sources if name not in CATEGORIES)
        warn_count = len(self.model.warnings)
        js = (f'<script src="{e(relative("assets/search-index.js", path))}" defer></script>'
              f'<script src="{e(relative("assets/search.js", path))}" defer></script>') if search else ''
        html = f'''<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{e(title)} – STATSSPELET</title>
<link rel="stylesheet" href="{e(relative('assets/style.css', path))}">{js}</head>
<body><a class="skip" href="#content">Hoppa till innehållet</a>
<header class="top"><a class="brand" href="{e(relative('index.html', path))}"><span class="seal" aria-hidden="true">S</span>
<span>STATSSPELET<small>KAMPANJENS WIKI</small></span></a>
<form action="{e(relative('search.html', path))}" method="get" role="search"><label class="sr-only" for="nav-search">Sök i wikin</label>
<input id="nav-search" name="q" type="search" placeholder="Sök efter namn, ID eller innehåll…"><button type="submit">Sök</button></form>
<span class="offline">Lokalt uppslagsverk</span></header>
<div class="layout"><aside><nav aria-label="Wikins navigation"><p class="nav-heading">UTFORSKA</p><ul>
<li>{self.link('index.html', 'Huvudsida')}</li><li>{self.link('timeline.html', 'Tidslinje')}</li>
<li>{self.link('search.html', 'Sök i wikin')}</li></ul><p class="nav-heading">KATEGORIER</p><ul>{nav}</ul>
<details class="source-nav"><summary>Källdata &amp; spelläge</summary><ul>{source_nav}</ul></details>
<ul><li>{self.link('report.html', f'Datarapport ({warn_count})')}</li></ul></nav></aside>
<main id="content"><div class="eyebrow">{e(eyebrow)}</div><h1>{e(title)}</h1>
<div class="article-tab">Läs artikel <span>Från sparade JSON-filer</span></div>{content}
<footer>STATSSPELET Wiki 1.0 · En läsvy av sparad speldata. Saknade uppgifter fylls inte i.
{self.link('report.html', 'Visa datarapport och källor')}</footer></main></div></body></html>'''
        target = self.destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding='utf-8')

    def records_list(self, records):
        ordered = sorted(records, key=lambda r: (r.title.casefold(), r.id))
        if not ordered:
            return '<p class="empty">Inga artikelposter finns i den här kategorin i den inlästa sparningen.</p>'
        return '<ul class="article-list">' + ''.join(
            f'<li>{self.link(r.path, r.title)} <small>{e(r.id)}</small></li>' for r in ordered) + '</ul>'

    def build(self):
        self.current = 'index.html'
        intro = '<p class="lead">Personer, platser och beslut — samlade ur din sparade kampanj.</p>'
        manifest = self.model.sources.get('manifest', {})
        game = self.model.sources.get('game_state', {})
        if isinstance(manifest, dict) and manifest.get('is_demo') is True:
            intro += '<div class="notice">DEMO · Fiktiva testdata. Detta är inte din kampanj.</div>'
        intro += f'<div class="stats"><div><strong>{len(self.model.records)}</strong>artiklar</div>'
        intro += f'<div><strong>{len(self.model.sources)}</strong>inlästa källfiler</div>'
        intro += f'<div><strong>{len(self.model.timeline)}</strong>tidslinjeposter</div></div>'
        if self.model.warnings:
            intro += '<div class="notice">Sparningen har uppgifter att kontrollera. ' + self.link('report.html', 'Läs datarapporten') + '.</div>'
        intro += '<h2>Utforska uppslagsverket</h2><div class="category-grid">'
        for name, (slug, title) in CATEGORIES.items():
            records = [r for r in self.model.records.values() if r.source == name]
            intro += '<section class="category-card"><h3>' + self.link(f'categories/{slug}.html', title) + '</h3>'
            intro += f'<p class="muted">{len(records)} artiklar</p>' + self.records_list(records[:4]) + '</section>'
        intro += '</div>'
        if game:
            intro += '<h2>Aktuellt spelläge</h2>' + self.value(game)
        intro += '<h2>Om denna wiki</h2><p>Innehållet kommer från FULLSAVE-mappen. Artiklarna visar de uppgifter '
        intro += 'som finns i JSON-filerna, med länkar mellan identifierade poster. Ingen ny spelhistoria genereras.</p>'
        self.page('index.html', 'Välkommen till kampanjens wiki', intro)

        for name, (slug, title) in CATEGORIES.items():
            self.current = f'categories/{slug}.html'
            records = [r for r in self.model.records.values() if r.source == name]
            body = f'<p class="lead">{len(records)} artiklar i kategorin {e(title.lower())}.</p>'
            if name in self.model.sources:
                body += '<p>' + self.link(f'sources/{name}.html', 'Visa kategorins fullständiga källdata') + '</p>'
            else:
                body += '<div class="notice">Källfilen ' + e(name + '.json') + ' saknas.</div>'
            self.page(self.current, title, body + self.records_list(records), 'Kategori')

        for record in self.model.records.values():
            self.current = record.path
            slug, category = CATEGORIES[record.source]
            body = '<div class="article-meta">' + self.link(f'categories/{slug}.html', category)
            body += f' <span>·</span> <code>{e(record.id)}</code></div>'
            if record.synthetic:
                body += '<div class="notice">Källposten saknar ID. Artikelns LOCAL-ID gäller endast denna presentation.</div>'
            summary_key = next((key for key in ('summary', 'description', 'overview') if key in record.data), None)
            if summary_key:
                body += '<div class="lead">' + self.value(record.data[summary_key]) + '</div>'
            body += '<h2>Fakta</h2>' + self.value(record.data)
            refs = self.model.references.get(record.id, [])
            relations = [r for r in refs if r['source'] == 'relationships']
            if relations:
                body += '<h2>Relationer</h2>'
                for relation in relations:
                    body += self.value(relation['data'])
            body += '<h2>Hänvisningar till denna artikel</h2>'
            if refs:
                body += '<ul>' + ''.join('<li>' + self.link(r['path'], r['title'])
                                         + ' <small>(' + e(r['source'] + '.json') + ')</small></li>'
                                         for r in refs) + '</ul>'
            else:
                body += '<p class="muted">Inga identifierade hänvisningar i sparningen.</p>'
            body += '<h2>Källa</h2><p>' + self.link(f'sources/{record.source}.html', record.source + '.json')
            body += ' · JSON-sökväg: <code>' + e(record.pointer or '/') + '</code></p>'
            self.page(record.path, record.title, body, category)

        for name, data in self.model.sources.items():
            self.current = f'sources/{name}.html'
            body = '<p class="lead">Innehåll från <code>' + e(name + '.json') + '</code>.</p>'
            body += self.value(data, anchors=True)
            body += '<details class="raw"><summary>Visa exakt JSON-innehåll (formaterat)</summary><pre>'
            body += e(json.dumps(data, ensure_ascii=False, indent=2)) + '</pre></details>'
            self.page(self.current, SOURCE_TITLES[name], body, 'Källdata')

        self.current = 'timeline.html'
        body = '<p class="lead">Händelser, beslut och poster från timeline.json.</p>'
        body += '<p>Datum i formatet ÅÅÅÅ-MM-DD visas i kronologisk ordning. Övriga datum och poster utan datum visas separat.</p>'
        for group, heading in ((0, 'Kronologisk tidslinje'), (1, 'Datum utan säker sortering'), (2, 'Datum saknas')):
            entries = [x for x in self.model.timeline if x['group'] == group]
            if entries:
                body += f'<h2>{heading}</h2><ol class="timeline">'
                for entry in entries:
                    body += '<li><div class="date">' + e(entry['date']) + '</div><div>' + self.link(entry['path'], entry['title'])
                    if entry['turn'] is not None:
                        body += '<small> Tur: ' + e(entry['turn']) + '</small>'
                    body += '</div></li>'
                body += '</ol>'
        if not self.model.timeline:
            body += '<p class="empty">Det finns ännu inga tidslinjeposter i de inlästa filerna.</p>'
        self.page(self.current, 'Tidslinje', body)

        self.current = 'search.html'
        body = '''<p class="lead">Sök i artiklarnas namn, ID och innehåll samt i källfilerna.</p>
<form id="search-form" class="search-form" role="search"><label for="query">Sökord</label>
<div class="search-controls"><input id="query" name="q" type="search" placeholder="Till exempel en person eller PER-000001">
<button type="submit">Sök</button></div><label for="category-filter">Kategori</label>
<select id="category-filter"><option value="">Alla kategorier och källor</option>'''
        body += ''.join(f'<option value="{e(title)}">{e(title)}</option>' for _, title in CATEGORIES.values())
        body += '''<option value="Källdata">Källdata</option></select></form>
<p id="result-count" role="status" aria-live="polite"></p><ol id="results" class="search-results"></ol>
<button id="more-results" type="button" hidden>Visa fler träffar</button>
<noscript><p>Sökningen kräver JavaScript. Du kan fortfarande använda kategorisidorna och webbläsarens textsökning.</p></noscript>'''
        self.page(self.current, 'Sök i wikin', body, search=True)

        self.current = 'report.html'
        body = '<p class="lead">Datakvalitet och inlästa källor.</p>'
        body += '<p>Rapporten kontrollerar filformat och identifierade referenser. Den bevisar inte att kampanjen är komplett '
        body += 'eller att ett eventuellt manifest stämmer med spelhistoriken.</p>'
        body += '<h2>Varningar</h2>'
        if self.model.warnings:
            body += '<ul class="warnings">' + ''.join('<li>' + e(w) + '</li>' for w in self.model.warnings) + '</ul>'
        else:
            body += '<p>Inga varningar i generatorns kontroller.</p>'
        body += '<h2>Inlästa filer</h2><ul>' + ''.join('<li>' + self.link(f'sources/{name}.html', name + '.json') + '</li>'
                                                        for name in self.model.sources) + '</ul>'
        body += '<h2>Saknade filer</h2><p>' + e(', '.join(self.model.missing) or 'Inga') + '</p>'
        body += '<p>' + self.link('build_report.json', 'Läs maskinläsbar rapport med SHA-256 för källfilerna') + '</p>'
        self.page(self.current, 'Datarapport', body)


def render_site(model, destination):
    Renderer(model, destination).build()
    assets = destination / 'assets'
    assets.mkdir()
    for name in ('style.css', 'search.js'):
        shutil.copyfile(Path(__file__).parent / 'assets' / name, assets / name)
    index = [{'title': r.title, 'id': r.id, 'category': CATEGORIES[r.source][1],
              'url': r.path, 'text': json.dumps(r.data, ensure_ascii=False)}
             for r in model.records.values()]
    index += [{'title': SOURCE_TITLES[name], 'id': name + '.json', 'category': 'Källdata',
               'url': f'sources/{name}.html', 'text': json.dumps(data, ensure_ascii=False)}
              for name, data in model.sources.items()]
    encoded = json.dumps(index, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e')
    encoded = encoded.replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    (assets / 'search-index.js').write_text('window.STATWIKI_INDEX = ' + encoded + ';\n', encoding='utf-8')
