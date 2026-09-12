"""JSON loading, tolerant collection normalization and reference indexing."""

from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

FILES = ('manifest game_state characters relationships organizations locations politics '
         'economy resources military projects events timeline decisions consequences rules '
         'open_questions wiki_index').split()
CATEGORIES = {
    'characters': ('personer', 'Personer'),
    'organizations': ('organisationer', 'Organisationer'),
    'projects': ('projekt', 'Projekt'),
    'military': ('militar', 'Militära objekt'),
    'locations': ('platser', 'Platser'),
    'resources': ('resurser', 'Resurser'),
    'events': ('handelser', 'Händelser'),
    'decisions': ('beslut', 'Beslut'),
}
SOURCE_TITLES = {
    'manifest': 'Sparningens manifest', 'game_state': 'Spelläget',
    'relationships': 'Relationer', 'politics': 'Politik', 'economy': 'Ekonomi',
    'timeline': 'Tidslinjens källdata', 'consequences': 'Konsekvenser',
    'rules': 'Regler', 'open_questions': 'Öppna frågor', 'wiki_index': 'Wikiindex',
    **{key: title for key, (_, title) in CATEGORIES.items()},
}
ID_PATTERN = re.compile(r'^[A-Za-z][A-Za-z0-9_]*-[A-Za-z0-9_-]+$')
TOKEN_PATTERN = re.compile(r'(?<![\w-])[A-Za-z][A-Za-z0-9_]*-[A-Za-z0-9_-]+(?![\w-])')
IDENTITY_FIELDS = ('id', 'character_id', 'person_id', 'organization_id',
                   'project_id', 'location_id', 'resource_id', 'event_id',
                   'decision_id', 'unit_id', 'ship_id', 'object_id')
EXTERNAL_IDS = {'campaign_id', 'save_id', 'fullsave_id', 'update_id', 'turn_id',
                'parent_save_id', 'base_fullsave_id', 'last_update_id'}


class DataError(ValueError):
    """A user-facing validation failure."""


def title_of(data, fallback):
    for key in ('name', 'title', 'label', 'namn', 'rubrik'):
        if isinstance(data.get(key), str) and data[key].strip():
            return data[key]
    return fallback


def pointer_part(value):
    return str(value).replace('~', '~0').replace('/', '~1')


def collections(value, pointer='', key_id=None, in_list=False):
    """Yield records from containers; never flatten the fields inside a record.

    Explicit `id` or a title identifies a record. Root/list flat dictionaries
    are also records. ID-keyed maps retain the key when a record has no ID.
    """
    if isinstance(value, list):
        for i, item in enumerate(value):
            yield from collections(item, f'{pointer}/{i}', in_list=True)
    elif isinstance(value, dict):
        record = (any(key in value for key in IDENTITY_FIELDS) or key_id is not None or
                  any(isinstance(value.get(k), str) for k in ('name', 'title', 'namn', 'rubrik')) or
                  (in_list and not any(isinstance(v, (dict, list)) for v in value.values())) or
                  (not pointer and value and not any(isinstance(v, (dict, list)) for v in value.values())))
        if record:
            yield pointer, value, key_id
        else:
            for key, item in value.items():
                if isinstance(item, (dict, list)):
                    yield from collections(item, f'{pointer}/{pointer_part(key)}',
                                           key if ID_PATTERN.fullmatch(key) else None)


def ref_values(value, key=''):
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key != 'id' and child_key not in EXTERNAL_IDS:
                yield from ref_values(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from ref_values(child, key)
    elif isinstance(value, str):
        if key.endswith(('_id', '_ids')):
            yield value, True
        else:
            for token in TOKEN_PATTERN.findall(value):
                yield token, False


def container_fields(value, record_paths, pointer=''):
    """Retain wrapper metadata, excluding records already indexed separately."""
    if pointer in record_paths:
        return None
    if isinstance(value, dict):
        return {key: container_fields(child, record_paths, pointer + '/' + pointer_part(key))
                for key, child in value.items()}
    if isinstance(value, list):
        return [container_fields(child, record_paths, pointer + '/' + str(index))
                for index, child in enumerate(value)]
    return value


@dataclass
class Record:
    id: str
    title: str
    source: str
    pointer: str
    data: dict
    path: str
    synthetic: bool = False


@dataclass
class Model:
    sources: dict = field(default_factory=dict)
    records: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    references: dict = field(default_factory=dict)
    source_ids: dict = field(default_factory=dict)
    timeline: list = field(default_factory=list)
    hashes: dict = field(default_factory=dict)

    def warn(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def target(self, ident):
        if ident in self.records:
            return self.records[ident].path
        return self.source_ids.get(ident)


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DataError(f'Dubblerad JSON-nyckel: {key}')
        result[key] = value
    return result


def reject_constant(value):
    raise DataError(f'Ogiltigt JSON-tal: {value}')


def load_model(source: Path) -> Model:
    model = Model()
    if not source.is_dir():
        raise DataError('FULLSAVE måste vara en uppackad mapp.')
    for name in FILES:
        path = source / f'{name}.json'
        if not path.exists():
            model.missing.append(path.name)
            continue
        if path.is_symlink() or path.resolve().parent != source.resolve():
            raise DataError(f'{path.name}: symboliska länkar utanför källmappen stöds inte.')
        try:
            raw = path.read_bytes()
            model.sources[name] = json.loads(raw.decode('utf-8-sig'),
                                             object_pairs_hook=reject_duplicates,
                                             parse_constant=reject_constant)
        except (ValueError, UnicodeError, OSError) as exc:
            raise DataError(f'{path.name}: {exc}') from exc
        model.hashes[path.name] = sha256(raw).hexdigest()
        if not isinstance(model.sources[name], (dict, list)):
            raise DataError(f'{path.name}: roten måste vara ett JSON-objekt eller en lista.')
    if not model.sources:
        raise DataError('Inga av de 18 stödda JSON-filerna finns i FULLSAVE-mappen.')
    if model.missing:
        model.warn('Saknade filer: ' + ', '.join(model.missing))

    for source_name, (category, _) in CATEGORIES.items():
        if source_name not in model.sources:
            continue
        candidates = list(collections(model.sources[source_name]))
        if model.sources[source_name] and not candidates:
            model.warn(f'{source_name}.json: inga artikelposter kunde identifieras; se källsidan.')
        for pointer, data, key_id in candidates:
            own_field = next((key for key in IDENTITY_FIELDS if key in data), None)
            # A category-specific ID can also be a reference: prefer map key over aliases.
            ident = data.get('id', key_id)
            if ident is None and own_field:
                expected = {
                    'characters': ('character_id', 'person_id'), 'organizations': ('organization_id',),
                    'projects': ('project_id',), 'military': ('unit_id', 'ship_id', 'object_id'),
                    'locations': ('location_id',), 'resources': ('resource_id',),
                    'events': ('event_id',), 'decisions': ('decision_id',),
                }[source_name]
                ident = next((data[k] for k in expected if k in data), None)
            synthetic = ident is None or ident == ''
            if not synthetic and (not isinstance(ident, str) or not ident.strip()):
                raise DataError(f'{source_name}.json#{pointer}: ID måste vara en icke-tom sträng.')
            if key_id and ident and ident != key_id:
                raise DataError(f'{source_name}.json#{pointer}: kartnyckel och ID skiljer sig.')
            if synthetic:
                ident = 'LOCAL-' + sha256(f'{source_name}:{pointer}'.encode()).hexdigest()[:16]
                model.warn(f'{source_name}.json#{pointer}: saknar ID; lokalt artikel-ID {ident}.')
            if ident in model.records:
                other = model.records[ident]
                raise DataError(f'Dubblerat artikel-ID {ident}: {other.source}.json#{other.pointer} '
                                f'och {source_name}.json#{pointer}.')
            title = title_of(data, ident)
            ascii_title = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode()
            slug = re.sub(r'[^a-z0-9]+', '-', ascii_title.lower()).strip('-')[:60] or 'artikel'
            digest = sha256(ident.encode()).hexdigest()[:20]
            path = f'articles/{category}/{slug}-{digest}.html'
            model.records[ident] = Record(ident, title, source_name, pointer, data, path, synthetic)

    # Supporting IDs link to the exact row on their source page, not invented articles.
    by_location = {(r.source, r.pointer): r for r in model.records.values()}
    for name, data in model.sources.items():
        if name in CATEGORIES or name == 'wiki_index':
            continue
        for pointer, row, keyed_id in collections(data):
            ident = row.get('id', keyed_id)
            if isinstance(ident, str) and not model.target(ident):
                model.source_ids[ident] = f'sources/{name}.html#row-{sha256(pointer.encode()).hexdigest()[:16]}'

    # Include incoming references from all source records and their context.
    for name, data in model.sources.items():
        rows = list(collections(data))
        if not rows:
            rows = [('', {'data': data}, None)]
        else:
            wrappers = container_fields(data, {pointer for pointer, _, _ in rows})
            rows.append(('', {'data': wrappers}, None))
        for pointer, row, keyed_id in rows:
            ident = row.get('id', keyed_id)
            article = by_location.get((name, pointer))
            if article:
                ident = article.id
            context_path = article.path if article else f'sources/{name}.html'
            context_title = article.title if article else title_of(row, SOURCE_TITLES[name])
            seen = set()
            for target, explicit in ref_values(row):
                if target == ident or target in seen:
                    continue
                seen.add(target)
                if model.target(target):
                    model.references.setdefault(target, []).append({
                        'title': context_title, 'path': context_path,
                        'source': name, 'pointer': pointer, 'data': row,
                    })
                elif explicit and target not in ('UNKNOWN', 'unknown', ''):
                    model.warn(f'{name}.json#{pointer}: okänd ID-referens {target}.')

    for record in model.records.values():
        if record.source in ('events', 'decisions'):
            model.timeline.append(timeline_entry(record.data, record.title, record.path, model))
    if 'timeline' in model.sources:
        for pointer, row, _ in collections(model.sources['timeline']):
            target = next((row[k] for k in ('event_id', 'decision_id', 'entity_id', 'id')
                           if isinstance(row.get(k), str) and model.target(row[k])), None)
            title = title_of(row, model.records[target].title if target in model.records else 'Tidslinjepost')
            path = model.target(target) if target else 'sources/timeline.html'
            model.timeline.append(timeline_entry(row, title, path, model))
    # Deduplicate only exact same date/title/target; retain conflicting source facts.
    unique = {(e['date'], e['title'], e['path']): e for e in model.timeline}
    model.timeline = sorted(unique.values(), key=lambda e: (e['group'], e['sort'], e['title'].casefold()))
    return model


def timeline_entry(data, title, path, model):
    value = next((data[k] for k in ('date', 'game_date', 'start_date', 'datum') if data.get(k)), None)
    text = str(value) if value is not None else 'Datum saknas'
    group, sort = 2, ''
    if value is not None:
        try:
            if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError()
            sort = date.fromisoformat(value).isoformat()
            group = 0
        except ValueError:
            group, sort = 1, text
            model.warn(f'Tidslinje: datumet {text} kan inte sorteras kronologiskt; använd ÅÅÅÅ-MM-DD.')
    return {'date': text, 'title': title, 'path': path, 'group': group, 'sort': sort,
            'turn': data.get('turn', data.get('turn_id'))}
