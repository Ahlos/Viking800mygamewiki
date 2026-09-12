/* Classic script: works offline with file:// and never inserts data as HTML. */
(function () {
  'use strict';
  function normalize(value) {
    return String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('sv');
  }
  function search(index, query, category) {
    const terms = normalize(query).trim().split(/\s+/).filter(Boolean);
    return index.filter(item => (!category || item.category === category) &&
      terms.every(term => normalize(item.title + ' ' + item.id + ' ' + item.text).includes(term)))
      .sort((a, b) => {
        const exact = item => normalize(item.title) === normalize(query) || normalize(item.id) === normalize(query);
        return Number(exact(b)) - Number(exact(a)) || a.title.localeCompare(b.title, 'sv');
      });
  }
  // The exported pure search function is also used by the offline verification test.
  if (typeof module !== 'undefined' && module.exports) module.exports = {search, normalize};
  if (typeof document === 'undefined') return;
  const form = document.getElementById('search-form');
  if (!form) return;
  const input = document.getElementById('query');
  const filter = document.getElementById('category-filter');
  const results = document.getElementById('results');
  const status = document.getElementById('result-count');
  const more = document.getElementById('more-results');
  let matches = [], shown = 0;
  function appendPage() {
    const end = Math.min(shown + 50, matches.length);
    for (; shown < end; shown++) {
      const item = matches[shown];
      const li = document.createElement('li');
      const link = document.createElement('a');
      link.href = item.url;
      link.textContent = item.title;
      const meta = document.createElement('small');
      meta.textContent = item.category + ' · ' + item.id;
      const excerpt = document.createElement('p');
      excerpt.textContent = item.text.slice(0, 220) + (item.text.length > 220 ? '…' : '');
      li.append(link, meta, excerpt);
      results.appendChild(li);
    }
    more.hidden = shown >= matches.length;
    status.textContent = matches.length ? matches.length + ' träffar. Visar ' + shown + '.' : 'Inga träffar. Prova ett annat namn, ID eller sökord.';
  }
  function render() {
    results.replaceChildren();
    shown = 0;
    matches = search(window.STATWIKI_INDEX || [], input.value, filter.value);
    appendPage();
  }
  input.value = new URLSearchParams(window.location.search).get('q') || '';
  form.addEventListener('submit', event => { event.preventDefault(); render(); });
  input.addEventListener('input', render);
  filter.addEventListener('change', render);
  more.addEventListener('click', appendPage);
  render();
})();
