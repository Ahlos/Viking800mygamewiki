/* Optional developer check: node tests/test_search.cjs (Node is not needed to run the generator). */
const assert = require('node:assert/strict');
const { search } = require('../statwiki/assets/search.js');
const index = [
  {title:'Åsa Öberg', id:'PER-1', category:'Personer', text:'Hamnstaden forskare'},
  {title:'Hamnstaden', id:'LOC-1', category:'Platser', text:'Åsa bor här'},
  {title:'Forskning', id:'PRO-1', category:'Projekt', text:'Öberg ansvarar'},
];
assert.deepEqual(search(index, 'asa oberg', '').map(x=>x.id), ['PER-1']);
assert.deepEqual(search(index, 'PER-1', '').map(x=>x.id), ['PER-1']);
assert.deepEqual(search(index, 'hamnstaden', 'Platser').map(x=>x.id), ['LOC-1']);
assert.deepEqual(search(index, 'finnsinte', ''), []);
assert.equal(search(index, '', '').length, 3);
assert.equal(search(index, 'Hamnstaden', '')[0].id, 'LOC-1');
assert.deepEqual(search(index, '<script>', ''), []);
console.log('7 search checks passed.');
