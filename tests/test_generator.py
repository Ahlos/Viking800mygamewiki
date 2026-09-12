import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('href', 'src'):
                self.links.append(value)
            if key == 'id':
                self.ids.add(value)


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'FULLSAVE med åäö'
        self.source.mkdir()
        self.out = self.base / 'wiki med åäö'

    def save(self, name, data):
        (self.source / (name + '.json')).write_text(
            json.dumps(data, ensure_ascii=False), encoding='utf-8-sig')

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'wiki_generator.py'),
                               str(self.source), '--output', str(self.out), *args],
                              capture_output=True, text=True, encoding='utf-8')

    def report(self):
        return json.loads((self.out / 'build_report.json').read_text(encoding='utf-8'))

    def test_generates_all_categories_offline_and_preserves_source(self):
        for source, prefix in [('characters', 'PER'), ('organizations', 'ORG'),
                               ('projects', 'PRO'), ('military', 'MIL'),
                               ('locations', 'LOC'), ('resources', 'RES'),
                               ('events', 'EVT'), ('decisions', 'DEC')]:
            self.save(source, {source: [{'id': prefix + '-001', 'name': 'Åland ' + source}]})
        self.save('relationships', [{'id': 'REL-001', 'source_id': 'PER-001',
                                    'target_id': 'ORG-001', 'relation_type': 'medlem'}])
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.iterdir()}
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.out / 'index.html').is_file())
        self.assertTrue((self.out / 'search.html').is_file())
        self.assertTrue((self.out / 'timeline.html').is_file())
        self.assertEqual(len(list((self.out / 'categories').glob('*.html'))), 8)
        self.assertEqual(self.report()['article_count'], 8)
        for page in self.out.rglob('*.html'):
            links = Links()
            links.feed(page.read_text(encoding='utf-8'))
            for target in links.links:
                if target and not target.startswith('#'):
                    self.assertTrue((page.parent / target.split('#')[0]).is_file(), (page, target))
                    if '#' in target:
                        linked = Links()
                        linked.feed((page.parent / target.split('#')[0]).read_text(encoding='utf-8'))
                        self.assertIn(target.split('#')[1], linked.ids)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.iterdir()})
        person = next((self.out / 'articles' / 'personer').glob('*.html')).read_text(encoding='utf-8')
        self.assertIn('medlem', person)
        self.assertIn('ORG-001', person)

    def test_keyed_and_nested_collections_and_unknown_reference(self):
        self.save('characters', {'characters': {'PER-001': {'name': 'Ada', 'organization_ids': ['ORG-404']}}})
        self.save('military', {'navy': {'ships': [{'id': 'SHIP-001', 'name': 'Fartyg'}]}})
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.report()['article_count'], 2)
        self.assertTrue(any('ORG-404' in w for w in self.report()['warnings']))

    def test_html_and_script_payloads_are_inert(self):
        self.save('characters', [{'id': '../../evil', 'name': '<script>alert(1)</script>',
                                  'description': '</script><img src=x onerror=alert(2)>'}])
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        for p in self.out.rglob('*.html'):
            text = p.read_text(encoding='utf-8')
            self.assertNotIn('<img src=x', text)
            self.assertNotIn('<script>alert', text)
        self.assertFalse((self.base / 'evil.html').exists())
        search = (self.out / 'assets' / 'search-index.js').read_text(encoding='utf-8')
        self.assertNotIn('</script>', search)

    def test_invalid_json_fails_before_writing_output(self):
        (self.source / 'characters.json').write_text('{bad', encoding='utf-8')
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn('characters.json', result.stderr)
        self.assertFalse(self.out.exists())

    def test_duplicate_ids_fail(self):
        self.save('characters', [{'id': 'X-1', 'name': 'A'}, {'id': 'X-1', 'name': 'B'}])
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn('Dubblerat artikel-ID', result.stderr)
        self.assertFalse(self.out.exists())

    def test_missing_files_and_record_id_are_reported(self):
        self.save('characters', [{'name': 'Okänd person', 'age': None}])
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.report()['article_count'], 1)
        self.assertIn('manifest.json', self.report()['missing_files'])
        self.assertTrue(any('ID' in w for w in self.report()['warnings']))

    def test_strict_warnings_stop_output(self):
        self.save('characters', [])
        self.assertEqual(self.run_cli('--strict').returncode, 2)
        self.assertFalse(self.out.exists())

    def test_refuses_nonempty_output_and_overlapping_paths(self):
        self.save('characters', [])
        self.out.mkdir()
        (self.out / 'keep.txt').write_text('keep')
        self.assertEqual(self.run_cli().returncode, 2)
        self.assertEqual((self.out / 'keep.txt').read_text(), 'keep')
        self.out = self.source / 'wiki'
        self.assertEqual(self.run_cli().returncode, 2)
        self.assertFalse(self.out.exists())

    def test_timeline_orders_iso_dates_and_references_existing_articles(self):
        self.save('events', [{'id': 'EVT-2', 'title': 'Senare', 'date': '2030-02-01'},
                             {'id': 'EVT-1', 'title': 'Tidigare', 'date': '2029-12-31'}])
        self.save('timeline', [{'date': '2030-02-01', 'event_id': 'EVT-2'},
                               {'title': 'Utan datum'}, {'date': '1 mars 2030', 'title': 'Textdatum'}])
        self.assertEqual(self.run_cli().returncode, 0)
        page = (self.out / 'timeline.html').read_text(encoding='utf-8')
        self.assertLess(page.index('2029-12-31'), page.index('2030-02-01'))
        self.assertIn('Utan datum', page)
        self.assertIn('Textdatum', page)

    def test_empty_source_fails(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn('Inga av de 18', result.stderr)
        self.assertFalse(self.out.exists())

    def test_alias_id_without_title_and_with_nested_fields_is_an_article(self):
        self.save('characters', [{'character_id': 'PER-7', 'organization_ids': ['ORG-1']}])
        self.save('organizations', [{'id': 'ORG-1', 'name': 'Test'}])
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.report()['article_count'], 2)

    def test_supplementary_ids_link_to_real_source_anchors(self):
        self.save('characters', [{'id': 'PER-1', 'rule_ids': ['RULE-1']}])
        self.save('rules', {'rules': [{'id': 'RULE-1', 'description': 'Testregel'}]})
        self.assertEqual(self.run_cli().returncode, 0)
        page = next((self.out / 'articles' / 'personer').glob('*.html'))
        links = Links()
        links.feed(page.read_text(encoding='utf-8'))
        target = next(x for x in links.links if 'rules.html#' in x)
        source_page = Links()
        source_page.feed((page.parent / target.split('#')[0]).read_text(encoding='utf-8'))
        self.assertIn(target.split('#')[1], source_page.ids)

    def test_duplicate_json_keys_and_nan_are_rejected(self):
        for raw in ['{"id":"A", "id":"B"}', '[{"id":"A", "value":NaN}]']:
            with self.subTest(raw=raw):
                (self.source / 'characters.json').write_text(raw, encoding='utf-8')
                result = self.run_cli()
                self.assertEqual(result.returncode, 2)
                self.assertIn('characters.json', result.stderr)
                self.assertFalse(self.out.exists())

    def test_wiki_index_links_canonical_target_without_creating_facts(self):
        self.save('characters', [{'id': 'PER-1', 'name': 'Verifierat namn'}])
        self.save('wiki_index', {'articles': [{'id': 'WIKI-1', 'title': 'Alternativ rubrik',
                                               'entity_id': 'PER-1'}]})
        self.assertEqual(self.run_cli().returncode, 0)
        self.assertEqual(self.report()['article_count'], 1)
        source = (self.out / 'sources' / 'wiki_index.html').read_text(encoding='utf-8')
        self.assertIn('../articles/personer/', source)
        article = next((self.out / 'articles' / 'personer').glob('*.html')).read_text(encoding='utf-8')
        self.assertIn('Alternativ rubrik', article)

    def test_non_string_id_fails(self):
        self.save('characters', [{'id': 3, 'name': 'Test'}])
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn('ID måste vara', result.stderr)

    def test_invalid_root_fails(self):
        self.save('characters', 'not a collection')
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn('roten måste vara', result.stderr)

    def test_rerun_does_not_replace_existing_wiki(self):
        self.save('characters', [{'id': 'PER-1', 'name': 'Första'}])
        self.assertEqual(self.run_cli().returncode, 0)
        before = (self.out / 'index.html').read_bytes()
        self.save('characters', [{'id': 'PER-1', 'name': 'Andra'}])
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn('ny eller tom', result.stderr)
        self.assertEqual((self.out / 'index.html').read_bytes(), before)

    def test_container_references_are_checked_and_linked(self):
        self.save('characters', {'characters': [{'id': 'PER-1', 'name': 'A'}],
                                 'leader_id': 'PER-MISSING'})
        self.save('organizations', {'organizations': [{'id': 'ORG-1', 'name': 'B'}],
                                    'contact_id': 'PER-1'})
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(any('PER-MISSING' in w for w in self.report()['warnings']))
        person = next((self.out / 'articles' / 'personer').glob('*.html')).read_text(encoding='utf-8')
        self.assertIn('organizations.html', person)


if __name__ == '__main__':
    unittest.main()
