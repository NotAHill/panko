'use strict';
/* Panko hub: one page over /api. No build step. Everything that comes from entries, sources or shared decks goes
   through `html` (escaped); card previews render in sandboxed iframes. */

// ---- helpers ------------------------------------------------------------------------------------------------------
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ESC[c]);
class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
const show = v => v == null || v === false ? '' : v instanceof Raw ? v.s : Array.isArray(v) ? v.map(show).join('') : esc(v);
const html = (strs, ...vals) => new Raw(strs.reduce((o, s, i) => o + s + (i < vals.length ? show(vals[i]) : ''), ''));
const put = (el, v) => { el.innerHTML = show(v); addHints(el); folds(el); return el; };
/* a box that folds (<details class="box" data-fold="key">) starts closed and stays as you left it while the page redraws */
const FOLD = {};
const folds = el => { for (const d of el.querySelectorAll?.('details[data-fold]') || []) { d.open = !!FOLD[d.dataset.fold]; d.ontoggle = () => { FOLD[d.dataset.fold] = d.open; }; } };
const n = x => (x ?? 0).toLocaleString('en');
const usd = x => { const v = +x || 0; return v && Math.abs(v) < 0.005 ? '<$0.01' : '$' + v.toFixed(2); };
const plural = (k, one, many) => `${n(k)} ${k === 1 ? one : (many || one + 's')}`;
const tilde = p => String(p || '').replace(/(^|[\s'"`(])\/(Users|home)\/[^/\s]+/g, '$1~');
const when = t => { if (!t) return ''; const d = new Date(typeof t === 'number' ? t * 1000 : t); return isNaN(d) ? String(t) : d.toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' }); };
const ago = t => { const s = Math.max(0, Date.now() / 1000 - t); return s < 60 ? `${s | 0}s` : s < 3600 ? `${(s / 60) | 0}m` : `${(s / 3600).toFixed(1)}h`; };
const dur = (a, b) => { if (!a) return ''; const s = (b || Date.now() / 1000) - a; return s < 60 ? `${s.toFixed(1)}s` : `${(s / 60) | 0}m ${(s % 60) | 0}s`; };
const SPIN = ['✢', '✳', '✶', '✻', '✽', '✻', '✶', '✳'];
const loading = (what = 'loading') => html`<div class="loading"><span class="spin">✻</span> ${what}…</div>`;
const ticks = t => html`${String(t || '').split('`').map((p, i) => i % 2 ? html`<code>${p}</code>` : p)}`;
const errorBox = e => html`<p class="err">${e.message || e}</p>`;
const bar = (frac, w = 20, cls = '') => {
  const pct = Math.max(0, Math.min(100, (frac || 0) * 100));
  return html`<span class="meter ${cls}" style="--w:${w}" role="img" aria-label="${Math.round(pct)}%"><i style="width:${pct.toFixed(1)}%"></i></span>`;
};
const ICON = {
  overview: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  cards: '<rect x="2" y="7" width="15" height="14" rx="2"/><path d="M7 3h13a2 2 0 0 1 2 2v12"/>',
  library: '<path d="M4 4h3v16H4z"/><path d="M9 4h3v16H9z"/><path d="m14.5 5.2 2.9-.8 3.9 14.6-2.9.8z"/>',
  sources: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/>',
  checks: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
  pictures: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
  sync: '<path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"/><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M21 3v5h-5"/><path d="M3 21v-5h5"/>',
  usage: '<path d="M3 3v18h18"/><path d="M8 17v-5"/><path d="M13 17V8"/><path d="M18 17V11"/>',
  jobs: '<path d="m4 17 6-6-6-6"/><path d="M12 19h8"/>',
  setup: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  anki: '<path d="M20 6 9 17l-5-5"/>',
  doubt: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  spend: '<path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
};
ICON.design = '<path d="M12 3a9 9 0 1 0 0 18c.9 0 1.5-.7 1.5-1.5 0-.4-.2-.8-.4-1.1-.3-.3-.4-.6-.4-1 0-.8.7-1.5 1.5-1.5H16a5 5 0 0 0 5-5c0-4.4-4-7.9-9-7.9z"/><circle cx="7.5" cy="10.5" r="1"/><circle cx="12" cy="7.5" r="1"/><circle cx="16.5" cy="10.5" r="1"/>';
ICON.voices = '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5M8 22h8"/>';
ICON.play = '<path d="M7 4v16l13-8z"/>';
ICON.stop = '<rect x="6" y="6" width="12" height="12" rx="1"/>';
const icon = name => new Raw(`<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICON[name] || ''}</svg>`);
const LOGO = [
  '██████   █████  ███    ██ ██   ██  ██████ ',
  '██   ██ ██   ██ ████   ██ ██  ██  ██    ██',
  '██████  ███████ ██ ██  ██ █████   ██    ██',
  '██      ██   ██ ██  ██ ██ ██  ██  ██    ██',
  '██      ██   ██ ██   ████ ██   ██  ██████ '].join('\n');

const S = { meta: null, ov: null, spend: null, jobs: [], watch: new Map(), route: null, keys: null, cleanup: null };

async function api(path, opts = {}) {
  const init = { method: opts.method || (opts.body !== undefined ? 'POST' : 'GET'), headers: { 'X-Panko': '1' } };
  if (opts.body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(opts.body); }
  if (opts.form) { init.method = 'POST'; init.body = opts.form; }
  const r = await fetch('/api' + path, init);
  let d, json = true; try { d = await r.json(); } catch { json = false; d = { error: `${r.status} ${r.statusText}` }; }
  if (!r.ok) {
    // A route the server doesn't know (not one of its own JSON errors): the page is newer than the running hub.
    if (r.status === 404 && !json) d.error = 'This page needs a newer hub than the one running. Stop panko hub in its terminal (Ctrl-C) and start it again.';
    const e = new Error(d.error || r.statusText); e.status = r.status; if (r.status === 401) locked(); throw e; }
  return d;
}

function locked() {
  put($('#view'), html`<section class="box bad"><div class="t">locked</div><p>This tab lost its key. Open the hub again
    from the link <code>panko hub</code> printed in your terminal.</p></section>`);
}

const V = name => S.meta?.varieties?.find(v => v.name === name) || { name, title: name || '', rtl: false, font: '' };
const tgt = (text, variety, cls = '') => html`<span class="tgt ${cls}" dir="auto" style="--tgt:${V(variety).font || 'system-ui'}">${text}</span>`;

// ---- toasts, dialogs, palette -------------------------------------------------------------------------------------
document.addEventListener('click', e => { const b = e.target.closest('[data-undo]'); if (b) { b.closest('.toast')?.remove(); S.undoNone?.(b.dataset.undo.split(',')); } });

/* A ? beside a box's title saying what the box is for, on hover or focus. Keyed by the title's first words. */
const HINTS = {
  'card': 'The card as Anki will show it. Click it or press space to flip; a word can make several cards (meaning to word, word to meaning…).',
  'entry': 'What Panko keeps for this word. Edit changes it here; the next sync updates the note in Anki.',
  'how it was checked': 'When a word comes in, the model compares it with your references and its own knowledge, and free tools check the spelling. "Looks right" means nothing needs doing.',
  'references': 'Dictionaries and word lists that have this word, and cards you already have that look alike, so you can spot a duplicate before activating.',
  'sources': 'Where this word came from, and what was said there. When two sources disagree, the one you trust more wins.',
  'duplicates': 'The same word came in more than once. The copies point here, so this is the one card you study.',
  'duplicate': 'The same word came in twice; this copy was folded into the card you keep, so you never study it twice.',
  'rejected': 'Words you said no to. They stay here so Panko remembers: if a source has one again, it doesn’t come back to your inbox.',
  'your sources': 'What you have added to read. Open one to read its units and send new words to the inbox.',
  'where your cards came from': 'Sources added before the reading queue existed. Open one to see its cards.',
  'reading in chat': 'Your own Claude reads the units with Panko’s tools instead of the API, so nothing is spent here.',
  'units': 'A source is split into units: a page, a few minutes of audio, or 25 rows of a deck. Each is read once; its new words go to the inbox.',
  'held': 'Words in this unit that look like cards you already have. Say whether each is the same word or a different one.',
  'tool checks': 'Free, no model: an analyser checks spelling and roots where your language has one; otherwise words are looked up in your references. A problem holds a card in the inbox as doubtful.',
  'gloss clashes': 'A production card shows the meaning and asks for the word, so two cards with the same meaning can’t both be answered. For each card: keep it, give it a sharper gloss, make it recognition only, or mark it as the same word as another (an inbox card then moves to duplicates). Nothing changes until you apply.',
  'to do': 'Cards without a picture or a decision about one.',
  'waiting for a picture': 'Active cards with no picture yet. Prayers, grammar words and the like are often better without one: mark those “no picture”.',
  'library': 'Ready-made decks, checked and with pictures. Adding one goes through the same checks as any source: words you have keep your card, near ones wait for you, new ones land in your inbox.',
  'decisions': 'What the model chose for each card: a photo, a drawing to make, or no picture. Apply puts them on the cards.',
  'cards': 'How many words each variety has, and how many of them are already in Anki.',
  "what's next": 'Things waiting for you, oldest first.',
  'running': 'Long or paid steps run one at a time in the background.',
  'plan': 'A dry run: what a sync would add, change and pay for. It needs no Anki and costs nothing.',
  'before you sync': 'Sync writes only Panko’s own notes and decks. Your review history and MyNotes field are never touched.',
  'share as a file': 'Built in a scratch collection, never your own. Notes keep the same ids from one package to the next, so a friend who imports a newer one gets updates, not copies.',
  'back of the card': 'Which sections the back shows and in what order. Template changes go through a normal sync, never a full one.',
  'fronts': 'Which kinds of card each word makes. Every kind is its own card in Anki.',
  'your own sections': 'Extra sections you fill in per card, such as a mnemonic or a culture note.',
  'type and size': 'Fonts and sizes on your cards, for both scripts.',
  'pictures': 'Where pictures come from, in order, and whether Panko may draw one when no photo fits.',
  "what's ready": 'What this Panko folder can do right now: keys, Anki, reference data and chat mode.',
  'reference data': 'Dictionaries and word lists checks look words up in. The open ones download for free.',
  'chat mode': 'Use Panko from your own Claude, so reading sources costs nothing here.',
  'how panko reads': 'Two ways to do the model’s work: chat mode (your own Claude uses Panko’s tools, on your subscription) or API mode (Panko calls the model with your key, paid and priced first). You can have both; the bar at the bottom shows which is in use.',
  'your language': 'What this Panko folder teaches. Everything about the language comes from here.',
  'this month': 'Spend on the language model this month. Each paid step is priced before it runs.',
};
function addHints(root) {
  for (const t of root.querySelectorAll?.('.box > .t') || []) {
    if (t.querySelector('.q')) continue;
    const key = (t.firstChild?.textContent || '').trim().toLowerCase();
    const tip = HINTS[key];
    if (!tip) continue;
    const q = document.createElement('span');
    q.className = 'q'; q.tabIndex = 0; q.textContent = '?'; q.onclick = e => e.preventDefault();   // in a fold's title it mustn't fold it
     q.setAttribute('role', 'note'); q.dataset.tip = tip; q.setAttribute('aria-label', tip);
    t.append(q);
  }
}

/* the hint itself floats above everything, so a box's edge never cuts it off */
const tipShow = q => {
  let t = $('#tip');
  if (!t) { t = document.createElement('div'); t.id = 'tip'; t.setAttribute('role', 'tooltip'); document.body.append(t); }
  t.textContent = q.dataset.tip; t.hidden = false;
  const r = q.getBoundingClientRect(), w = t.offsetWidth, h = t.offsetHeight;
  const below = r.bottom + 8 + h < innerHeight;
  t.style.top = (below ? r.bottom + 8 : r.top - 8 - h) + 'px';
  t.style.left = Math.max(12, Math.min(innerWidth - w - 12, r.left - 8)) + 'px';
};
const tipHide = () => { const t = $('#tip'); if (t) t.hidden = true; };
document.addEventListener('mouseover', e => { const q = e.target.closest?.('[data-tip]'); if (q) tipShow(q); });
document.addEventListener('mouseout', e => { if (e.target.closest?.('[data-tip]')) tipHide(); });
document.addEventListener('focusin', e => { if (e.target.matches?.('[data-tip]')) tipShow(e.target); });
document.addEventListener('focusout', tipHide);
addEventListener('hashchange', tipHide);

function toast(msg, kind = '', ms = 6000) {
  const t = document.createElement('div');
  t.className = 'toast ' + kind;
  if (kind === 'bad') t.setAttribute('role', 'alert');
  put(t, html`<button class="ghost x" aria-label="dismiss">×</button>${msg}`);
  $('.x', t).onclick = () => t.remove();
  $('#toasts').append(t);
  if (ms) setTimeout(() => t.remove(), ms);
}

/* A choice in the style of a terminal permission prompt. options: [{label, value: L => result}] (no value = cancel). */
function ask({ title, body = '', question = 'Do you want to proceed?', options, hint = '↑↓ to choose, enter to confirm, esc to cancel' }) {
  return new Promise(resolve => {
    const L = $('#layer');
    let cur = 0;
    const before = document.activeElement;
    put(L, html`<div class="back"><div class="box modal" role="dialog" aria-modal="true" aria-labelledby="dlg-t" tabindex="-1"><div class="t" id="dlg-t">${title}</div>
      ${body}<div class="q" id="dlg-q">${question}</div>
      <ol class="opts" role="listbox" aria-labelledby="dlg-q">${options.map((o, i) => html`<li data-i="${i}" role="option" aria-selected="false"><span class="n">${i + 1}.</span> ${o.label}</li>`)}</ol>
      <div class="hint">${hint}</div></div></div>`);
    const lis = $$('.opts li', L);
    const paint = () => lis.forEach((li, i) => { li.classList.toggle('on', i === cur); li.setAttribute('aria-selected', i === cur); });
    const done = v => { document.removeEventListener('keydown', key, true); L.innerHTML = ''; before?.focus?.(); resolve(v); };
    const pick = i => done(options[i].value ? options[i].value(L) : null);
    const key = e => {
      const inInput = e.target.tagName === 'INPUT';
      if (e.key === 'Escape') { e.preventDefault(); done(null); }
      else if (e.key === 'ArrowDown' || (!inInput && e.key === 'j')) { cur = (cur + 1) % lis.length; paint(); e.preventDefault(); }
      else if (e.key === 'ArrowUp' || (!inInput && e.key === 'k')) { cur = (cur - 1 + lis.length) % lis.length; paint(); e.preventDefault(); }
      else if (e.key === 'Enter') { e.preventDefault(); pick(cur); }
      else if (!inInput && /^[1-9]$/.test(e.key) && +e.key <= lis.length) { e.preventDefault(); pick(+e.key - 1); }
      else return;
      e.stopPropagation();
    };
    document.addEventListener('keydown', key, true);
    lis.forEach((li, i) => {
      li.onmouseenter = () => { cur = i; paint(); };
      li.onclick = ev => { if (ev.target.tagName !== 'INPUT') pick(i); };
    });
    $('.back', L).onclick = ev => { if (ev.target.classList.contains('back')) done(null); };
    paint();
    $('.modal', L).focus({ preventScroll: true });
  });
}

const confirmIt = (title, body, yes = 'Yes') => ask({ title, body, options: [{ label: yes, value: () => true }, { label: 'No' }] });

const EST_NAMES = { usd: 'estimate', usd_batch: 'as a batch', extract_usd: 'reading', check_and_pictures_usd: 'checks and picture plans',
  units: 'units', entries: 'entries', cards: 'cards', groups: 'groups', model: 'model', clips: 'audio clips',
  characters: 'characters', minutes: 'minutes', tracks: 'tracks', sheets: 'contact sheets', unplanned: 'without a plan yet' };
function estRows(est) {
  return Object.entries(est).filter(([, v]) => v !== null && v !== '' && typeof v !== 'object' || Array.isArray(v)).map(([k, v]) =>
    html`<span class="k">${EST_NAMES[k] || k.replace(/_/g, ' ')}</span><span class="v ${k === 'usd' ? 'acc' : ''}">${
      /usd/.test(k) ? usd(v) : Array.isArray(v) ? `${v.length}${v.length ? ': ' + v.slice(0, 8).join(', ') + (v.length > 8 ? '…' : '') : ''}` : typeof v === 'number' ? n(v) : v}</span>`);
}
const nothing = est => ['units', 'entries', 'cards', 'groups', 'clips', 'tracks'].some(k => k in est && (Array.isArray(est[k]) ? !est[k].length : !est[k]));

async function paid(title, est, { batch = true } = {}) {
  const body = html`<div class="kv">${estRows(est)}</div>`;
  if (est.usd == null) return ask({ title, body, options: [{ label: 'Yes, go ahead (paid)', value: () => ({}) }, { label: 'No' }] });
  const def = Math.max(0.05, Math.ceil(est.usd * 1.5 * 100) / 100);
  const budget = L => parseFloat($('#bud', L).value) || def;
  const opts = [{ label: html`Yes, spend up to $<input id="bud" inputmode="decimal" value="${def.toFixed(2)}" aria-label="budget in dollars">`,
    value: L => ({ batch: false, budget: budget(L) }) }];
  if (batch && est.usd_batch != null) opts.push({ label: html`Yes, as a batch: about ${usd(est.usd_batch)}, answers within 24 h`,
    value: L => ({ batch: true, budget: budget(L) }) });
  opts.push({ label: 'No' });
  return ask({ title, body, options: opts, hint: 'Panko stops before going over the budget. Esc cancels.' });
}

/* Estimate → ask → run as a job. */
async function paidAction(path, body, title, { batch = true, onDone } = {}) {
  try {
    const r = await api(path, { body });
    const est = r.estimate;
    if (!est) return r;
    if (nothing(est)) return toast('Nothing to do.');
    const ans = await paid(title, est, { batch });
    if (!ans) return;
    const j = await api(path, { body: { ...body, ...ans, confirm: true } });
    watch(j.job, onDone);
  } catch (e) { toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); }
}

function watch(job, onDone) {
  S.watch.set(job.id, onDone || null);
  toast(html`<span class="acc">✻</span> started ${job.title} <a href="#/jobs/${job.id}">see the log</a>`, '', 4000);
  pollJobs();
}

async function startJob(path, body = {}, onDone) {
  try { const r = await api(path, { body }); watch(r.job, onDone); return r.job; }
  catch (e) { toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); }
}

const COMMANDS = [
  ['/overview', 'what needs doing', () => go('#/')],
  ['/inbox', 'candidates waiting to become cards', () => go('#/inbox')],
  ['/doubtful', 'candidates a check held back', () => go('#/cards?status=candidate&flag=doubtful')],
  ['/cards', 'every active card', () => go('#/cards?status=active')],
  ['/tags', 'cards by tag', () => go('#/cards?status=all&tag=')],
  ['/sources', 'what you learn from', () => go('#/sources')],
  ['/add', 'add a source', () => go('#/sources?add=1')],
  ['/library', 'ready-made decks to add to yours', () => go('#/library')],
  ['/checks', 'tool checks and gloss clashes', () => go('#/checks')],
  ['/verify', 'run the free tool checks on the inbox', () => startJob('/verify', { status: 'candidate' })],
  ['/pictures', 'pictures for cards without one', () => go('#/pictures')],
  ['/design', 'how your cards look, and where pictures come from', () => go('#/design')],
  ['/voices', 'the voices that read your cards', () => go('#/voices')],
  ['/sync', 'what a sync would change, then sync', () => go('#/sync')],
  ['/plan', 'check what a sync would do (free)', () => { go('#/sync'); setTimeout(() => $('[data-a=plan]')?.click(), 300); }],
  ['/usage', 'spend by day, task and model', () => go('#/usage')],
  ['/collect', 'save the answers of finished batches', () => startJob('/llm/collect')],
  ['/jobs', 'background steps and their logs', () => go('#/jobs')],
  ['/setup', 'config and chat mode', () => go('#/setup')],
  ['/tour', 'a walk through the hub', () => tour()],
  ['/theme', 'light or dark', () => toggleTheme()],
  ['/keys', 'keyboard shortcuts', () => keysHelp()],
];

function palette(initial = '') {
  const L = $('#layer');
  let cur = 0, items = [], moved = false;
  put(L, html`<div class="back"><div class="palette" role="dialog" aria-label="commands">
    <label class="prompt"><input id="pal" placeholder="type a command, or words to search your cards" autocomplete="off" spellcheck="false"></label>
    <ul id="pal-list"></ul></div></div>`);
  const input = $('#pal', L), list = $('#pal-list', L);
  const close = () => { L.innerHTML = ''; };
  const paint = () => {
    const q = input.value.trim();
    const cmds = COMMANDS.filter(c => !q || c[0].includes(q.toLowerCase().replace(/^\/?/, '/')) || c[1].includes(q.toLowerCase()));
    items = [...cmds];
    if (q && !q.startsWith('/')) {
      if (/^[a-z]{2}-\d{3,}$/i.test(q)) items.unshift([q, 'open this card', () => go(`#/cards/${q.toLowerCase()}`)]);
      items.unshift([`search`, `cards matching “${q}”`, () => go(`#/cards?status=all&q=${encodeURIComponent(q)}`)]);
    }
    cur = Math.min(cur, Math.max(0, items.length - 1));
    put(list, items.length ? items.map((c, i) => html`<li data-i="${i}" class="${i === cur ? 'on' : ''}"><span class="c">${c[0]}</span><span>${c[1]}</span></li>`)
      : html`<li><span class="c">∅</span><span>no command matches</span></li>`);
    $$('li[data-i]', list).forEach(li => { li.onclick = () => run(+li.dataset.i); li.onmouseenter = () => { if (moved) { cur = +li.dataset.i; paint(); } }; });
    list.querySelector('.on')?.scrollIntoView({ block: 'nearest' });
  };
  const run = i => { const c = items[i]; close(); c && c[2](); };
  list.onmousemove = () => { moved = true; };
  input.oninput = () => { cur = 0; paint(); };
  input.onkeydown = e => {
    if (e.key === 'Escape') { e.preventDefault(); close(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); cur = (cur + 1) % Math.max(1, items.length); paint(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); cur = (cur - 1 + items.length) % Math.max(1, items.length); paint(); }
    else if (e.key === 'Enter') { e.preventDefault(); run(cur); }
    e.stopPropagation();
  };
  $('.back', L).onclick = ev => { if (ev.target.classList.contains('back')) close(); };
  input.value = initial;
  paint();
  input.focus();
}

function keysHelp() {
  const rows = [['/', 'commands and search'], ['g o', 'overview'], ['g i', 'inbox'], ['g c', 'cards'], ['g s', 'sources'],
    ['g k', 'checks'], ['g p', 'pictures'], ['g d', 'card design'], ['g v', 'voices'], ['g y', 'sync'], ['g u', 'usage'], ['g j', 'jobs'], ['g ,', 'setup'], ['t', 'light or dark'],
    ['j k ↑ ↓', 'move in a list'], ['enter', 'open the card'], ['x', 'select'], ['a', 'activate'], ['r', 'reject'],
    ['u', 'back to the inbox'], ['e', 'edit'], ['space', 'flip the card'], ['[ ]', 'other card of the note'], ['s', 'search'],
    ['n p', 'next or previous page'], ['⌘ enter', 'save an edit'], ['esc', 'close, clear']];
  ask({ title: 'keyboard', body: html`<div class="keys">${rows.map(([k, d]) => html`<div><span>${k.split(' ').map(x => html`<kbd>${x}</kbd> `)}</span><span class="dim">${d}</span></div>`)}</div>`,
    question: '', options: [{ label: 'Close' }, { label: 'Show me around the hub', value: () => 'tour' }], hint: 'esc closes' })
    .then(v => { if (v === 'tour') tour(); });
}

function toggleTheme() {
  const cur = document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('panko-theme', next); } catch (e) { /* private window */ }
  $$('iframe.pv').forEach(f => { if (f.dataset.src) loadPv(f, f.dataset.src.replace(/theme=\w*/, 'theme=' + next)); });
  S.onTheme?.();
}
const theme = () => document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');

// ---- frame: nav, status line, jobs polling -----------------------------------------------------------------------
const NAV = ['learn', ['overview', 'o'], ['inbox', 'i'], ['cards', 'c'], ['sources', 's'], ['library', 'l'], 'tools', ['checks', 'k'], ['pictures', 'p'],
  ['sync', 'y'], 'your cards', ['design', 'd'], ['voices', 'v'], 'system', ['usage', 'u'], ['jobs', 'j'], ['setup', ',']];

function navName() {
  const r = S.route;
  if (!r) return '';
  if (r.name === 'cards' && (r.q.status || 'active') === 'candidate') return 'inbox';
  return r.name;
}

function paintNav() {
  const on = navName();
  const c = S.ov ? Object.values(S.ov.counts) : [];
  const inbox = c.reduce((a, x) => a + (x.candidate || 0), 0);
  const busy = S.jobs.filter(j => j.status === 'running' || j.status === 'queued').length;
  const cnt = { inbox: inbox ? html`<span class="cnt hot">${n(inbox)}</span>` : '', jobs: busy ? html`<span class="cnt hot"><span class="spin">✻</span>${busy}</span>` : '' };
  const out = show(NAV.map(x => typeof x === 'string' ? html`<div class="grp">${x}</div>`
    : html`<a href="#/${x[0] === 'overview' ? '' : x[0]}" class="${on === x[0] ? 'on' : ''}"${on === x[0] ? new Raw(' aria-current="page"') : ''}>${icon(x[0])}${x[0][0].toUpperCase() + x[0].slice(1)}${cnt[x[0]] || ''}<span class="key">g ${x[1]}</span></a>`))
    + show(html`<div class="foot"><button class="link" data-tour>show me around</button></div>`);
  if (out !== S.navHTML) { S.navHTML = out; $('#nav').innerHTML = out; }
}

const learning = m => {
  const t = (m.varieties || []).map(v => v.title);
  return t.length ? 'learning ' + (t.length > 1 ? t.slice(0, -1).join(', ') + ' and ' + t.at(-1) : t[0]) : (m.language || '');
};

/* Which way the model's work is done: chat mode (your Claude, through Panko's tools; free here) or API mode (Panko
   calls the model with your key; paid, always priced first). Chat counts as connected for a while after its last call. */
const since = s => s < 90 ? 'just now' : s < 5400 ? `${Math.round(s / 60)} min ago` : s < 172800 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} days ago`;
function modeInfo(md) {
  if (!md) return null;
  const c = md.chat, a = md.api;
  const chat = c.active ? `Chat mode: your Claude used Panko’s tools ${since(c.ago)}. Reading and deciding there costs nothing here.`
    : c.last ? `Chat mode: last used ${since(c.ago)}.` : 'Chat mode: not used yet. Connect your Claude with the snippet under setup → chat mode.';
  const api = a.ready ? `API mode: ready (${a.model || a.provider}). Paid steps here use your key, and always show the price first.`
    : 'API mode: no key, so paid steps are off.';
  const [cls, label] = c.active ? ['chat', a.ready ? 'chat mode · API key set' : 'chat mode']
    : a.ready ? ['api', 'API mode · paid'] : ['none', 'no model connected'];
  return { cls, label, chat, api, tip: chat + '\n' + api };
}
const modeBadge = () => { const i = modeInfo(S.ov?.modes); return i ? html`<a href="#/setup" class="mode ${i.cls}" data-tip="${i.tip}" aria-label="${i.tip}"><span class="dot"></span>${i.label}</a>` : ''; };

function paintStatus() {
  const m = S.meta || {};
  const run = S.jobs.find(j => j.status === 'running');
  const q = S.jobs.filter(j => j.status === 'queued').length;
  put($('#status'), html`<span>${m.config ? m.language || 'set up' : 'not set up yet'}</span><span class="path">${m.hosted ? '' : tilde(m.root)}</span>
    ${run ? html`<a class="job" href="#/jobs/${run.id}"><span class="spin">✻</span> ${run.title}… ${dur(run.started)}${q ? `, ${q} queued` : ''}</a>` : ''}
    <span class="grow"></span>${modeBadge()}${S.spend != null ? html`<a href="#/usage" class="dim">${usd(S.spend)} this month</a>` : ''}<span class="kbd-hint"><kbd>?</kbd> keys</span>`);
  put($('#top-meta'), html`${m.config ? learning(m) : html`<a href="#/setup">set up</a>`}${m.hosted ? html` · <a href="/host/account" title="your account: password, download your data, sign out">account</a>` : ''}`);
}

async function refreshCounts() {
  if (!S.meta?.config) return;
  try { S.ov = await api('/overview'); S.spend = S.ov.spend.month; paintNav(); paintStatus(); paintRows(); } catch (e) { /* shown elsewhere */ }
}

async function pollJobs() {
  clearTimeout(S.pollT);
  try {
    const { jobs } = await api('/jobs');
    const prev = new Map(S.jobs.map(j => [j.id, j.status]));
    S.jobs = jobs;
    let changed = false;
    for (const j of jobs) {
      const was = prev.get(j.id), over = ['done', 'failed', 'cancelled'].includes(j.status);
      if (!over || !(S.watch.has(j.id) || (was && !['done', 'failed', 'cancelled'].includes(was)))) continue;
      changed = true;
      const cb = S.watch.get(j.id);
      S.watch.delete(j.id);
      if (j.status === 'done') toast(html`<span class="ok">✔</span> ${j.title}${j.log.length ? html`<div class="dim">${j.log[j.log.length - 1]}</div>` : ''}`, 'ok', 9000);
      else if (j.status === 'failed') toast(html`<span class="bad">✘</span> ${j.title} failed: ${j.error} <a href="#/jobs/${j.id}">see the log</a>`, 'bad', 0);
      if (cb) { try { cb(await api(`/jobs/${j.id}?tail=80`)); } catch (e) { /* the toast said enough */ } }
    }
    if (changed) refreshCounts();
    paintNav(); paintStatus();
  } catch (e) { /* the server may be restarting */ }
  const busy = S.jobs.some(j => j.status === 'running' || j.status === 'queued');
  document.documentElement.toggleAttribute('data-busy', busy);
  S.pollT = setTimeout(pollJobs, busy || S.watch.size ? 1000 : 5000);
}

setInterval(() => {
  const i = (Date.now() / 120 | 0) % SPIN.length;
  $$('.spin').forEach(s => { s.textContent = SPIN[i]; });
}, 120);

// ---- routing and keys ---------------------------------------------------------------------------------------------
function parseHash() {
  const h = location.hash.replace(/^#\/?/, '');
  const [p, q] = h.split('?');
  const parts = p.split('/').filter(Boolean).map(decodeURIComponent);
  return { name: parts[0] || 'overview', args: parts.slice(1), q: Object.fromEntries(new URLSearchParams(q || '')) };
}
const go = h => { if (location.hash === h) route(); else location.hash = h; };

const NO_CONFIG = new Set(['setup', 'overview', 'jobs']);
const needsSetup = el => put(el, html`<div class="page-h"><h1>${S.route.name}</h1></div>
  <section class="box accent"><div class="t">set up Panko first</div><p class="muted-p">This page needs to know which language you're learning.
  It takes a minute: pick your language and Panko writes a config file you can change later.</p>
  <div class="acts mt"><a class="btn pri" href="#/setup">set up Panko</a></div></section>`);

async function route() {
  S.route = parseHash();
  S.cleanup?.(); S.cleanup = null; S.keys = null; S.flip = null; S.onTheme = null;
  $('#layer').innerHTML = '';
  paintNav();
  const view = $('#view');
  const el = document.createElement('div');
  el.className = 'route';
  view.replaceChildren(el);
  view.scrollTop = 0;
  const fn = !S.meta?.config && !NO_CONFIG.has(S.route.name) ? needsSetup : VIEWS[S.route.name] || VIEWS.overview;
  put(el, loading());
  const mine = S.rseq = (S.rseq || 0) + 1;
  try { await fn(el, S.route); } catch (e) { if (mine === S.rseq && e.status !== 401) put(el, errorBox(e)); }
}

document.addEventListener('keydown', e => {
  if ($('#layer').childElementCount) return;
  const t = e.target;
  if (t.matches?.('input, textarea, select, [contenteditable]')) { if (e.key === 'Escape') t.blur(); return; }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); return palette(); }
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (S.gPending) {
    S.gPending = false;
    const m = NAV.find(x => x && x[1] === e.key);
    if (m) { e.preventDefault(); go(m[0] === 'overview' ? '#/' : '#/' + m[0]); }
    return;
  }
  if (e.key === 'g') { S.gPending = true; setTimeout(() => { S.gPending = false; }, 1000); return; }
  if (e.key === '/') { e.preventDefault(); return palette(); }
  if (e.key === '?') { e.preventDefault(); return keysHelp(); }
  if (e.key === 't') return toggleTheme();
  S.keys?.(e);
});

/* Delegate [data-a] clicks inside an element to handlers. */
function actions(el, handlers) {
  el.onclick = async ev => {
    const b = ev.target.closest('[data-a]');
    if (b && el.contains(b) && handlers[b.dataset.a]) { ev.preventDefault(); await handlers[b.dataset.a](b, ev); return; }
    const row = ev.target.closest('[data-href]');
    if (row && el.contains(row) && !ev.target.closest('a, button, input')) go(row.dataset.href);
  };
}

const VIEWS = {};

// ---- overview -----------------------------------------------------------------------------------------------------
VIEWS.overview = async el => {
  if (!S.meta.config) return go('#/setup');
  await refreshCounts();
  const o = S.ov;
  const vs = Object.entries(o.counts);
  const m = S.meta;
  const empty = !vs.length && !Object.keys(o.sources || {}).length;
  put(el, html`<div class="page-h"><h1>overview</h1><span class="sub">${empty ? 'getting started' : 'what needs doing'}</span></div>
    ${tourOffer()}
    ${empty ? html`<section class="box accent"><div class="t">start here</div>
      <ol class="steps">
        <li><span><b>Add something you learn from.</b> A PDF or photos of a lesson, a recording, or an Anki deck you already have.
          <a href="#/sources?add=1">add a source</a></span></li>
        <li><span><b>Choose who reads it.</b> <span id="st-who">Your own Claude in chat, free (<a href="#/setup">connect it in setup</a>), or the API with your key (<a href="#/setup">add it in setup</a>; paid, priced first).</span></span></li>
        <li><span><b>Pick the good words.</b> They wait in the <a href="#/inbox">inbox</a> until you activate them.</span></li>
        <li><span><b>Send them to Anki</b> with the MCP add-on open. <a href="#/sync">Sync</a> shows what would change before anything does.</span></li>
      </ol>
      <div class="acts mt"><a class="btn pri" href="#/sources?add=1">+ add your first source</a><a class="btn" href="#/design">see how cards look</a></div></section>` : ''}
    <section class="box welcome accent"><div class="t">welcome</div>
      <div class="hero-mark"><img src="/static/logo.svg" alt="" width="64" height="64"><pre class="logo" aria-hidden="true">${LOGO}</pre></div>
      <div class="kv">
        <span class="k">learning</span><span class="v">${m.language}</span>
        <span class="k">varieties</span><span class="v">${m.varieties.map(v => v.title).join(', ')}</span>
        <span class="k">glosses in</span><span class="v">${m.gloss_language}</span>
        ${m.hosted ? '' : html`<span class="k">folder</span><span class="v">${tilde(m.root)}</span>`}
        <span class="k">spend</span><span class="v">${usd(o.spend.month)} this month, <span class="dim">${usd(o.spend.all)} in all</span></span>
      </div>
      ${empty ? '' : week(o.added)}
    </section>
    ${empty ? '' : html`${tiles(o)}
    <section class="box"><div class="t">cards <span class="dim">by variety</span></div>
      ${vs.length ? vs.map(([v, c]) => varietyRow(v, c)) : html`<p class="empty">No cards yet. Your sources have units waiting to be read.</p>`}
    </section>`}
    ${empty ? '' : html`<div class="cols">
      <section class="box"><div class="t">what's next</div>${nextSteps(o)}</section>
      <section class="box"><div class="t">running</div>${o.jobs.length ? html`<ul class="plain">${o.jobs.map(j => html`<li><span class="spin acc">✻</span> <a href="#/jobs/${j.id}">${j.title}</a> <span class="dim">${j.status}</span></li>`)}</ul>`
        : html`<p class="empty">Nothing running.</p>`}${o.batches ? html`<p class="dim">${plural(o.batches, 'batch', 'batches')} sent and not collected yet. <button class="link" data-a="collect">collect</button></p>` : ''}</section>
    </div>`}
    <p class="tip kbd-hint">Press <kbd>/</kbd> for commands and search, or <kbd>?</kbd> for every key.</p>`);
  if (empty) api('/readiness').then(x => {     // slow (it asks Anki and the providers), so it fills in afterwards
    if (x.rows.find(r => r.what.startsWith('API mode'))?.ok && $('#st-who')) put($('#st-who'), html`Your API key is set, so Panko can read units itself (paid, priced first), or your own Claude can in chat, free.`);
  }).catch(() => {});
  actions(el, { collect: () => startJob('/llm/collect'), tour: () => tour(), 'tour-no': () => { tourDone(); $('#tour-offer')?.remove(); } });
};

/* Words added per day over the last two weeks: a small bar row. */
function week(days) {
  if (!days?.length) return '';
  const max = Math.max(1, ...days.map(d => d.n));
  const total = days.reduce((a, d) => a + d.n, 0);
  const short = d => new Date(d + 'T12:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  return html`<div class="week"><span class="lbl">${plural(total, 'word')} added in the last two weeks</span>
    <div class="spark">${days.map(d => html`<i class="${d.n ? '' : 'z'}" style="height:${d.n ? Math.max(8, d.n / max * 100).toFixed(0) : 4}%" title="${short(d.day)}: ${d.n}"></i>`)}</div>
    <div class="spark-x"><span>${short(days[0].day)}</span><span>today</span></div></div>`;
}

function tiles(o) {
  const c = Object.values(o.counts);
  const sum = k => c.reduce((a, x) => a + (x[k] || 0), 0);
  const tile = (href, cls, ic, v, l) => html`<a class="tile ${cls}" href="${href}"><span class="ic">${icon(ic)}</span><span class="v">${v}</span><span class="l">${l}</span></a>`;
  return html`<div class="tiles">
    ${tile('#/cards?status=active&flag=in-anki', 'ok', 'anki', n(sum('in_anki')), 'cards in Anki')}
    ${tile('#/inbox', '', 'inbox', n(sum('candidate')), 'waiting in the inbox')}
    ${tile('#/cards?status=candidate&flag=doubtful', 'warn', 'doubt', n(sum('doubtful')), 'doubtful, to fix or reject')}
    ${tile('#/usage', 'info', 'spend', usd(o.spend.month), 'spent this month')}
  </div>`;
}

function varietyRow(v, c) {
  const live = (c.active || 0) + (c.candidate || 0);
  const q = x => `#/cards?variety=${encodeURIComponent(v)}&${x}`;
  const unsynced = (c.active || 0) - (c.in_anki || 0);
  const frac = live ? (c.in_anki || 0) / live : 0;
  return html`<div class="vrow"><span class="name">${V(v).title}</span><span class="bar-l">${bar(frac, 24, 'ok')}<small>${Math.round(frac * 100)}% in Anki</small></span>
    <div class="stats">
      <a href="${q('status=active')}"><b>${n(c.in_anki)}</b> in Anki</a>
      ${unsynced > 0 ? html`<a href="#/sync"><b>${n(unsynced)}</b> waiting for sync</a>` : ''}
      <a href="${q('status=candidate')}"><b>${n(c.candidate)}</b> in the inbox</a>
      ${c.doubtful ? html`<a class="w" href="${q('status=candidate&flag=doubtful')}"><b>${n(c.doubtful)}</b> doubtful</a>` : ''}
      ${c.no_picture ? html`<a href="${q('status=active&flag=no-picture')}"><b>${n(c.no_picture)}</b> without a picture</a>` : ''}
      ${c.no_example ? html`<a href="${q('status=all&flag=no-example')}"><b>${n(c.no_example)}</b> without an example</a>` : ''}
      ${c.duplicate ? html`<a href="${q('status=duplicate')}"><b>${n(c.duplicate)}</b> duplicates</a>` : ''}
      ${c.rejected ? html`<a href="${q('status=rejected')}"><b>${n(c.rejected)}</b> rejected</a>` : ''}
    </div></div>`;
}

function nextSteps(o) {
  const c = Object.values(o.counts);
  const sum = k => c.reduce((a, x) => a + (x[k] || 0), 0);
  const steps = [...o.steps];
  const unsynced = sum('active') - sum('in_anki');
  if (unsynced > 0) steps.push({ text: `${plural(unsynced, 'active card')} not in Anki yet: sync`, go: '#/sync' });
  if (sum('no_picture')) steps.push({ text: `${plural(sum('no_picture'), 'card')} without a picture`, go: '#/pictures' });
  if (sum('doubtful')) steps.push({ text: `${plural(sum('doubtful'), 'doubtful candidate')} to fix or reject`, go: '#/cards?status=candidate&flag=doubtful' });
  if (!Object.keys(o.sources).length && !sum('active') && !sum('candidate')) steps.push({ text: 'add your first source', go: '#/sources?add=1' });
  return steps.length ? html`<ul class="arrows">${steps.map(s => html`<li><a href="${s.go}">${s.text}</a></li>`)}</ul>` : html`<p class="empty">All caught up.</p>`;
}

// ---- cards (inbox, active, retired) -------------------------------------------------------------------------------
const PAGE = 100;
const C = { status: 'candidate', variety: '', flag: '', q: '', sort: 'id', offset: 0, rows: [], total: 0, cur: 0, sel: new Set(),
  open: null, entry: null, preview: null, pv: { card: 0, side: 'front' }, edit: false, seq: 0 };
const STATUS = [['candidate', 'inbox'], ['active', 'active'], ['duplicate', 'duplicates'], ['rejected', 'rejected'], ['all', 'all']];
const STATUS_NAME = { candidate: 'inbox', active: 'active', duplicate: 'duplicate', rejected: 'rejected' };
const shownStatus = e => e.status !== 'retired' ? e.status : e.merged_into ? 'duplicate' : 'rejected';
const FLAGS = [['', 'any flag'], ['doubtful', 'doubtful'], ['check', 'spelling or root note'], ['no-picture', 'no picture'],
  ['no-example', 'no example'], ['in-anki', 'in Anki']];
const FLAG_SHOWN = new Set(['doubtful', 'check', 'drop', 'wrong', 'no-picture', 'no-example']);
const FLAG_LABEL = { doubtful: 'doubtful', check: 'spelling note', drop: 'drop', wrong: 'wrong', 'no-picture': 'no picture', 'no-example': 'no example', 'in-anki': 'in Anki' };
const tagName = t => t.replace(/^panko::/, '').replace(/::/g, ' / ');

VIEWS.inbox = (el, r) => cardsView(el, r, 'candidate');
VIEWS.cards = (el, r) => cardsView(el, r, 'active');

async function cardsView(el, r, status) {
  if (!S.design) api('/design').then(d => { S.design = d.design; }).catch(() => {});
  Object.assign(C, { status: (r.q.status === 'retired' ? 'rejected' : r.q.status) || status, variety: r.q.variety || '', kind: r.q.kind || '', sources: null, flag: r.q.flag || '', tag: r.q.tag || '', source: r.q.source || '', q: r.q.q || '',
    sort: r.q.sort || 'id', offset: +(r.q.offset || 0), sel: new Set(), cur: 0, open: null });
  const openId = r.args[0] || r.q.id || null;
  put(el, html`<div class="cards"><div class="list">
      <div class="page-h"><h1 id="c-title"></h1><span class="sub" id="c-sub"></span></div>
      <div class="filters">
        <div class="tabs" id="c-status"></div>
        <div class="line">
          <label class="prompt"><input id="c-q" placeholder="search words, glosses, ids or tags" value="${C.q}" autocomplete="off" spellcheck="false"></label>
          <select id="c-variety" aria-label="variety"><option value="">every variety</option>${S.meta.varieties.map(v => html`<option value="${v.name}">${v.title}</option>`)}</select>
          <select id="c-kind" aria-label="words or phrases"><option value="">words and phrases</option><option value="word">words</option><option value="phrase">phrases</option></select>
          <select id="c-flag" aria-label="flag">${FLAGS.map(([k, l]) => html`<option value="${k}">${l}</option>`)}</select>
          <select id="c-tag" aria-label="tag"><option value="">any tag</option></select>
          <select id="c-source" aria-label="source"><option value="">any source</option></select>
          <select id="c-sort" aria-label="order"><option value="id">by id</option><option value="recent">recent first</option><option value="word">by word</option><option value="gloss">by gloss</option></select>
        </div>
      </div>
      <div class="bulk" id="c-bulk"></div>
      <table class="t" id="c-table"></table>
      <div class="pager" id="c-pager"></div>
    </div><aside class="detail" id="detail"></aside></div>`);
  $('#c-variety').value = C.variety; $('#c-kind').value = C.kind; $('#c-flag').value = C.flag; $('#c-sort').value = C.sort;
  let typing;
  $('#c-q').oninput = e => { clearTimeout(typing); typing = setTimeout(() => { C.q = e.target.value.trim(); C.offset = 0; loadRows(); }, 180); };
  $('#c-q').onkeydown = e => { if (e.key === 'Enter' || e.key === 'ArrowDown') { e.preventDefault(); e.target.blur(); if (C.rows.length) openCard(C.rows[C.cur].id); } };
  for (const [id, k] of [['#c-variety', 'variety'], ['#c-kind', 'kind'], ['#c-source', 'source'], ['#c-flag', 'flag'], ['#c-tag', 'tag'], ['#c-sort', 'sort']]) $(id).onchange = e => { C[k] = e.target.value; C.offset = 0; loadRows(); };
  actions(el, {
    status: b => { C.status = b.dataset.s; C.offset = 0; C.sel.clear(); loadRows(); },
    activate: () => act('activate'), reject: () => act('reject'), restore: () => act('restore'),
    'sel-page': () => { C.rows.forEach(x => C.sel.add(x.id)); paintRows(); }, 'sel-none': () => { C.sel.clear(); paintRows(); },
    prev: () => page(-1), next: () => page(1),
  });
  $('#c-table').onclick = ev => {
    const tr = ev.target.closest('tr[data-i]');
    if (!tr) return;
    const i = +tr.dataset.i;
    if (ev.target.closest('.chk') || ev.metaKey || ev.ctrlKey) return toggleSel(i);
    if (ev.shiftKey && C.rows[C.cur]) { const [a, b] = [Math.min(C.cur, i), Math.max(C.cur, i)]; for (let k = a; k <= b; k++) C.sel.add(C.rows[k].id); C.cur = i; return paintRows(); }
    C.cur = i; openCard(C.rows[i].id);
  };
  S.keys = cardKeys;
  await loadRows();
  if (openId) openCard(openId);
  else put($('#detail'), idlePanel());
}

async function loadRows() {
  const seq = ++C.seq;
  const p = new URLSearchParams({ status: C.status, variety: C.variety, kind: C.kind, flag: C.flag, tag: C.tag, source: C.source, q: C.q, sort: C.sort, offset: C.offset, limit: PAGE });
  const d = await api('/entries?' + p);
  if (seq !== C.seq || !$('#c-table')) return;      // a newer search, or the page has moved on
  C.rows = d.rows; C.total = d.total; C.tags = d.tags || [];
  paintTags(); paintFlags(d.flags || {}); paintSources();
  const oi = d.rows.findIndex(r => r.id === C.open);      // the cursor stays on the open card, so only one row is marked
  C.cur = oi >= 0 ? oi : Math.min(C.cur, Math.max(0, d.rows.length - 1));
  paintRows(); syncUrl();
}

/* Every source with cards, by title; loaded once per visit to the cards pages. */
async function paintSources() {
  const sel = $('#c-source');
  if (!sel) return;
  if (!C.sources) { try { C.sources = (await api('/sources')).known.filter(k => k.entries); } catch { C.sources = []; } }
  if (!$('#c-source')) return;
  put(sel, html`<option value="">any source</option>${C.sources.map(k => html`<option value="${k.id}" ${k.id === C.source ? 'selected' : ''} title="${k.title}">${k.title} (${n(k.entries)})</option>`)}`);
}

/* Only the flags some card here has, with how many; the one chosen stays even at 0. */
function paintFlags(counts) {
  const sel = $('#c-flag');
  if (!sel) return;
  put(sel, html`${FLAGS.filter(([k]) => !k || counts[k] || k === C.flag).map(([k, l]) => html`<option value="${k}" ${k === C.flag ? 'selected' : ''}>${l}${k ? ` (${n(counts[k] || 0)})` : ''}</option>`)}`);
}

function syncUrl() {
  if (!$('#c-table')) return;
  const p = new URLSearchParams({ status: C.status });
  for (const k of ['variety', 'kind', 'flag', 'tag', 'source', 'q']) if (C[k]) p.set(k, C[k]);
  if (C.sort !== 'id') p.set('sort', C.sort);
  if (C.offset) p.set('offset', C.offset);
  if (C.open) p.set('id', C.open);
  history.replaceState(null, '', '#/cards?' + p);
  S.route = parseHash();
  paintNav();
}

function paintTags() {
  const sel = $('#c-tag');
  if (!sel) return;
  const have = new Map(C.tags);
  if (C.tag && !have.has(C.tag)) have.set(C.tag, 0);
  put(sel, html`<option value="">any tag</option>${[...have].map(([t, k]) => html`<option value="${t}">${tagName(t)}${k ? ` (${n(k)})` : ''}</option>`)}`);
  sel.value = C.tag;
}

/* The card panel before a card is open: what the list holds, and the keys. */
function idlePanel() {
  const counts = S.ov ? Object.entries(S.ov.counts).filter(([v]) => !C.variety || v === C.variety).map(([, c]) => c) : [];
  const sum = k => counts.reduce((a, c) => a + (c[k] || 0), 0);
  const inbox = C.status === 'candidate';
  const links = [
    inbox && sum('doubtful') && ['#/cards?status=candidate&flag=doubtful', plural(sum('doubtful'), 'doubtful candidate'), 'warn'],
    !inbox && sum('no_picture') && ['#/cards?status=active&flag=no-picture', plural(sum('no_picture'), 'card') + ' without a picture', ''],
    sum('no_example') && ['#/cards?status=all&flag=no-example', plural(sum('no_example'), 'word') + ' without an example', ''],
  ].filter(Boolean);
  const keys = inbox ? [['j k', 'move'], ['enter', 'open'], ['x', 'select'], ['a', 'activate'], ['r', 'reject'], ['/', 'search']]
    : [['j k', 'move'], ['enter', 'open'], ['e', 'edit'], ['space', 'flip the card'], ['/', 'search']];
  return html`<div class="idle"><section class="box"><div class="t">${inbox ? 'the inbox' : 'cards'}</div>
      <p class="muted-p">${inbox ? 'Pick a candidate to see the card it would make. Activate the good ones; they reach Anki on the next sync.'
        : 'Pick a card to see it as Anki shows it, and edit it.'}</p>
      ${links.length ? html`<ul class="arrows mt">${links.map(([h, t, cls]) => html`<li><a class="${cls}" href="${h}">${t}</a></li>`)}</ul>` : ''}
      ${C.tags?.length ? html`<h4 class="sub-h">tags</h4><div class="tagcloud">${C.tags.slice(0, 14).map(([t, k]) => html`<a class="flag" href="#/cards?status=${C.status}&tag=${encodeURIComponent(t)}">${tagName(t)} <span class="faint">${n(k)}</span></a>`)}</div>` : ''}
    </section>
    <section class="box kbd-hint"><div class="t">keys</div>${keys.map(([k, d]) => html`<div class="keyrow"><span>${k.split(' ').map(x => html`<kbd>${x}</kbd> `)}</span><span>${d}</span></div>`)}</section></div>`;
}

function paintRows() {
  if (!$('#c-table')) return;
  const counts = S.ov ? Object.entries(S.ov.counts).filter(([v]) => !C.variety || v === C.variety).map(([, c]) => c) : [];
  const cnt = s => s === 'all' ? counts.reduce((a, c) => a + (c.candidate || 0) + (c.active || 0) + (c.retired || 0), 0) : counts.reduce((a, c) => a + (c[s] || 0), 0);
  $('#c-title').textContent = { candidate: 'inbox', active: 'active cards', duplicate: 'duplicates', rejected: 'rejected', all: 'everything' }[C.status];
  put($('#c-sub'), html`${plural(C.total, 'entry', 'entries')}${C.q || C.flag || C.tag || C.source || C.kind ? ' match' + (C.total === 1 ? 'es' : '') : ''}`);
  put($('#c-status'), STATUS.map(([s, l]) => html`<button data-a="status" data-s="${s}" class="${C.status === s ? 'on' : ''}">${l}<span class="c">${counts.length ? n(cnt(s)) : ''}</span></button>`));
  const head = html`<colgroup><col style="width:5.5ch"><col style="width:28%"><col class="c-tl" style="width:22%"><col><col style="width:13ch"></colgroup>
    <thead><tr><th class="chk"></th><th>word</th><th class="c-tl">transliteration</th><th>gloss</th><th></th></tr></thead>`;
  put($('#c-table'), html`${head}<tbody>${C.rows.length ? C.rows.map((r, i) => html`<tr class="row ${i === C.cur ? 'cur' : ''} ${C.sel.has(r.id) ? 'sel' : ''} ${r.id === C.open ? 'open' : ''}" data-i="${i}">
      <td class="chk"><span class="cb"></span></td>
      <td title="${r.ar}"><div class="clamp">${tgt(r.ar, r.variety)}</div></td>
      <td class="dim c-tl" title="${r.tl}"><div class="clamp">${r.tl}</div></td>
      <td title="${r.gloss}"><div class="clamp">${r.gloss}</div></td>
      <td class="flags">${r.flags.filter(f => FLAG_SHOWN.has(f)).slice(0, 1).map(f => html`<span class="flag ${f}">${FLAG_LABEL[f] || f}</span>`)}${C.status === 'all' ? html`<span class="flag ${r.status}">${STATUS_NAME[r.status]}</span>` : ''}</td>
    </tr>`) : html`<tr><td colspan="5" class="empty">${C.q || C.flag || C.tag || C.source || C.kind ? 'Nothing matches.' : C.status === 'candidate' ? 'The inbox is empty. New words from your sources land here.' : 'Nothing here.'}</td></tr>`}</tbody>`);
  const canAct = C.status === 'candidate' || C.status === 'all';
  put($('#c-bulk'), C.sel.size ? html`<span class="count">${n(C.sel.size)} selected</span>
      ${canAct ? html`<button class="pri" data-a="activate">activate<kbd>a</kbd></button><button class="danger" data-a="reject">reject<kbd>r</kbd></button>` : ''}
      ${C.status === 'rejected' ? html`<button data-a="restore">back to the inbox<kbd>u</kbd></button>` : ''}
      <button class="ghost" data-a="sel-page">select the page</button><button class="ghost" data-a="sel-none">clear</button>`
    : html`<span>${C.total ? `${n(C.offset + 1)}–${n(C.offset + C.rows.length)} of ${n(C.total)}` : ''}</span>
      ${(C.status === 'candidate' ? [['a', 'activate'], ['r', 'reject'], ['x', 'select'], ['shift', '+ click for a range']] : [['j k', 'move'], ['enter', 'open']])
        .map(([k, d]) => html`<span class="faint kbd-hint">${k.split(' ').map(x => html`<kbd>${x}</kbd> `)}${d}</span>`)}`);
  const pages = Math.ceil(C.total / PAGE);
  put($('#c-pager'), pages > 1 ? html`<button data-a="prev" ${C.offset ? '' : 'disabled'}>← prev</button><span>page ${C.offset / PAGE + 1} of ${pages}</span><button data-a="next" ${C.offset + PAGE < C.total ? '' : 'disabled'}>next →</button>` : '');
  $('#c-table tr.cur')?.scrollIntoView({ block: 'nearest' });
}

const selIds = () => C.sel.size ? [...C.sel] : C.rows[C.cur] ? [C.rows[C.cur].id] : [];
function toggleSel(i) { const id = C.rows[i]?.id; if (!id) return; C.sel.has(id) ? C.sel.delete(id) : C.sel.add(id); C.cur = i; paintRows(); }
function page(d) { const o = C.offset + d * PAGE; if (o < 0 || o >= C.total) return; C.offset = o; C.cur = 0; loadRows(); }

async function act(kind, ids = selIds()) {
  if (!ids.length) return;
  const rows = ids.map(id => C.rows.find(r => r.id === id) || (C.entry?.entry.id === id ? { id, ...C.entry.entry, flags: C.entry.entry.tags?.includes('panko::doubtful') ? ['doubtful'] : [] } : { id, flags: [] }));
  if (kind === 'activate') {
    const doubt = rows.filter(r => r.flags?.includes('doubtful'));
    if (doubt.length && !await confirmIt(`activate ${plural(ids.length, 'card')}?`,
      html`<p>${doubt.length === ids.length && ids.length === 1 ? 'This one is' : `${n(doubt.length)} of these are`} <span class="warn">doubtful</span>: a check found a problem.
        Activating clears the doubt and the card goes to Anki on the next sync.</p>`, 'Yes, I checked it')) return;
  }
  if (kind === 'reject' && ids.length > 1 && !await confirmIt(`reject ${plural(ids.length, 'candidate')}?`,
    html`<p class="dim">They go to the rejected tab, not away: it can bring them back, and they stay out of your inbox when a source has them again.</p>`)) return;
  try {
    const r = await api(`/entries/${kind}`, { body: { ids } });
    const done = r.activated || r.retired || r.restored || [];
    const verb = { activate: 'activated', reject: 'rejected', restore: 'back in the inbox' }[kind];
    const skipped = ids.length - done.length;
    toast(html`<span class="ok">✔</span> ${plural(done.length, 'card')} ${verb}${skipped ? html`, <span class="warn">${n(skipped)} skipped</span>` : ''}${kind === 'activate' && done.length ? html`<div class="dim">They reach Anki on the next sync.</div>` : ''}`, 'ok');
    const wasOpen = C.open && done.includes(C.open);
    C.sel.clear();
    await loadRows();
    refreshCounts();
    if (wasOpen) { if (C.rows[C.cur]) openCard(C.rows[C.cur].id); else { C.open = null; put($('#detail'), idlePanel()); } }
  } catch (e) { toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); }
}

function cardKeys(e) {
  const k = e.key;
  const move = d => { if (!C.rows.length) return; C.cur = Math.max(0, Math.min(C.rows.length - 1, C.cur + d)); paintRows(); if (C.open) openCard(C.rows[C.cur].id); };
  if (k === 'j' || k === 'ArrowDown') { e.preventDefault(); move(1); }
  else if (k === 'k' || k === 'ArrowUp') { e.preventDefault(); move(-1); }
  else if (k === 'Enter' || k === 'o') { if (C.rows[C.cur]) openCard(C.rows[C.cur].id); }
  else if (k === 'x') toggleSel(C.cur);
  else if (k === 'a' && (C.status === 'candidate' || C.status === 'all')) act('activate', C.sel.size ? [...C.sel] : [C.open || C.rows[C.cur]?.id].filter(Boolean));
  else if (k === 'r' && (C.status === 'candidate' || C.status === 'all')) act('reject', C.sel.size ? [...C.sel] : [C.open || C.rows[C.cur]?.id].filter(Boolean));
  else if (k === 'u' && C.status === 'rejected') act('restore');
  else if (k === 'e' && C.open) { C.edit = !C.edit; paintDetail(); }
  else if (k === ' ' && C.open) { e.preventDefault(); C.pv.side = C.pv.side === 'front' ? 'back' : 'front'; paintPreview(); }
  else if ((k === ']' || k === '[') && C.preview?.cards.length) { const m = C.preview.cards.length; C.pv.card = (C.pv.card + (k === ']' ? 1 : m - 1)) % m; C.pv.side = 'front'; paintPreview(); }
  else if (k === 's' || k === 'f') { e.preventDefault(); $('#c-q')?.focus(); }
  else if (k === 'n') page(1);
  else if (k === 'p') page(-1);
  else if (k === 'Escape') { if ($('#detail.open') && innerWidth <= 1100) { $('#detail').classList.remove('open'); } else if (C.sel.size) { C.sel.clear(); paintRows(); } }
}

async function openCard(id) {
  const same = C.open === id;
  C.open = id;
  const oi = C.rows.findIndex(r => r.id === id);
  if (oi >= 0 && (oi !== C.cur || !same) && $('#c-table')) { C.cur = oi; paintRows(); }   // cursor and open card are one row
  if (!same) { C.edit = false; C.pv = { card: 0, side: 'front' }; }
  const box = $('#detail');
  if (!box) return;
  box.classList.add('open');
  if (!same) put(box, loading('reading the entry'));
  try {
    const [d, p] = await Promise.all([api(`/entries/${encodeURIComponent(id)}`), api(`/entries/${encodeURIComponent(id)}/preview`)]);
    if (C.open !== id || !box.isConnected) return;
    C.entry = d; C.preview = p;
    C.pv.card = Math.min(C.pv.card, Math.max(0, p.cards.length - 1));
    paintDetail(); syncUrl();
    $$('#c-table tr[data-i]').forEach(tr => tr.classList.toggle('open', C.rows[+tr.dataset.i]?.id === id));
  } catch (e) { put(box, errorBox(e)); }
}

const pvSrc = id => `/api/entries/${encodeURIComponent(id)}/preview?side=${C.pv.side}&card=${C.pv.card}&theme=${theme()}`;

/* The card document is fetched and handed to the sandboxed iframe as srcdoc: no navigation, an opaque origin. */
async function loadPv(f, src) {
  f.dataset.src = src;
  try {
    const r = await fetch(src, { headers: { 'X-Panko': '1' } });
    const text = await r.text();
    if (f.dataset.src === src) f.srcdoc = text;
  } catch (e) { f.srcdoc = `<p style="font:13px monospace;color:#c44">${esc(e.message)}</p>`; }
}

function paintPreview() {
  const f = $('#detail iframe.pv');
  if (!f) return;
  loadPv(f, pvSrc(C.open));
  $$('#detail [data-card]').forEach(b => b.classList.toggle('on', +b.dataset.card === C.pv.card));
  $$('#detail [data-side]').forEach(b => b.classList.toggle('on', b.dataset.side === C.pv.side));
}

function paintDetail() {
  const box = $('#detail');
  if (!box || !C.entry) return;
  const { entry: e, sightings, anki, kept, duplicates, also } = C.entry;
  const p = C.preview;
  const v = V(e.variety);
  put(box, html`
    <div class="head">
      <div class="acts split"><span class="faint">${e.id}</span><span class="acts">
        ${e.status === 'candidate' ? html`<button class="pri" data-a="activate">activate<kbd>a</kbd></button><button class="danger" data-a="reject">reject<kbd>r</kbd></button>` : ''}
        ${e.status === 'retired' && !anki && !e.merged_into ? html`<button data-a="restore">back to the inbox</button>` : ''}
        <button data-a="edit">${C.edit ? 'stop editing' : 'edit'}<kbd>e</kbd></button><button class="ghost close" data-a="close" aria-label="close">✕</button></span></div>
      <div class="tgt huge" dir="auto" style="--tgt:${v.font || 'system-ui'}">${e.ar}</div>
      <div class="line2">${e.tl}${e.tl_alt ? html` <span class="faint">(${e.tl_alt})</span>` : ''}</div>
      <div class="gloss">${e.gloss}</div>
      <div class="meta"><span class="flag ${shownStatus(e)}">${STATUS_NAME[shownStatus(e)]}</span><span>${v.title} ${e.kind}</span>${e.pos ? html`<span>${e.pos}</span>` : ''}${e.region ? html`<span>${e.region}</span>` : ''}${anki ? html`<span class="ok">✔ in Anki</span>` : ''}${(e.tags || []).includes('panko::doubtful') ? html`<span class="warn">⚠ doubtful</span>` : ''}</div>
    </div>
    ${C.edit ? editForm(e) : ''}
    ${retiredBox(e, kept, also)}
    <section class="box"><div class="t">card <span class="dim">as Anki shows it</span></div>
      ${p.cards.length ? html`<div class="pv-bar"><div class="tabs">${p.cards.map((c, i) => html`<button data-card="${i}" class="${i === C.pv.card ? 'on' : ''}">${c.name}</button>`)}</div>
        <div class="seg"><button data-side="front" class="${C.pv.side === 'front' ? 'on' : ''}">front</button><button data-side="back" class="${C.pv.side === 'back' ? 'on' : ''}">back</button></div></div>
        <iframe class="pv" sandbox="allow-scripts" title="card preview"></iframe>
        <div class="hint split"><span class="kbd-hint"><kbd>space</kbd> flips, <kbd>[</kbd> <kbd>]</kbd> for the other card</span><span>${p.deck}</span></div>`
        : html`<p class="empty">No card would be made from this entry.</p>`}
    </section>
    ${C.edit ? '' : fieldsBox(e)}
    ${checkBox(e)}
    <section class="box"><div class="t">references <span class="dim">and words like it</span></div><div id="ev">${loading('looking it up')}</div></section>
    <section class="box"><div class="t">sources</div>${sourcesBox(e, sightings)}</section>
    ${duplicates?.length ? html`<section class="box"><div class="t">duplicates <span class="dim">folded into this card</span></div><ul class="ev">${duplicates.map(x => html`<li class="ent"><a href="#/cards?status=all&id=${x.id}">${x.id}</a> ${tgt(x.ar, e.variety)} <span class="dim">${x.tl}</span> <span>${x.gloss}</span></li>`)}</ul></section>` : ''}
    ${anki ? html`<p class="faint mt">Anki note ${anki.note_id}, last written ${when(anki.synced)}</p>` : ''}`);
  actions(box, {
    activate: () => act('activate', [e.id]), reject: () => act('reject', [e.id]), restore: () => act('restore', [e.id]),
    edit: () => { C.edit = !C.edit; paintDetail(); },
    close: () => box.classList.remove('open'),
    'ex-add': () => addRow('#ed-ex', exRow({})), 'rel-add': () => addRow('#ed-rel', relRow({})),
    'row-del': b => b.closest('.rowedit').remove(),
    save: () => saveEdit(e), cancel: () => { C.edit = false; paintDetail(); },
  });
  if ($('iframe.pv', box)) loadPv($('iframe.pv', box), pvSrc(e.id));
  S.flip = () => { C.pv.side = C.pv.side === 'front' ? 'back' : 'front'; paintPreview(); };
  lookUp(e);
  $$('[data-card]', box).forEach(b => { b.onclick = () => { C.pv.card = +b.dataset.card; C.pv.side = 'front'; paintPreview(); }; });
  $$('[data-side]', box).forEach(b => { b.onclick = () => { C.pv.side = b.dataset.side; paintPreview(); }; });
  const form = $('#ed', box);
  if (form) {
    form.onkeydown = ev => { if (ev.key === 'Enter' && (ev.metaKey || ev.ctrlKey)) { ev.preventDefault(); saveEdit(e); } if (ev.key === 'Escape') { C.edit = false; paintDetail(); } };
    form.onsubmit = ev => { ev.preventDefault(); saveEdit(e); };
    $('input, textarea', form)?.focus();
  }
}

const FIELD_NAMES = { gloss_note: 'gloss note', pos: 'part of speech', literal: 'literally', tl_alt: 'scholarly', tl: 'transliteration',
  ar: 'word', present: 'present', imperative: 'imperative', plural: 'plural', gender: 'gender', usage: 'usage', notes: 'notes', region: 'region' };

function retiredBox(e, kept, also = []) {
  if (e.status !== 'retired') return '';
  const link = x => html`<a href="#/cards?status=all&id=${x.id}">${x.id}</a> ${tgt(x.ar, e.variety)} <span class="dim">${x.tl}</span> ${x.gloss} <span class="flag ${x.status}">${STATUS_NAME[x.status]}</span>`;
  if (e.merged_into) return html`<section class="box"><div class="t">duplicate</div>
    <p>${kept ? html`The same word as ${link(kept)}, the card that was kept.` : html`${e.merged_into}.`}</p>
    ${also.length ? html`<p class="mt-s"><span class="dim">Panko matched it to the closest card; it's also close to</span></p><ul class="ev">${also.map(x => html`<li>${link(x)}</li>`)}</ul>` : ''}
    <p class="faint mt-s">Its sources show on that card, and if a source has the word again, it counts for that card.</p></section>`;
  return html`<section class="box"><div class="t">rejected</div>
    <p>${e.retired_why ? html`${e.retired_why[0].toUpperCase() + e.retired_why.slice(1)}.` : 'Set aside before Panko kept a reason; it may be a duplicate (see references below).'}</p>
    <p class="faint mt-s">It never goes to Anki, and when a source has it again it stays here instead of coming back to your inbox. Back to the inbox undoes it.</p></section>`;
}

function fieldsBox(e) {
  const tgtFields = new Set(['plural', 'present', 'imperative']);
  const simple = ['gloss_note', 'gender', 'plural', 'present', 'imperative', 'literal', 'usage', 'notes'].filter(k => e[k]);
  return html`<section class="box"><div class="t">entry</div>
    ${e.image?.file ? html`<img class="picture" src="/media/${encodeURIComponent(e.image.file)}" alt="${e.gloss}" loading="lazy"><p class="faint">${credit(e.image.credit)}</p>`
      : html`<p class="faint">${e.picture_pref === 'none' ? 'no picture, as you asked' : 'no picture yet'}</p>`}
    <div class="kv mt-s">
      ${simple.map(k => html`<span class="k">${FIELD_NAMES[k] || k}</span><span class="v">${tgtFields.has(k) ? tgt(e[k], e.variety) : e[k]}</span>`)}
      ${(e.examples || []).length ? html`<span class="k">examples</span><span class="v">${e.examples.map(x => html`<div class="mb-s">${tgt(x.ar, e.variety)}<div class="dim">${x.tl || ''}</div><div>${x.en || ''}</div>${x.source || x.cite ? html`<div class="faint">${x.source || x.cite}</div>` : ''}</div>`)}</span>` : html`<span class="k">examples</span><span class="v warn">none yet</span>`}
      ${(e.related || []).length ? html`<span class="k">related</span><span class="v">${e.related.map(x => html`<div>${tgt(x.ar, e.variety)} <span class="dim">${x.tl || ''}</span> ${x.meaning || ''}</div>`)}</span>` : ''}
      ${e.cards ? html`<span class="k">cards</span><span class="v">${e.cards.join(', ')}</span>` : ''}
      ${!e.image?.file && (PIC_PREF[e.picture_pref] && e.picture_pref || e.picture_request) ? html`<span class="k">picture wish</span><span class="v">${[e.picture_pref && e.picture_pref !== 'none' ? PIC_PREF[e.picture_pref] : '', e.picture_request].filter(Boolean).join(': ')}</span>` : ''}
      ${(S.design?.extras || []).filter(x => e.extra?.[x.slot]).map(x => html`<span class="k">${x.label.toLowerCase()}</span><span class="v">${e.extra[x.slot]}</span>`)}
      <span class="k">tags</span><span class="v">${(e.tags || []).map(t => html`<a class="flag" href="#/cards?status=all&tag=${encodeURIComponent(t)}">${tagName(t)}</a>`)}</span>
    </div></section>`;
}

/* Picture credits are stored as a little HTML (a link to the file page): shown as plain text, with the link kept
   only when it's an ordinary https address. DOMParser never runs what it parses. */
function credit(c) {
  if (!c) return '';
  const doc = new DOMParser().parseFromString(String(c), 'text/html');
  const a = doc.querySelector('a[href^="https://"]');
  const text = doc.body.textContent.replace(/\s+/g, ' ').trim();
  if (!a) return text;
  const label = a.textContent.trim();
  const rest = text.startsWith(label) ? text.slice(label.length) : ', ' + text;
  return html`<a href="${a.getAttribute('href')}" target="_blank" rel="noopener noreferrer">${label}</a>${rest}`;
}

const VERDICT = { ok: 'looks right', fix: 'right after a fix on the way in', doubtful: 'doubtful: look before you use it', drop: 'better left out',
  wrong: 'wrong', uncommon: 'right, but not common', regional: 'right, but regional' };
const REGISTER = { formal: 'formal', informal: 'informal', slang: 'slang', vulgar: 'vulgar', religious: 'religious', dated: 'dated' };

function checkBox(e) {
  const ck = e.check || {};
  const morph = ck.morph || [];
  if (!ck.verdict && !ck.summary && !morph.length) return '';
  const cls = { ok: 'ok', fix: 'info', doubtful: 'warn', drop: 'bad', wrong: 'bad', uncommon: 'info', regional: 'info' }[ck.verdict] || '';
  const said = VERDICT[ck.verdict] || ck.verdict;
  const reg = ck.register && ck.register !== 'neutral' ? REGISTER[ck.register] || ck.register : '';
  return html`<section class="box ${cls === 'warn' || morph.some(p => p.problem !== 'unknown') ? 'warn' : ''}"><div class="t">how it was checked</div>
    ${ck.verdict ? html`<p><span class="${cls}">● ${said}</span>${reg ? html` <span class="dim">(${reg})</span>` : ''}</p>${ck.usual_word ? html`<p><span class="dim">the usual word is</span> ${tgt(ck.usual_word, e.variety)}</p>` : ''}` : ''}
    ${ck.summary && !/^correct\.?$/i.test(ck.summary.trim()) ? html`<p>${ck.summary}</p>` : ''}
    ${(ck.evidence || []).length ? html`<h4 class="sub-h">checked against</h4><ul class="ev dim">${ck.evidence.map(x => html`<li>${String(x).replace(/^Memory:\s*/i, 'the model’s own knowledge: ')}</li>`)}</ul>` : ''}
    ${morph.length ? html`<h4 class="sub-h">analyser</h4><ul class="ev">${morph.map(p => html`<li><span class="flag ${p.problem === 'unknown' ? '' : 'check'}">${p.problem}</span>${p.field}: ${tgt(p.text, e.variety)}${p.suggest ? html` → ${tgt(p.suggest, e.variety)}` : ''} <span class="dim">${p.detail || ''}</span></li>`)}</ul>` : ''}
  </section>`;
}

const squash = t => String(t || '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '');

function sourcesBox(e, sightings) {
  const rows = [];
  const find = t => rows.find(r => squash(r.title) === squash(t) || squash(r.title).endsWith(squash(t)) || squash(t).endsWith(squash(r.title)));
  for (const s of sightings) {
    const r = find(s.title) || rows[rows.push({ title: s.title, said: [] }) - 1];
    const spoken = ['lesson', 'media'].includes(s.source_kind);
    if (!r.role && spoken && s.speaker) r.role = `said by ${s.speaker}`;
    if (s.ar || s.en) r.said.push(s);
  }
  for (const t of e.sources || []) if (!find(t)) rows.push({ title: t, said: [] });
  for (const x of e.origin?.notes || []) {
    const r = find(x.deck) || rows[rows.push({ title: x.deck, said: [] }) - 1];
    if (x.studied) r.studied = true;
  }
  if (!rows.length) return html`<p class="faint">none recorded</p>`;
  return html`<ul class="ev">${rows.map(r => html`<li>${r.title}${r.role ? html` <span class="dim">(${r.role})</span>` : ''}${r.studied ? html` <span class="flag ok">you studied it</span>` : ''}
    ${r.said.map(s => html`${s.ar ? html`<div>${tgt(s.ar, e.variety)}</div>` : ''}${s.en ? html`<div class="dim">${s.en}</div>` : ''}`)}</li>`)}</ul>`;
}

async function lookUp(e) {
  const box = $('#ev');
  put(box, loading('looking it up'));
  try {
    const r = await api(`/entries/${encodeURIComponent(e.id)}/evidence`);
    const ent = x => html`<li class="ent"><a href="#/cards?status=all&id=${x.id}">${x.id}</a> ${tgt(x.ar, e.variety)} <span class="dim">${x.tl || ''}</span> <span>${x.gloss || ''}</span><span class="flag ${x.status}">${STATUS_NAME[x.status] || x.status}</span>${x.pos ? html` <span class="faint">${x.pos}</span>` : ''}</li>`;
    put(box, html`${r.hits.length ? html`<ul class="ev">${r.hits.map(h => html`<li>${h}</li>`)}</ul>` : html`<p class="empty">No reference has it.</p>`}
      ${r.panko ? html`<h4 class="sub-h">already in the store</h4><ul class="ev">${ent(r.panko)}</ul>` : ''}
      ${r.same_letters.length ? html`<h4 class="sub-h">same letters, other words</h4><ul class="ev">${r.same_letters.map(ent)}</ul>` : ''}
      ${r.near.length ? html`<h4 class="sub-h">close to</h4><ul class="ev">${r.near.map(ent)}</ul>` : ''}`);
  } catch (err) { put(box, errorBox(err)); }
}

// ---- editing
const SIMPLE = [['ar', 'word', 'tgt'], ['tl', 'transliteration'], ['tl_alt', 'scholarly transliteration'], ['gloss', 'gloss', 'wide'],
  ['gloss_note', 'gloss note', 'wide'], ['pos', 'part of speech'], ['gender', 'gender'], ['plural', 'plural', 'tgt'],
  ['present', 'present', 'tgt'], ['imperative', 'imperative', 'tgt'], ['literal', 'literally'], ['region', 'region'],
  ['usage', 'usage', 'area'], ['notes', 'notes', 'area']];

const PIC_PREF = { '': 'Panko decides', photo: 'a real photo', drawing: 'a drawing', none: 'no picture' };

const exRow = x => html`<div class="rowedit ex"><input data-k="ar" dir="auto" class="tgt" placeholder="sentence" value="${x.ar || ''}"><input data-k="tl" placeholder="transliteration" value="${x.tl || ''}"><input data-k="en" placeholder="meaning" value="${x.en || ''}"><input data-k="source" placeholder="source" value="${x.source || x.cite || ''}"><button type="button" class="ghost" data-a="row-del" aria-label="remove">✕</button></div>`;
const relRow = x => html`<div class="rowedit"><input data-k="ar" dir="auto" class="tgt" placeholder="word" value="${x.ar || ''}"><input data-k="tl" placeholder="transliteration" value="${x.tl || ''}"><input data-k="meaning" placeholder="meaning" value="${x.meaning || ''}"><button type="button" class="ghost" data-a="row-del" aria-label="remove">✕</button></div>`;
function addRow(sel, row) { const d = document.createElement('div'); put(d, row); $(sel).append(d.firstElementChild); $(sel).lastElementChild.querySelector('input').focus(); }

function editForm(e) {
  const font = V(e.variety).font || 'system-ui';
  const extras = S.design?.extras || [];
  return html`<form id="ed" class="box accent" autocomplete="off"><div class="t">edit</div>
    ${e.status === 'active' ? html`<p class="faint mb-s">Changes reach Anki on the next sync. Your own MyNotes field is never touched.</p>` : ''}
    <div class="form" style="--tgt:${font}">
      ${SIMPLE.map(([k, label, kind]) => html`<label class="f ${kind === 'wide' || kind === 'area' ? 'wide' : ''}"><span>${label}</span>${kind === 'area'
        ? html`<textarea name="${k}" rows="2">${e[k] || ''}</textarea>`
        : html`<input name="${k}" value="${e[k] || ''}" ${kind === 'tgt' ? new Raw('dir="auto" class="tgt"') : ''}>`}</label>`)}
      <label class="f wide"><span>tags <span class="faint">separated by spaces</span></span><input name="tags" value="${(e.tags || []).join(' ')}"></label>
      ${e.kind === 'word' ? html`<label class="f"><span>cards</span><select name="cards"><option value="recognition,production">recognition and production</option><option value="recognition">recognition only</option></select></label>` : ''}
      <label class="f"><span>picture</span><select name="picture_pref">${Object.entries(PIC_PREF).map(([v, l]) => html`<option value="${v}" ${(e.picture_pref || '') === v ? 'selected' : ''}>${l}</option>`)}</select></label>
      <label class="f wide"><span>what the picture should show <span class="faint">optional</span></span><input name="picture_request" value="${e.picture_request || ''}" placeholder="a glass of mint tea, seen from above"></label>
      ${extras.map(x => html`<label class="f wide"><span>${x.label}</span><textarea data-extra="${x.slot}" rows="2">${e.extra?.[x.slot] || ''}</textarea></label>`)}
      <div class="wide"><div class="dim mb-s">examples</div><div id="ed-ex">${(e.examples || []).map(exRow)}</div><button type="button" class="ghost" data-a="ex-add">+ example</button></div>
      <div class="wide"><div class="dim mb-s">related words</div><div id="ed-rel">${(e.related || []).map(relRow)}</div><button type="button" class="ghost" data-a="rel-add">+ related</button></div>
    </div>
    <div class="acts mt"><button class="pri" type="submit">save<kbd>⌘↵</kbd></button><button type="button" data-a="cancel">cancel</button></div>
  </form>`;
}

function rowsOf(sel, keys, orig) {
  return $$(sel + ' .rowedit').map((r, i) => {
    const o = { ...(orig[i] || {}) };
    for (const k of keys) {
      const v = $(`[data-k=${k}]`, r).value.trim();
      if (v) o[k] = v; else delete o[k];
      if (k === 'source' && o.cite && v) delete o.cite;
    }
    return o;
  }).filter(o => keys.some(k => o[k]));
}

async function saveEdit(e) {
  const f = $('#ed');
  if (!f) return;
  const fields = {};
  for (const [k] of SIMPLE) { const v = f.elements[k].value.trim(); if (v !== (e[k] || '')) fields[k] = v; }
  const tags = f.elements.tags.value.split(/\s+/).filter(Boolean);
  if (JSON.stringify(tags) !== JSON.stringify(e.tags || [])) fields.tags = tags;
  if (f.elements.cards) {
    const cur = (e.cards || ['recognition', 'production']).join(',');
    if (f.elements.cards.value !== cur) fields.cards = f.elements.cards.value.split(',');
  }
  for (const k of ['picture_pref', 'picture_request']) { const v = f.elements[k].value.trim(); if (v !== (e[k] || '')) fields[k] = v; }
  const extra = { ...(e.extra || {}) };
  $$('[data-extra]', f).forEach(t => { const v = t.value.trim(); if (v) extra[t.dataset.extra] = v; else delete extra[t.dataset.extra]; });
  if (JSON.stringify(extra) !== JSON.stringify(e.extra || {})) fields.extra = extra;
  const ex = rowsOf('#ed-ex', ['ar', 'tl', 'en', 'source'], e.examples || []);
  if (JSON.stringify(ex) !== JSON.stringify(e.examples || [])) fields.examples = ex;
  const rel = rowsOf('#ed-rel', ['ar', 'tl', 'meaning'], e.related || []);
  if (JSON.stringify(rel) !== JSON.stringify(e.related || [])) fields.related = rel;
  if (!fields.ar && 'ar' in fields) return toast(html`<span class="bad">✘</span> the word can't be empty`, 'bad');
  if (!Object.keys(fields).length) { C.edit = false; return paintDetail(); }
  try {
    await api(`/entries/${encodeURIComponent(e.id)}`, { method: 'PATCH', body: { fields } });
    toast(html`<span class="ok">✔</span> saved ${Object.keys(fields).join(', ')}`, 'ok');
    C.edit = false;
    await openCard(e.id);
    loadRows();
  } catch (err) { toast(html`<span class="bad">✘</span> ${err.message}`, 'bad', 0); }
}

// ---- sources ------------------------------------------------------------------------------------------------------
VIEWS.sources = async (el, r) => {
  if (r.args[0]) return sourceView(el, r.args[0], r);
  const { sources, known } = await api('/sources');
  const earlier = known.filter(k => !k.queued);
  put(el, html`<div class="page-h"><h1>sources</h1><span class="sub">${plural(sources.length + earlier.length, 'source')}</span><span class="grow"></span><button class="pri" data-a="add">+ add a source</button></div>
    <div id="addbox"></div>
    ${sources.length ? html`<section class="box"><div class="t">your sources</div><table class="t"><thead><tr><th>title</th><th>kind</th><th class="r">units</th><th>read</th><th class="r">to ingest</th><th class="r">held</th></tr></thead><tbody>
      ${sources.map(s => html`<tr class="row" data-href="#/sources/${encodeURIComponent(s.id)}"><td>${s.title}<div class="faint">${s.id}${s.date ? ', ' + s.date : ''}</div></td>
        <td class="dim">${s.kind} <span class="faint">${s.type}</span></td><td class="r num">${s.transcribe_first ? html`<span class="warn">transcribe first</span>` : n(s.units)}</td>
        <td class="nw">${bar(s.units ? s.ingested / s.units : 0, 14, 'ok')} <span class="dim num">${s.ingested}/${s.units}</span></td>
        <td class="r num ${s.submitted ? 'info' : 'faint'}">${s.submitted}</td><td class="r num ${s.held ? 'warn' : 'faint'}">${s.held}</td></tr>`)}</tbody></table></section>`
      : earlier.length ? '' : html`<section class="box"><div class="t">no sources yet</div><p class="muted-p">A source is anything you learn from, from a lesson recording to an Anki deck you already have.</p>
        <ol class="steps mt"><li><span><b>Add it.</b> Panko splits it into units: pages, minutes of audio or rows of a deck.</span></li>
          <li><span><b>Read it.</b> The model, or your own Claude in chat, reads each unit and checks the words against your references.</span></li>
          <li><span><b>Choose.</b> New words wait in your inbox until you activate them.</span></li>
          <li><span><b>Sync.</b> Active cards go to Anki.</span></li></ol>
        <div class="acts mt"><button class="pri" data-a="add">+ add your first source</button></div></section>`}
    ${earlier.length ? html`<section class="box"><div class="t">where your cards came from <span class="dim">added before the queue</span></div>
      <table class="t"><thead><tr><th>source</th><th>kind</th><th class="r">trust</th><th class="r">words</th></tr></thead><tbody>
      ${earlier.map(k => html`<tr class="row" data-href="#/cards?status=all&source=${encodeURIComponent(k.id)}"><td>${k.title}<div class="faint">${k.id}${k.date ? ', ' + k.date : ''}</div></td>
        <td class="dim">${k.kind}</td><td class="r num dim">${k.trust}</td><td class="r num">${n(k.entries)}</td></tr>`)}</tbody></table>
      <p class="faint mt-s">Trust decides which source wins when two disagree: your teacher high, shared decks low. Open one to see its cards.</p></section>` : ''}
    <section class="box"><div class="t">reading in chat <span class="dim">no API spend</span></div><p class="muted-p">Your own Claude can read the units instead of the API:
      connect Panko once (<a href="#/setup">setup → chat mode</a>), then ask Claude to work through a source with Panko. What it submits shows up here, ready to ingest.</p></section>`);
  actions(el, { add: () => addForm() });
  if (r.q.add) addForm();
};

const KINDS = ['lesson', 'teacher-sheet', 'book', 'media', 'deck', 'notes'];
function addForm() {
  const box = $('#addbox');
  if (box.childElementCount) return $('#s-title')?.focus();
  let mode = 'upload', files = [];
  put(box, html`<section class="box accent"><div class="t">add a source</div>
    <div class="seg" id="s-mode"><button data-m="upload" class="on">upload files</button><button data-m="path">a path on this computer</button><button data-m="deck">an Anki deck</button></div>
    <div class="form mt">
      <div class="wide" data-for="upload"><div class="drop" id="drop">drop your files here, or <button class="link" type="button" id="pick">choose files</button>
        <input type="file" id="files" multiple hidden><div id="picked" class="acc mt-s"></div></div></div>
      <label class="f wide" data-for="path" hidden><span>file or folder</span><input id="s-path" placeholder="~/Documents/lessons/lesson-3.pdf"></label>
      <label class="f wide" data-for="deck" hidden><span>deck name, as Anki shows it <span class="faint">(Anki open; read only, nothing in it changes)</span></span><input id="s-deck" placeholder="Darija"></label>
      <label class="f"><span>title</span><input id="s-title" placeholder="Lesson 3: at the market"></label>
      <label class="f"><span>kind</span><select id="s-kind">${KINDS.map(k => html`<option>${k}</option>`)}</select></label>
      <label class="f"><span>date</span><input id="s-date" type="date"></label>
      <label class="f"><span title="your teacher high, a shared deck low">trust <span class="faint">0–100</span></span><input id="s-trust" type="number" min="0" max="100" value="70"></label>
      <details class="wide"><summary>more: pages of a PDF, people in a recording</summary><div class="form mt">
        <label class="f"><span>first page</span><input id="s-first" type="number" min="1" value="1"></label>
        <label class="f"><span>last page <span class="faint">0 = to the end</span></span><input id="s-last" type="number" min="0" value="0"></label>
        <label class="f"><span>page offset <span class="faint">printed = PDF page − this</span></span><input id="s-offset" type="number" value="0"></label>
        <label class="f"><span>speakers <span class="faint">comma separated</span></span><input id="s-speakers" placeholder="teacher, me"></label>
        <label class="f"><span>the learner is</span><input id="s-learner" placeholder="me"></label>
        <label class="f"><span>transcript you already have</span><input id="s-transcript" placeholder="~/lesson-3.txt"></label>
      </div></details>
    </div>
    <div class="acts mt"><button class="pri" id="s-go">add it</button><button data-a="cancel">cancel</button><span id="s-msg" class="dim"></span></div></section>`);
  const show_ = () => $$('[data-for]', box).forEach(x => { x.hidden = x.dataset.for !== mode; });
  $$('#s-mode button', box).forEach(b => { b.onclick = () => { mode = b.dataset.m; $$('#s-mode button', box).forEach(x => x.classList.toggle('on', x === b)); if (mode === 'deck') $('#s-kind').value = 'deck'; show_(); }; });
  const pickFiles = fs => {
    files = [...fs];
    put($('#picked'), files.length ? html`${files.length === 1 ? files[0].name : `${files.length} files: ${files.slice(0, 4).map(f => f.name).join(', ')}${files.length > 4 ? '…' : ''}`}` : '');
    if (files.length && !$('#s-title').value) $('#s-title').value = files[0].name.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ');
    const ext = files[0]?.name.split('.').pop().toLowerCase();
    if (/^(mp3|m4a|wav|ogg|flac|mp4|mov|webm)$/.test(ext || '')) $('#s-kind').value = 'lesson';
    else if (ext === 'pdf') $('#s-kind').value = 'book';
    else if (/^(jpe?g|png|heic|webp)$/.test(ext || '')) $('#s-kind').value = 'teacher-sheet';
  };
  $('#pick').onclick = () => $('#files').click();
  $('#files').onchange = e => pickFiles(e.target.files);
  const drop = $('#drop');
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
  drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); pickFiles(e.dataTransfer.files); };
  actions(box, { cancel: () => { box.innerHTML = ''; } });
  $('#s-go').onclick = async () => {
    const msg = $('#s-msg');
    const val = id => $(id).value.trim();
    const body = { title: val('#s-title'), kind: val('#s-kind'), date: val('#s-date'), trust: +val('#s-trust') || 70,
      first_page: +val('#s-first') || 1, last_page: +val('#s-last') || 0, page_offset: +val('#s-offset') || 0,
      speakers: val('#s-speakers'), learner: val('#s-learner'), transcript: val('#s-transcript') };
    if (!body.title) return put(msg, html`<span class="bad">give it a title</span>`);
    $('#s-go').disabled = true;
    try {
      if (mode === 'deck') {
        if (!val('#s-deck')) throw new Error('which deck?');
        await startJob('/sources', { ...body, deck: val('#s-deck') }, j => { if (j.result?.id) go(`#/sources/${encodeURIComponent(j.result.id)}`); });
        box.innerHTML = '';
        return;
      }
      if (mode === 'upload') {
        if (!files.length) throw new Error('choose a file first');
        put(msg, loading('uploading'));
        const fd = new FormData();
        files.forEach(f => fd.append('files', f));
        if (files.length > 1) fd.append('folder', body.title.toLowerCase().replace(/[^\w]+/g, '-').slice(0, 60));
        body.path = (await api('/upload', { form: fd })).path;
      } else body.path = val('#s-path');
      const s = await api('/sources', { body });
      toast(html`<span class="ok">✔</span> added ${body.title}: ${plural(s.units, 'unit')}`, 'ok');
      go(`#/sources/${encodeURIComponent(s.id)}`);
    } catch (e) { put(msg, html`<span class="bad">✘ ${e.message}</span>`); $('#s-go').disabled = false; }
  };
  show_();
  $('#s-title').focus();
}

async function sourceView(el, sid, r) {
  const d = await api(`/sources/${encodeURIComponent(sid)}`);
  const s = d.source, P = d.pending, units = d.units, pack = s.type === 'pack';
  const about = pack ? [html`a deck from the <a href="#/library">library</a>`, 'v' + (s.version || 1), s.date]
    : [...new Set([s.kind, s.type])].concat([s.date, 'trust ' + s.trust, s.minutes && s.minutes + ' min']);
  put(el, html`<div class="page-h"><a href="#/sources" class="dim">sources /</a><h1>${s.title}</h1><span class="sub">${about.filter(Boolean).map((x, i) => html`${i ? ', ' : ''}${x}`)}</span></div>
    <section class="box"><div class="t">units <span class="dim">${n(units.length)}</span></div>
      ${P.transcribe_first ? html`<p>This recording needs a transcript before it can be read (speech-to-text, paid).</p>
        <div class="acts mt"><button class="pri" data-a="transcribe"><span class="paid">$</span>transcribe it</button></div>` : html`
      <div class="legend"><span><i></i>to read ${n(P.todo)}</span><span><i class="submitted"></i>ready to ingest ${n(P.submitted)}</span><span><i class="held"></i>held ${n(P.held)}</span><span><i class="ingested"></i>ingested ${n(P.ingested)}</span></div>
      <div class="units">${units.map(u => html`<button class="${u.state} ${r.q.unit === u.unit ? 'on' : ''}" data-u="${u.unit}" title="${[u.unit, u.page && 'page ' + u.page, u.state, u.items && u.items + ' items'].filter(Boolean).join(', ')}">${u.unit}</button>`)}</div>
      ${pack ? html`<p class="muted-p">A deck's cards are already written and checked, so there's nothing to read: they went through the same duplicate checks as any source.
        <a href="#/cards?status=all&tag=${encodeURIComponent('src::pack::' + sid)}">See its cards</a>.</p>
        ${P.submitted ? html`<div class="acts mt"><button data-a="ingest">ingest ${plural(P.submitted, 'ready unit')}</button></div>` : ''}` : html`
      <div class="acts">
        <label class="dim">next <input id="run-n" type="number" min="1" max="200" value="${Math.max(1, Math.min(5, P.todo))}"> units</label>
        <button class="${d.llm_ready ? 'pri' : ''}" data-a="run" ${P.todo && d.llm_ready ? '' : 'disabled'}><span class="paid">$</span>read them with the model</button>
        <button data-a="ingest" ${P.submitted ? '' : 'disabled'}>ingest ${plural(P.submitted, 'ready unit')}</button>
      </div>
      ${d.llm_ready ? '' : html`<p class="faint mt-s">Reading with the model needs an API key: <a href="#/setup">add <code>ANTHROPIC_API_KEY</code> in setup</a>.</p>`}
      ${P.todo ? html`<details class="mt-s" ${d.llm_ready ? '' : 'open'}><summary>or read it in chat, free</summary>
        <p class="muted-p mt-s">With Panko connected to your own Claude (<a href="#/setup">setup → chat mode</a>), ask it:</p>
        <div class="snippet mt-s"><pre>Work through the Panko source "${s.title}" (${sid}) and submit each unit.</pre></div>
        <p class="faint mt-s">What it submits shows up here as ready to ingest.</p></details>` : ''}`}`}
    </section>
    ${P.held.length ? heldBox(P.held, sid) : ''}
    <div id="unitbox"></div>`);
  const reload = () => sourceView(el, sid, S.route);
  actions(el, {
    transcribe: () => paidAction(`/sources/${encodeURIComponent(sid)}/transcribe`, {}, `transcribe ${s.title}?`, { batch: false, onDone: reload }),
    run: () => { const k = +$('#run-n').value || 5; paidAction(`/sources/${encodeURIComponent(sid)}/run`, { n: k }, `read ${plural(k, 'unit')} of ${s.title}?`, { onDone: reload }); },
    ingest: () => startJob(`/sources/${encodeURIComponent(sid)}/ingest`, {}, reload),
    same: async b => { await decide(sid, b.dataset.unit, b.dataset.ar, b.dataset.known, false); reload(); },
    distinct: async b => { await decide(sid, b.dataset.unit, b.dataset.ar, '', true); reload(); },
  });
  $$('.units button', el).forEach(b => { b.onclick = () => { $$('.units button', el).forEach(x => x.classList.toggle('on', x === b)); unitView(sid, b.dataset.u); }; });
  if (r.q.unit) unitView(sid, r.q.unit);
}

async function decide(sid, unit, ar, known, distinct) {
  try {
    await api(`/sources/${encodeURIComponent(sid)}/decide`, { body: { unit, ar, known_id: known, distinct } });
    toast(html`<span class="ok">✔</span> decided ${ar}<div class="dim">Ingest again to bring it in.</div>`, 'ok');
  } catch (e) { toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); }
}

function heldBox(held, sid) {
  return html`<section class="box warn"><div class="t">held <span class="dim">${n(held.length)} to decide</span></div>
    <p class="muted-p">These look like words you already have. Say whether each is the same word, or a different one.</p>
    ${held.map(h => html`<div class="match"><div>${tgt(h.ar, '')} <span class="dim">${h.tl || ''}</span> ${h.gloss} <span class="faint">${h.unit}</span></div>
      <div class="faint">${h.why}</div>
      ${(h.matches || []).map(m => html`<div class="mt-s">→ <a href="#/cards?status=all&id=${m.id}">${m.id}</a> ${tgt(m.ar, '')} <span class="dim">${m.tl || ''}</span> ${m.gloss || ''}
        <button data-a="same" data-unit="${h.unit}" data-ar="${h.ar}" data-known="${m.id}">same word</button></div>`)}
      <div class="acts mt-s"><button data-a="distinct" data-unit="${h.unit}" data-ar="${h.ar}">a different word</button></div></div>`)}
  </section>`;
}

async function unitView(sid, u) {
  const box = $('#unitbox');
  put(box, html`<section class="box"><div class="t">${u}</div>${loading()}</section>`);
  history.replaceState(null, '', `#/sources/${encodeURIComponent(sid)}?unit=${u}`);
  try {
    const d = await api(`/sources/${encodeURIComponent(sid)}/units/${u}`);
    put(box, html`<section class="box"><div class="t">${u} <span class="dim">${d.page ? `page ${d.page}, ` : ''}${d.state}</span></div>
      <div class="unit-view">${d.image ? html`<img src="${d.image}" alt="page ${d.page || u}" loading="lazy">` : ''}${d.layer_state
        ? html`<div class="layer"><p class="layer-note ${d.layer_state === 'ok' ? 'dim' : 'warn'}">${d.layer_state === 'none' ? d.layer_note : html`<b>Text in the PDF:</b> ${d.layer_note}.`}</p>
          ${d.layer ? html`<details ${d.layer_state === 'ok' ? 'open' : ''}><summary>${d.layer_state === 'ok' ? 'the text' : 'show it anyway'}</summary><pre dir="auto">${d.layer}</pre></details>` : ''}</div>`
        : d.text ? html`<pre dir="auto">${d.text}</pre>` : ''}${!d.image && !d.text && !d.layer ? html`<p class="empty">Nothing to show.</p>` : ''}</div>
      ${d.items.length ? html`<p class="dim mt">${plural(d.items.length, 'item')} read from it</p><table class="t"><tbody>${d.items.map(it => html`<tr><td>${tgt(it.ar, it.variety)}</td><td class="dim">${it.tl || ''}</td><td>${it.gloss || ''}</td><td class="nw">${it.verdict?.verdict ? html`<span class="flag ${it.verdict.verdict}">${it.verdict.verdict}</span>` : ''}${it.known_id ? html`<span class="flag">known</span>` : ''}</td></tr>`)}</tbody></table>`
        : html`<p class="faint mt">Not read yet.</p>`}
    </section>`);
  } catch (e) { put(box, html`<section class="box"><div class="t">${u}</div>${errorBox(e)}</section>`); }
}

// ---- checks -------------------------------------------------------------------------------------------------------
VIEWS.checks = async el => {
  const vs = S.meta.varieties;
  put(el, html`<div class="page-h"><h1>checks</h1><span class="sub">free tools first; the model only when you ask</span></div>
    <section class="box"><div class="t">tool checks <span class="dim">free</span></div>
      <p class="muted-p">Words with an analyser are checked for spelling, harakat and root; the rest are looked up in your references.
        A hard problem holds a candidate back as <span class="warn">doubtful</span>: it stays out of Anki until you fix it or activate it yourself.</p>
      <div class="kv mt">${vs.map(v => html`<span class="k">${v.title}</span><span class="v">${v.analyser ? html`<span class="ok">●</span> ${v.analyser}` : html`<span class="faint">○ references only</span>`}</span>`)}</div>
      <div class="acts mt"><select id="v-status" aria-label="which entries"><option value="candidate">the inbox</option><option value="active">active cards</option><option value="all">both</option></select>
        <button data-a="verify">run the checks</button><button class="pri" data-a="verify-apply">run and hold doubtful ones</button></div>
      <div id="v-out"></div>
    </section>
    <section class="box"><div class="t">gloss clashes</div><div id="cl">${loading()}</div></section>`);
  const showVerify = j => {
    const r = j.result;
    if (!r) return;
    const row = x => html`<tr><td><a href="#/cards?status=all&id=${x.id}">${x.id}</a></td><td>${tgt(x.ar, '')}</td><td>${x.problems.map(p => html`<div><span class="flag ${p.problem === 'unknown' ? '' : 'check'}">${p.problem}</span>${p.field}: ${tgt(p.text, '')}${p.suggest ? html` → ${tgt(p.suggest, '')}` : ''}</div>`)}</td></tr>`;
    put($('#v-out'), html`<hr><p>analyser: ${plural(r.checked, 'entry', 'entries')}, <span class="ok">${n(r.fine)} fine</span>, <span class="warn">${n(r.doubtful.length)} doubtful</span>, ${n(r.listed.length)} noted${r.applied ? html`, <span class="acc">${n(r.tagged)} newly held</span>` : ''}</p>
      <p>references: <span class="${r.ungrounded.length ? 'warn' : 'ok'}">${plural(r.ungrounded.length, 'word')}</span> found in none of them</p>
      ${r.doubtful.length ? html`<details open><summary>doubtful</summary><table class="t"><tbody>${r.doubtful.slice(0, 200).map(row)}</tbody></table></details>` : ''}
      ${r.listed.length ? html`<details><summary>noted (not held)</summary><table class="t"><tbody>${r.listed.slice(0, 200).map(row)}</tbody></table></details>` : ''}
      ${r.ungrounded.length ? html`<details><summary>in no reference</summary><table class="t"><tbody>${r.ungrounded.slice(0, 300).map(u => html`<tr><td><a href="#/cards?status=all&id=${u.id}">${u.id}</a></td><td>${tgt(u.ar, '')}</td><td class="dim">${u.tl || ''}</td><td>${u.gloss || ''}</td></tr>`)}</tbody></table></details>` : ''}`);
  };
  actions(el, {
    verify: () => startJob('/verify', { status: $('#v-status').value }, showVerify),
    'verify-apply': () => startJob('/verify', { status: $('#v-status').value, apply: true }, showVerify),
    'cl-decide': b => paidAction('/clashes/decide', { all: b.dataset.all === '1' }, 'let the model suggest for the groups you haven’t chosen for?', { batch: false, onDone: () => clashes() }),
    'cl-apply': async () => {
      if (!await confirmIt(`apply ${plural(clPending(), 'change')}?`, html`<p>New glosses are written and some cards become recognition only. An inbox card that is the same word as another moves to duplicates; a card already in Anki is never removed (it becomes recognition only and is listed for you).</p>`)) return;
      try {
        const r = await api('/clashes/apply', { body: {} });
        toast(html`<span class="ok">✔</span> ${[r.gloss && `${n(r.gloss)} new gloss${r.gloss === 1 ? '' : 'es'}`, r.recognition && `${n(r.recognition)} recognition only`, r.duplicates && `${n(r.duplicates)} to duplicates`, r.retired && `${n(r.retired)} dropped`].filter(Boolean).join(', ') || 'nothing to change'}${r.for_you.length ? html`; already in Anki, so made recognition only: ${r.for_you.map(f => f.id).join(', ')}` : ''}`, 'ok', 15000);
        clashes();
      } catch (e) { toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); }
    },
    'cl-fine': b => clFine(b.dataset.key),
    'cl-all': b => clashes(b.dataset.all === '1'),
  });
  clashes(false);
};


/* Gloss clashes: each card gets a choice (yours, or the model's suggestion until you change it); a group can be called
   fine as it is. Choices save as you make them, and only the changed row repaints, so the list keeps its place. */
const CL = { all: false, dec: {}, groups: {}, total: 0, undecided: 0 };
const clChoice = d => !d || d.keep ? 'keep' : d.gloss ? 'gloss' : d.cards ? 'recognition' : d.same ? 'same:' + d.same : d.drop ? 'drop' : 'keep';
const clPending = () => Object.values(CL.dec).filter(d => !d.keep).length;

function clCard(x, g, editing = false) {
  const d = CL.dec[x.id], c = editing ? 'gloss' : clChoice(d), on = v => v === c ? 'selected' : '';
  return html`<span class="who"><a href="#/cards?status=all&id=${x.id}">${x.id}</a> ${tgt(x.ar, '')} <span class="dim">${x.tl}</span> ${x.gloss} <span class="flag ${x.status}">${STATUS_NAME[x.status]}</span></span>
    <span class="pick"><select data-cl="${x.id}" aria-label="what to do with ${x.id}">
      <option value="keep" ${on('keep')}>keep</option>
      <option value="gloss" ${on('gloss')}>new gloss…</option>
      <option value="recognition" ${on('recognition')}>recognition only</option>
      ${g.entries.filter(o => o.id !== x.id).map(o => html`<option value="same:${o.id}" ${on('same:' + o.id)}>same as ${o.id}</option>`)}
      ${c === 'drop' ? html`<option value="drop" selected>drop: ${d.drop}</option>` : ''}
    </select>${d && !d.keep && d.by !== 'you' ? html`<span class="faint" title="the model’s suggestion; change it if you disagree">suggested</span>` : ''}
    ${c === 'gloss' ? html`<input class="cl-gloss" data-cl-gloss="${x.id}" value="${d?.gloss || x.gloss}" aria-label="new gloss for ${x.id}" spellcheck="false">` : ''}</span>`;
}

function clHead() {
  const p = clPending();
  put($('#cl-head'), html`<p class="muted-p">Production cards show the gloss and ask for the word, so two cards with the same gloss can't both be right.
      ${n(CL.total)} group${CL.total === 1 ? '' : 's'} ${CL.all ? 'across everything' : 'touch your inbox'}. Choose for each card here, or let the model suggest and look over what it says.</p>
    <div class="acts mt"><div class="seg"><button data-a="cl-all" data-all="0" class="${CL.all ? '' : 'on'}">inbox</button><button data-a="cl-all" data-all="1" class="${CL.all ? 'on' : ''}">everything</button></div>
      <button data-a="cl-decide" data-all="${CL.all ? 1 : 0}" ${CL.undecided ? '' : 'disabled'} title="only the groups you haven't chosen for"><span class="paid">$</span>let the model suggest${CL.undecided && CL.undecided < CL.total ? ` (${n(CL.undecided)})` : ''}</button>
      <button class="${p ? 'pri' : ''}" data-a="cl-apply" ${p ? '' : 'disabled'}>apply ${plural(p, 'change')}</button></div>`);
}

async function clashes(all = CL.all) {
  const box = $('#cl');
  if (!box) return;
  CL.all = all;
  put(box, loading('finding clashes'));
  try {
    const d = await api('/clashes' + (all ? '?all=1' : ''));
    Object.assign(CL, { dec: d.decisions || {}, total: d.total, undecided: d.undecided, groups: {} });
    d.groups.forEach(g => g.entries.forEach(x => { CL.groups[x.id] = [x, g]; }));
    put(box, html`<div id="cl-head"></div>
      ${d.groups.length ? html`<table class="t mt clashes"><tbody>${d.groups.map(g => html`<tr data-key="${g.key}"><td class="sense"><div>“${g.sense}”</div>
          <button class="ghost sm" data-a="cl-fine" data-key="${g.key}" title="these cards are clear as they are: leave them and stop showing this group">these are fine</button></td>
          <td>${g.entries.map(x => html`<div class="cl-card" data-id="${x.id}">${clCard(x, g)}</div>`)}</td></tr>`)}</tbody></table>
          ${d.total > d.groups.length ? html`<p class="faint mt-s">The first ${n(d.groups.length)}; the rest show as these are settled.</p>` : ''}`
        : html`<p class="empty mt">No clashes${d.fine ? html` <span class="dim">(${plural(d.fine, 'group')} you called fine)</span>` : ''}.</p>`}`);
    clHead();
  } catch (e) { put(box, errorBox(e)); }
  box.onchange = async ev => {
    const sel = ev.target.closest('select[data-cl]'), inp = ev.target.closest('input[data-cl-gloss]');
    const id = sel?.dataset.cl || inp?.dataset.clGloss;
    if (!id || !CL.groups[id]) return;
    const [x, g] = CL.groups[id], row = ev.target.closest('.cl-card');
    if (sel && sel.value === 'gloss') { put(row, clCard(x, g, true)); const i = $('input', row); i.focus(); i.select(); return; }
    if (sel && sel.value === 'drop') return;
    const [choice, same] = inp ? ['gloss'] : sel.value.split(':');
    try {
      const r = await api('/clashes/choose', { body: { id, choice, same, gloss: inp?.value } });
      CL.dec[id] = r.decision;
      if (!CL.dec[id]) delete CL.dec[id];
      put(row, clCard(x, g));
      clHead();
    } catch (e) { toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); put(row, clCard(x, g)); }
  };
  box.onkeydown = ev => { if (ev.key === 'Enter' && ev.target.matches('input[data-cl-gloss]')) ev.target.blur(); };
}

async function clFine(key, undo = false) {
  try {
    await api('/clashes/fine', { body: { key, undo } });
    if (undo) return clashes();
    $(`#cl tr[data-key="${CSS.escape(key)}"]`)?.remove();
    key.split('|').forEach(i => delete CL.dec[i]);
    CL.total--; clHead();
    toast(html`<span class="ok">✔</span> left as they are <button class="link" data-unfine="${key}">undo</button>`, 'ok', 9000);
  } catch (e) { toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); }
}
document.addEventListener('click', e => { const b = e.target.closest('[data-unfine]'); if (b) { b.closest('.toast')?.remove(); clFine(b.dataset.unfine, true); } });

// ---- library ------------------------------------------------------------------------------------------------------
VIEWS.library = async el => {
  const d = await api('/library');
  const mb = b => `${Math.max(1, Math.round((b || 0) / 1e6))} MB`;
  const file = (x, k) => (x.files || []).find(f => f.kind === k);
  const deck = x => {
    const c = x.counts || {}, pack = file(x, 'pack'), apkg = file(x, 'apkg');
    return html`<section class="box deck ${x.fits ? '' : 'off'}"><div class="t">${x.title} <span class="dim">v${x.version || 1}</span></div>
      ${x.description ? html`<p>${x.description}</p>` : ''}
      <p class="dim">${x.language}${(x.varieties || []).length ? ' · ' + x.varieties.join(', ') : ''} · ${n(c.words)} words, ${n(c.phrases)} phrases ·
        ${n(c.pictures)} pictures · ${n(c.audio)} audio clips${pack ? ` · ${mb(pack.bytes)}` : ''}</p>
      ${(x.samples || []).length ? html`<ul class="samples">${x.samples.map(e => html`<li>${tgt(e.ar, (x.varieties || [])[0] || '')} <span class="dim">${e.tl}</span> ${e.gloss}</li>`)}</ul>` : ''}
      <p class="faint">Card text ${x.licence || ''}. Pictures: ${Object.entries(x.picture_licences || {}).map(([k, v]) => `${k} ${n(v)}`).join(', ') || 'none'}.${x.audio ? ' Audio made with speech synthesis.' : ''}</p>
      <div class="acts mt">
        ${!x.fits ? html`<span class="warn">${x.why_not}</span>`
          : x.update ? html`<span class="dim">you have v${x.have}; taking the new version over yours isn't built yet</span>`
          : x.have ? html`<span class="ok">✔ in your Panko</span> <a href="#/sources/${encodeURIComponent('pack-' + x.id)}">see its cards</a>`
          : html`<button class="pri" data-a="get" data-id="${x.id}">add to my Panko</button>
            <label class="chk-l"><input type="checkbox" data-act="${x.id}"> make its new cards active</label>`}
        ${apkg?.url ? html`<a class="faint" href="${apkg.url}" target="_blank" rel="noopener">.apkg for Anki without Panko (${mb(apkg.bytes)})</a>` : ''}
      </div></section>`;
  };
  const fits = d.decks.filter(x => x.fits), others = d.decks.filter(x => !x.fits);
  put(el, html`<div class="page-h"><h1>library</h1><span class="sub">ready-made decks, checked, to build on</span></div>
    ${d.error === 'no library set' ? html`<section class="box"><div class="t">no library set</div>
        <p class="muted-p">Panko reads the library's list of decks from <code>[library] index</code> in your config (a web address or a file),
        or from the library repo named in <code>[library] repo</code>. Set one, then reload.</p></section>`
      : d.error ? html`<section class="box warn"><div class="t">the library can't be reached</div><p class="muted-p">${d.error}</p>
        <p class="faint">From <code>${tilde(d.source)}</code>. You can still add a pack you have as a file: <code>panko library import FILE</code>.</p></section>`
      : !d.decks.length ? html`<section class="box"><p class="empty">The library has no decks yet.</p></section>`
      : html`<p class="muted-p">Adding a deck works like adding any source: a word you already have keeps your card (and gains the deck's sentences),
          a near one waits for you on the source's page, a word you rejected stays rejected, and the rest land in your inbox. Downloads go to <code>${tilde(d.dir)}</code>.</p>
        ${fits.map(deck)}
        ${others.length ? html`<details class="mt"><summary>${plural(others.length, 'deck')} for other languages or varieties</summary>${others.map(deck)}</details>` : ''}`}`);
  actions(el, {
    get: async b => {
      const x = d.decks.find(k => k.id === b.dataset.id), pack = file(x, 'pack');
      const act = $(`[data-act="${x.id}"]`, el)?.checked;
      if (!await confirmIt(`add ${x.title}?`, html`<p>Downloads ${mb(pack?.bytes)} (checked against the library's list), then adds its
        ${n((x.counts?.words || 0) + (x.counts?.phrases || 0))} cards through the usual checks. ${act ? 'New cards become active straight away.' : 'New cards land in your inbox.'} Free.</p>`)) return;
      startJob('/library/get', { id: x.id, activate: !!act }, () => VIEWS.library(el));
    },
  });
};

// ---- pictures -----------------------------------------------------------------------------------------------------
const PIC = { page: { decisions: 0, waiting: 0 }, key: '' };
const PIC_PAGE = 100;
/* one page of rows and a pager under it ("101–200 of 770  ‹ ›") */
const paged = (rows, which, row, head) => {
  const pages = Math.max(1, Math.ceil(rows.length / PIC_PAGE)), p = Math.min(PIC.page[which], pages - 1);
  const from = p * PIC_PAGE, shown = rows.slice(from, from + PIC_PAGE);
  return html`<table class="t mt">${head}<tbody>${shown.map(row)}</tbody></table>
    ${pages > 1 ? html`<div class="pager"><span class="dim">${n(from + 1)}–${n(from + shown.length)} of ${n(rows.length)}</span>
      <button data-a="page" data-w="${which}" data-p="${p - 1}" ${p ? '' : 'disabled'} >← prev</button>
      <button data-a="page" data-w="${which}" data-p="${p + 1}" ${p < pages - 1 ? '' : 'disabled'} >next →</button></div>` : ''}`;
};

VIEWS.pictures = async (el, r) => {
  const status = r.q.status || 'active', tag = r.q.tag || '';
  if (PIC.key !== status + '|' + tag) { PIC.key = status + '|' + tag; PIC.page = { decisions: PIC.page.decisions, waiting: 0 }; }
  const d = await api('/pictures?' + new URLSearchParams({ status, tag }));
  const kind = x => x.photo ? html`<span class="ok">photo</span>` : x.prompt ? html`<span class="violet">drawing</span>` : x.skip ? html`<span class="faint">none</span>` : '';
  const peek = x => x.file ? `/media/${encodeURIComponent(x.file)}` : x.thumb || '';
  const waiting = d.cards.length;
  put(el, html`<div class="page-h"><h1>pictures</h1><span class="sub">real photos first; a drawing only when no photo fits</span></div>
    <section class="box"><div class="t">to do</div>
      <p><span class="acc big">${n(d.todo)}</span> ${status} card${d.todo === 1 ? '' : 's'}${tag ? ` tagged ${tagName(tag)}` : ''} without a picture or a decision.
        ${d.none ? html`<span class="dim">${plural(d.none, 'card')} set to no picture.</span>` : ''}</p>
      <p class="muted-p">The model plans a search per card, looks through contact sheets from your picture sources and picks a photo.
        When nothing fits it writes a drawing prompt, if you allow drawings. Or choose one yourself, free: <b>choose a photo</b> on any card below.
        <a href="#/design">Choose the sources</a> in card design.</p>
      <div class="acts mt"><div class="seg"><button data-a="st" data-s="active" class="${status === 'active' ? 'on' : ''}">active</button><button data-a="st" data-s="candidate" class="${status === 'candidate' ? 'on' : ''}">inbox</button></div>
        <label class="dim">at most <input id="p-lim" type="number" min="1" value="${Math.min(50, d.todo || 50)}"> cards</label>
        <button class="pri" data-a="decide" ${d.todo ? '' : 'disabled'}><span class="paid">$</span>choose pictures</button></div>
    </section>
    <details class="box" data-fold="pictures-decisions"><summary class="t">decisions <span class="dim">${n(d.decisions.length)}</span></summary>
      ${d.decisions.length ? html`<div class="acts"><button data-a="apply" ${d.decisions.some(x => x.photo && !x.applied) ? '' : 'disabled'} title="download each photo the model chose and put it on its card">download the chosen photos</button>
        ${d.decisions.some(x => x.photo && !x.applied) ? '' : html`<span class="faint">every chosen photo is on its card</span>`}
        ${d.drawings_waiting ? html`<span class="dim">${plural(d.drawings_waiting, 'drawing')} waiting: <code>uv run panko draw data/pictures/drawings.json --batch</code></span>` : ''}</div>` : ''}
      ${d.decisions.length ? paged(d.decisions, 'decisions', x => html`<tr>
        <td class="nw"><a href="#/cards?status=all&id=${x.id}">${x.id}</a></td>
        <td>${peek(x) ? html`<span class="peekable" data-peek="${peek(x)}">${tgt(x.ar, '')}</span>` : tgt(x.ar, '')}</td><td class="cut" style="max-width:240px">${x.gloss}</td>
        <td class="nw">${kind(x)}${x.by === 'you' ? html` <span class="faint">by you</span>` : ''}</td>
        <td class="dim why" title="${x.prompt || x.skip || ''}">${x.applied ? html`<span class="ok">✔</span> ` : ''}${x.prompt || x.skip || ''}</td>
        <td class="r nw"><button class="nopic" data-a="choose" data-id="${x.id}">${x.applied ? 'change photo' : 'choose a photo'}</button></td></tr>`,
        html`<thead><tr><th>card</th><th>word</th><th>gloss</th><th>choice</th><th>why</th><th></th></tr></thead>`) : html`<p class="empty">None yet.</p>`}
    </details>
    <details class="box" data-fold="pictures-waiting"><summary class="t">waiting for a picture <span class="dim">${n(d.todo)}</span></summary>
      <div class="acts"><select id="p-tag" aria-label="tag"><option value="">any tag</option>${d.tags.map(([t, k]) => html`<option value="${t}" ${t === tag ? 'selected' : ''}>${tagName(t)} (${n(k)})</option>`)}</select>
        ${tag && d.todo ? html`<button data-a="none-all">mark all ${n(d.todo)} as no picture</button>` : html`<span class="faint">some cards are better without one, such as prayers or grammar words: pick a tag to set them all at once</span>`}</div>
      ${waiting ? paged(d.cards, 'waiting', c => html`<tr class="row" data-href="#/cards?status=all&id=${c.id}"><td class="nw faint">${c.id}</td><td>${tgt(c.ar, '')}</td><td class="dim">${c.tl || ''}</td><td>${c.gloss}</td>
        <td class="r two"><button class="nopic" data-a="choose" data-id="${c.id}">choose a photo</button><button class="nopic" data-a="none" data-id="${c.id}" title="this card is better without a picture">mark as no picture</button></td></tr>`,
        html`<thead><tr><th>card</th><th>word</th><th>transliteration</th><th>gloss</th><th></th></tr></thead>`) : html`<p class="empty mt">Nothing waiting.</p>`}</details>`);
  $('#p-tag').onchange = e => go('#/pictures?' + new URLSearchParams({ status, tag: e.target.value }));
  const redraw = () => VIEWS.pictures(el, r);
  const none = async (ids, undo = false) => {
    try {
      const x = await api('/pictures/none', { body: { ids, undo } });
      toast(html`<span class="ok">✔</span> ${plural(x.changed.length, 'card')} ${undo ? 'back in the picture queue' : 'set to no picture'}${undo ? '' : html` <button class="link" data-undo="${x.changed.join(',')}">undo</button>`}`, 'ok', 9000);
      redraw();
    } catch (e) { toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); }
  };
  S.undoNone = ids => none(ids, true);
  const row = id => d.decisions.find(x => x.id === id) || d.cards.find(x => x.id === id) || { id };
  actions(el, {
    st: b => go('#/pictures?' + new URLSearchParams({ status: b.dataset.s, tag })),
    page: b => { PIC.page[b.dataset.w] = +b.dataset.p; redraw(); },
    none: b => none([b.dataset.id]),
    choose: b => choosePhoto(row(b.dataset.id), redraw),
    'none-all': async () => { if (await confirmIt(`no picture for ${plural(d.todo, 'card')} tagged ${tagName(tag)}?`, html`<p>They leave the picture queue. You can undo it, or ask for a picture on any one of them from its edit form.</p>`)) none(d.ids); },
    decide: () => paidAction('/pictures/decide', { status, tag, limit: +$('#p-lim').value || 0 }, 'choose pictures with the model?', { batch: false, onDone: redraw }),
    apply: () => startJob('/pictures/apply', {}, redraw),
  });
};

/* Choose a photo for one card yourself: the model's candidates if it searched, else a search of your picture
   sources (free). Clicking one puts it on the card straight away. */
async function choosePhoto(card, onDone) {
  const L = $('#layer'), before = document.activeElement;
  let busy = false;
  const close = () => { document.removeEventListener('keydown', key, true); L.innerHTML = ''; tipHide(); peekHide(); before?.focus?.(); };
  const key = e => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); } };
  document.addEventListener('keydown', key, true);
  const frame = inner => put(L, html`<div class="back"><div class="box modal chooser" role="dialog" aria-modal="true" aria-labelledby="ch-t" tabindex="-1">
    <div class="t" id="ch-t">choose a photo · ${tgt(card.ar || '', '')} <span class="dim">${card.gloss || ''}</span></div>${inner}</div></div>`);
  const show = res => {
    frame(html`<form class="acts" id="ch-f"><input id="ch-q" value="${res.query}" aria-label="search for" placeholder="search for…" style="flex:1">
        <button>search</button><span class="faint">${res.from} · free</span></form>
      ${res.candidates.length ? html`<div class="grid-pics mt">${res.candidates.map(c => html`<button class="pic ${res.chosen === c.i ? 'on' : ''}" data-i="${c.i}" title="${c.title}">
          <img src="${c.thumb}" alt="${c.title}" loading="lazy" referrerpolicy="no-referrer" data-peek="${c.thumb}">
          <span class="lic">${c.provider} · ${c.license || 'licence unknown'}</span></button>`)}</div>
        <p class="faint mt-s">Click one to put it on the card. ${res.chosen != null ? 'The outlined one is what the model chose.' : ''}</p>`
        : html`<p class="empty mt">Nothing found for “${res.query}”. Try other words.</p>`}`);
    $('.back', L).onclick = ev => { if (ev.target.classList.contains('back')) close(); };
    $('#ch-f', L).onsubmit = ev => { ev.preventDefault(); load($('#ch-q', L).value.trim()); };
    for (const b of $$('.pic', L)) b.onclick = async () => {
      if (busy) return;
      busy = true; b.classList.add('wait');
      try {
        await api('/pictures/choose', { body: { id: card.id, dir: res.dir, index: +b.dataset.i } });
        close();
        toast(html`<span class="ok">✔</span> photo on ${card.id} ${tgt(card.ar || '', '')}`, 'ok', 6000);
        onDone?.();
      } catch (e) { busy = false; b.classList.remove('wait'); toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); }
    };
    $('.modal', L).focus({ preventScroll: true });
  };
  const load = async q => {
    frame(html`<p class="dim">${q ? `searching for “${q}”…` : 'looking for photos…'}</p>`);
    $('.back', L).onclick = ev => { if (ev.target.classList.contains('back')) close(); };
    try { show(await api('/pictures/candidates?' + new URLSearchParams({ id: card.id, q: q || '' }))); }
    catch (e) { close(); toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); }
  };
  load('');
}

/* a bigger look at a picture on hover ([data-peek] = its address), after a short pause like link previews elsewhere */
const PEEK_DELAY = 350;
let peekTimer = 0, peekAt = { clientX: 0, clientY: 0 };
const peekShow = q => {
  let p = $('#peek');
  if (!p) { p = document.createElement('div'); p.id = 'peek'; p.hidden = true; p.innerHTML = '<img alt="">'; document.body.append(p); }
  const img = p.firstChild;
  if (img.getAttribute('src') !== q.dataset.peek) { img.referrerPolicy = 'no-referrer'; img.src = q.dataset.peek; }
  p.hidden = false;
  peekMove(peekAt);
};
const peekMove = ev => {
  peekAt = { clientX: ev.clientX, clientY: ev.clientY };
  const p = $('#peek'); if (!p || p.hidden) return;
  const w = p.offsetWidth || 200, h = p.offsetHeight || 160;
  p.style.left = (ev.clientX + 16 + w > innerWidth ? ev.clientX - 16 - w : ev.clientX + 16) + 'px';
  p.style.top = Math.max(8, Math.min(innerHeight - h - 8, ev.clientY - h / 2)) + 'px';
};
const peekHide = () => { clearTimeout(peekTimer); const p = $('#peek'); if (p) p.hidden = true; };
document.addEventListener('mouseover', e => {
  const q = e.target.closest?.('[data-peek]');
  if (!q || q.contains(e.relatedTarget)) return;            // moving between the word's own parts isn't a new hover
  clearTimeout(peekTimer); peekAt = e;
  peekTimer = setTimeout(() => peekShow(q), PEEK_DELAY);
});
document.addEventListener('mousemove', e => { if (e.target.closest?.('[data-peek]')) peekMove(e); });
document.addEventListener('mouseout', e => { const q = e.target.closest?.('[data-peek]'); if (q && !q.contains(e.relatedTarget)) peekHide(); });

// ---- sync ---------------------------------------------------------------------------------------------------------
VIEWS.sync = async el => {
  const hosted = !!S.meta.hosted;
  put(el, html`<div class="page-h"><h1>sync</h1><span class="sub">active cards → Anki, updated in place</span></div>
    ${hosted ? html`<section class="box warn"><div class="t">to Anki from the server</div><p class="muted-p">Syncing straight into your Anki needs the Panko add-on, which is coming. Until then, make an .apkg below and open it in Anki: it adds the cards, and a newer one updates them in place.</p></section>` : html`<section class="box warn"><div class="t">before you sync</div><ul class="arrows">
      <li>Anki is open, with the MCP add-on listening on 127.0.0.1:3141.</li>
      <li>Panko writes only its own notes, decks and note types. Your review history stays, and your MyNotes field is never written.</li>
      <li>Template and CSS changes go through a normal sync; nothing here forces a full one.</li>
      <li>Audio for new text is made on the way (paid). The plan shows how much first.</li></ul></section>
    <section class="box"><div class="t">plan <span class="dim">free, no Anki needed</span></div>
      <div class="acts"><button class="pri" data-a="plan">check what a sync would do</button></div><div id="plan">${S.plan ? '' : ''}</div></section>`}
    <section class="box" id="share"><div class="t">share as a file</div>
      <p class="muted-p">An Anki package (.apkg) of your active cards, for a friend: they open it and Anki adds the decks. It has the pictures and the audio already made, and no review history, so they start fresh. Your Anki isn't touched.</p>
      <div class="acts mt">${S.meta.varieties.length > 1 ? S.meta.varieties.map(v => html`<label class="chk-l"><input type="checkbox" data-var="${v.name}" checked> ${v.title}</label>`) : ''}
        <label class="chk-l" title="source names can name your teacher, and clips are cut from your lessons"><input type="checkbox" id="x-personal"> include where each word came from and clips from your lessons</label></div>
      <div class="acts mt"><button data-a="export">make the .apkg</button><span id="x-out" class="dim"></span></div></section>`);
  const showPlan = j => {
    const p = j.result;
    S.plan = p;
    if (!p) return;
    const list = (rows, total) => rows.length ? html`<table class="t"><tbody>${rows.map(x => html`<tr class="row" data-href="#/cards?status=active&id=${x.id}"><td class="nw faint">${x.id}</td><td>${tgt(x.ar, x.variety)}</td><td>${x.gloss}</td></tr>`)}</tbody></table>${total > rows.length ? html`<p class="faint">…and ${n(total - rows.length)} more</p>` : ''}` : '';
    put($('#plan'), html`<hr><div class="kv"><span class="k">add</span><span class="v acc">${n(p.add_count)}</span><span class="k">update</span><span class="v">${n(p.update_count)}</span>
      <span class="k">unchanged</span><span class="v dim">${n(p.unchanged)}</span><span class="k">audio to make</span><span class="v ${p.audio_clips ? 'warn' : 'dim'}">${p.audio_clips ? `${plural(p.audio_clips, 'clip')}, ${n(p.audio_total)} characters (paid)` : 'none'}</span></div>
      <div class="acts mt"><button class="pri" data-a="sync" ${p.add_count + p.update_count + p.audio_clips ? '' : 'disabled'}>${p.audio_clips ? html`<span class="paid">$</span>` : ''}sync now</button></div>
      ${p.add_count ? html`<details class="mt"><summary>new notes (${n(p.add_count)})</summary>${list(p.add, p.add_count)}</details>` : ''}
      ${p.update_count ? html`<details class="mt-s"><summary>notes to update (${n(p.update_count)})</summary>${list(p.update, p.update_count)}</details>` : ''}`);
  };
  actions(el, {
    export: b => {
      const varieties = $$('[data-var]', el).filter(x => x.checked).map(x => x.dataset.var);
      if (S.meta.varieties.length > 1 && !varieties.length) return put($('#x-out'), html`<span class="warn">pick at least one</span>`);
      b.disabled = true;
      put($('#x-out'), loading('packing the cards and their media'));
      startJob('/export/apkg', { varieties, personal: $('#x-personal').checked }, j => {
        b.disabled = false;
        const r = j.result;
        if (!r) return put($('#x-out'), html`<span class="bad">✘ ${j.error || 'it failed: see the log'}</span>`);
        put($('#x-out'), html`<a class="btn pri" href="/export/file/${encodeURIComponent(r.name)}" download>download ${r.name}</a>
          <span class="dim">${plural(r.notes, 'card')}, ${n(Math.round(r.bytes / 1e6))} MB${r.audio_not_made ? html`, without ${plural(r.audio_not_made, 'audio clip')} not made yet (the next sync makes them)` : ''}</span>`);
      });
    },
    plan: () => { put($('#plan'), loading('working out the changes')); startJob('/sync/plan', {}, showPlan); },
    sync: async () => {
      const p = S.plan;
      const ok = await ask({ title: 'sync to Anki?', body: html`<div class="kv"><span class="k">add</span><span class="v">${n(p.add_count)}</span><span class="k">update</span><span class="v">${n(p.update_count)}</span>
        <span class="k">audio</span><span class="v">${p.audio_clips ? `${plural(p.audio_clips, 'clip')}, ${n(p.audio_total)} characters` : 'none'}</span></div>`,
        options: [{ label: p.audio_clips ? 'Yes, sync and make the audio' : 'Yes, sync', value: () => true }, { label: 'No' }] });
      if (!ok) return;
      startJob('/sync', { confirm: true }, j => { const r = j.result; if (r) put($('#plan'), html`<hr><p class="ok">✔ synced: ${n(r.added)} added, ${n(r.updated)} updated, ${n(r.unchanged)} unchanged, ${n(r.media)} media files</p>`); S.plan = null; });
    },
  });
  if (S.plan && !hosted) showPlan({ result: S.plan });
};

// ---- usage --------------------------------------------------------------------------------------------------------
VIEWS.usage = async el => {
  const d = await api('/usage');
  const max = Math.max(0.0001, ...d.days.map(x => x.usd));
  const tasks = Object.entries(d.all.by_task || {}).sort((a, b) => b[1] - a[1]);
  const models = Object.entries(d.all.by_model || {}).sort((a, b) => b[1] - a[1]);
  const tmax = Math.max(0.0001, ...tasks.map(x => x[1]));
  put(el, html`<div class="page-h"><h1>usage</h1><span class="sub">what the language model has cost</span><span class="grow"></span><button data-a="collect">collect finished batches</button></div>
    <div class="cols">
      <section class="box"><div class="t">this month</div><p class="figure">${usd(d.month.usd)}</p><p class="dim">${usd(d.all.usd)} in all</p><p class="dim">budget per run: ${usd(d.budget)}</p></section>
      <section class="box"><div class="t">by model</div>${models.length ? html`<div class="chart">${models.map(([k, v]) => html`<span class="l">${k}</span><span></span><span class="r">${usd(v)}</span>`)}</div>` : html`<p class="empty">Nothing yet.</p>`}</section>
    </div>
    <section class="box"><div class="t">by day <span class="dim">last ${d.days.length}</span></div>${d.days.length ? html`<div class="chart">${d.days.map(x => html`<span class="l">${x.day.slice(5)}</span>${bar(x.usd / max, 40)}<span class="r">${usd(x.usd)}</span>`)}</div>` : html`<p class="empty">No spend yet.</p>`}</section>
    <section class="box"><div class="t">by task</div>${tasks.length ? html`<div class="chart">${tasks.map(([k, v]) => html`<span class="l">${k}</span>${bar(v / tmax, 40)}<span class="r">${usd(v)}</span>`)}</div>` : html`<p class="empty">Nothing yet.</p>`}</section>
    <section class="box"><div class="t">recent calls</div>${d.recent.length ? html`<table class="t"><thead><tr><th>when</th><th>task</th><th>model</th><th class="r">cost</th></tr></thead><tbody>${d.recent.map(x => html`<tr><td class="nw dim">${when(x.at)}</td><td>${x.task}${x.batch ? html` <span class="flag">batch</span>` : ''}</td><td class="dim">${x.model}</td><td class="r num">${usd(x.cost)}</td></tr>`)}</tbody></table>` : html`<p class="empty">None.</p>`}</section>`);
  actions(el, { collect: () => startJob('/llm/collect', {}, () => VIEWS.usage(el)) });
};

// ---- jobs ---------------------------------------------------------------------------------------------------------
VIEWS.jobs = async (el, r) => {
  if (r.args[0]) return jobView(el, r.args[0]);
  const paint = async () => {
    const { jobs } = await api('/jobs');
    put(el, html`<div class="page-h"><h1>jobs</h1><span class="sub">steps run one at a time, in this session of the hub</span></div>
      <section class="box"><div class="t">recent</div>${jobs.length ? html`<table class="t"><thead><tr><th>job</th><th>state</th><th>started</th><th class="r">took</th><th></th></tr></thead><tbody>${jobs.map(j => html`<tr class="row" data-href="#/jobs/${j.id}">
        <td>${j.paid ? html`<span class="paid-mark">$</span>` : ''}${j.title}<div class="faint">${j.log[j.log.length - 1] || ''}</div></td><td><span class="state ${j.status}">${j.status === 'running' ? html`<span class="spin">✻</span> ` : ''}${j.status}</span></td>
        <td class="nw dim">${j.started ? ago(j.started) + ' ago' : ''}</td><td class="r nw dim">${dur(j.started, j.finished)}</td><td>${j.status === 'queued' ? html`<button class="ghost" data-a="cancel" data-id="${j.id}">cancel</button>` : ''}</td></tr>`)}</tbody></table>`
        : html`<p class="empty">No jobs yet. Long or paid steps (reading units, checks, pictures, sync) run here.</p>`}</section>`);
    actions(el, { cancel: async b => { await api(`/jobs/${b.dataset.id}/cancel`, { body: {} }); paint(); } });
  };
  await paint();
  const t = setInterval(() => { if (!$('#layer').childElementCount) paint().catch(() => {}); }, 2000);
  S.cleanup = () => clearInterval(t);
};

async function jobView(el, id) {
  let t;
  const paint = async () => {
    const j = await api(`/jobs/${id}?tail=2000`);
    const pre = $('.log', el);
    const atEnd = !pre || pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
    put(el, html`<div class="page-h"><a href="#/jobs" class="dim">jobs /</a><h1>${j.title}</h1><span class="state ${j.status}">${j.status === 'running' ? html`<span class="spin">✻</span> ` : ''}${j.status}</span>
        <span class="sub">${[j.paid && 'paid', j.started ? 'started ' + when(j.started) : 'waiting', j.started && dur(j.started, j.finished)].filter(Boolean).join(', ')}</span></div>
      ${j.error ? html`<p class="err">${j.error}</p>` : ''}
      <section class="box"><div class="t">log <span class="dim">${n(j.lines)} lines</span></div><pre class="log">${j.log.length ? j.log.map((l, i) => html`<span class="ln">${j.lines - j.log.length + i + 1}</span>${l}\n`) : html`<span class="faint">nothing printed yet</span>`}</pre></section>
      ${j.result && typeof j.result === 'object' ? html`<details class="box"><summary>result</summary><pre class="mt">${JSON.stringify(j.result, null, 1).slice(0, 20000)}</pre></details>` : ''}`);
    const p2 = $('.log', el);
    if (atEnd) p2.scrollTop = p2.scrollHeight;
    if (['done', 'failed', 'cancelled'].includes(j.status)) clearInterval(t);
  };
  await paint();
  t = setInterval(() => paint().catch(() => clearInterval(t)), 1000);
  S.cleanup = () => clearInterval(t);
}

// ---- setup --------------------------------------------------------------------------------------------------------
VIEWS.setup = async (el, r) => {
  const d = await api('/setup');
  if (!d.config) return setupWizard(el, d);
  if (r?.q?.again) return setupWizard(el, d);
  const [ready, K] = await Promise.all([api('/readiness'), api('/setup/keys')]);
  const hosted = !!S.meta.hosted;
  put(el, html`<div class="page-h"><h1>setup</h1><span class="sub">${hosted ? 'your Panko on the server' : tilde(d.path)}</span></div>
    <section class="box"><div class="t">your language</div><p>${S.meta.language}, ${learning(S.meta)}, glosses in ${S.meta.gloss_language}.</p>
      <p class="muted-p mt-s">${hosted ? html`To add a variety, add it to <code>varieties</code> in the config below. Your Panko holds one language.`
        : html`To add a variety, add it to <code>varieties</code> in the config and reload. A Panko folder holds one language:
      for a second one, make another folder and run <code>panko init</code> there (or set <code>PANKO_HOME</code> to it), so each keeps its own cards.`}</p>
      <div class="acts mt"><button data-a="again">start again with a different language</button></div></section>
    <section class="box"><div class="t">what's ready</div>${ready.rows.map(r => html`<div class="check-row"><span class="${r.ok ? 'ok' : 'faint'}">${r.ok ? '✔' : '○'}</span><span>${r.what}</span><span class="dim">${ticks(tilde(r.detail))}</span></div>`)}</section>
    <section class="box"><div class="t">reference data</div>
      <table class="t"><tbody>${d.references.map(x => html`<tr><td>${x.name}</td><td class="nw">${x.present ? html`<span class="ok">present</span>` : x.url ? html`<span class="warn">missing</span>` : html`<span class="faint">add it yourself</span>`}</td><td class="dim cut" style="max-width:320px">${hosted ? '' : tilde(x.path)}</td></tr>`)}</tbody></table>
      <div class="acts mt"><button data-a="refs" ${d.references.some(x => !x.present && x.url) ? '' : 'disabled'}>download the open ones that are missing</button></div></section>
    <section class="box" id="keys"><div class="t">keys <span class="dim">yours, kept in ${hosted ? 'your Panko' : html`<code>.env</code>`}; never shown again once saved</span></div>
      <table class="t keys"><tbody>${K.keys.map((k, i) => html`${k.note && k.note !== K.keys[i - 1]?.note ? html`<tr class="grp"><td colspan="3">${k.note}</td></tr>` : ''}<tr><td class="nw"><code>${k.name}</code></td>
        <td class="nw">${k.set ? html`<span class="ok">set</span>` : k.server ? html`<span class="dim" title="the server's shared key is used until you add your own">the server's</span>` : html`<span class="faint">not set</span>`}</td>
        <td><form class="key-f" data-key="${k.name}" autocomplete="off"><input type="password" name="v" placeholder="${k.set ? 'replace it' : 'paste it'}" aria-label="${k.name}" autocomplete="off" spellcheck="false">
          <button>save</button>${k.set ? html`<button type="button" data-a="clear-key" data-key="${k.name}">remove</button>` : ''}</form></td></tr>`)}</tbody></table>
      ${K.disk ? html`<p class="muted-p mt">Disk: ${n(Math.round(K.disk.used / 1e6))} MB of ${K.disk.quota_gb} GB used. One upload can be up to ${n(K.disk.upload_mb)} MB.</p>` : ''}</section>
    <section class="box"><div class="t">config</div><p class="muted-p">Your language, varieties, decks, providers and budget${hosted ? '' : html` live in <code>${tilde(d.path)}</code>`}. Edit them here (the old version is kept as <code>panko.toml.bak</code>)${hosted ? '' : ', or in your own editor and reload this page'}.</p>
      ${hosted ? '' : html`<div class="acts mt"><button data-a="open-config">open it</button><button data-a="open-folder">open the Panko folder</button></div>`}
      <details class="mt" id="cfg-box"><summary>edit it</summary><textarea id="cfg-text" class="cfg-text mt-s" spellcheck="false">${d.text}</textarea>
        <div class="acts mt-s"><button class="pri" data-a="save-config">save</button><span id="cfg-out"></span></div></details></section>
    ${(i => i ? html`<section class="box"><div class="t">how Panko reads</div>
      <div class="check-row"><span class="${d.modes.chat.active ? 'ok' : 'faint'}">${d.modes.chat.active ? '●' : '○'}</span><span>${i.chat}</span></div>
      <div class="check-row"><span class="${d.modes.api.ready ? 'acc' : 'faint'}">${d.modes.api.ready ? '●' : '○'}</span><span>${i.api}</span></div></section>` : '')(modeInfo(d.modes))}
    <section class="box"><div class="t">chat mode</div>${hosted ? html`<p class="muted-p">Let your own Claude read sources and decide with Panko's tools, on your own Claude plan with no API spend. Add Panko as a custom connector with this address (claude.ai or Claude Desktop: Settings, then Connectors), then connect and allow it.</p>
      ${d.chat_url ? html`<div class="snippet mt"><button data-a="copy">copy</button><pre id="snip">${d.chat_url}</pre></div>
      <p class="faint mt-s">Claude Code: <code>claude mcp add --transport http panko ${d.chat_url}</code>, then <code>/mcp</code> to sign in. Connected apps are on your <a href="/host/account">account</a> page.</p>` : html`<p class="faint">Your account page has the address.</p>`}`
      : html`<p class="muted-p">Let your own Claude (Desktop or Code) read sources and decide with Panko's tools, with no API spend.
      Add this to Claude's MCP config, then restart it.</p>${d.chat ? html`<div class="snippet mt"><button data-a="copy">copy</button><pre id="snip">${d.chat}</pre></div>`
        : html`<p class="warn">Needs the extra: <code>uv sync --extra mcp</code></p>`}`}</section>
    <section class="box"><div class="t">look</div><div class="acts"><button data-a="theme">switch light / dark</button><button data-a="tour">show me around</button><span class="dim kbd-hint">or press <kbd>t</kbd> to switch</span></div></section>`);
  actions(el, {
    refs: () => startJob('/refs/download', {}, () => VIEWS.setup(el)),
    'open-config': () => api('/open', { body: { what: 'config' } }).catch(e => toast(e.message, 'bad')),
    'open-folder': () => api('/open', { body: { what: 'folder' } }).catch(e => toast(e.message, 'bad')),
    'clear-key': async b => {
      if (!await confirmIt(`remove ${b.dataset.key}?`, html`<p>Panko stops using it until you add it again.</p>`, 'Remove')) return;
      try { await api('/setup/keys', { body: { name: b.dataset.key, value: '' } }); toast('removed'); VIEWS.setup(el); } catch (e) { toast(e.message, 'bad'); }
    },
    'save-config': async () => {
      try {
        await api('/setup/text', { body: { text: $('#cfg-text').value } });
        put($('#cfg-out'), html`<span class="ok">✔ saved</span>`);
        S.meta = await api('/meta'); paintNav(); paintStatus();
      } catch (e) { put($('#cfg-out'), html`<span class="bad">✘ ${e.message}</span>`); }
    },
    copy: async () => { try { await navigator.clipboard.writeText($('#snip').textContent); toast('copied'); } catch { toast('select the text and copy it', 'bad'); } },
    theme: () => toggleTheme(),
    tour: () => tour(),
    again: async () => {
      const n = Object.values(S.ov?.counts || {}).reduce((a, c) => a + (c.candidate || 0) + (c.active || 0) + (c.retired || 0), 0);
      if (await confirmIt('start again with a different language?', html`<p>Panko writes a new config and keeps the old one next to it as <code>panko.toml.bak</code>.</p>
        ${n ? html`<p class="warn">Your cards stay in this folder and keep their old language. For a second language, a new Panko folder is usually better.</p>` : ''}`, 'Start again')) go('#/setup?again=1');
    },
  });
  $$('form.key-f', el).forEach(f => f.onsubmit = async ev => {
    ev.preventDefault();
    const v = f.elements.v.value.trim();
    if (!v) return f.elements.v.focus();
    try {
      await api('/setup/keys', { body: { name: f.dataset.key, value: v } });
      f.elements.v.value = '';
      toast(html`<span class="ok">✔</span> ${f.dataset.key} saved`, 'ok');
      VIEWS.setup(el);
    } catch (e) { toast(e.message, 'bad'); }
  });
};

function setupWizard(el, d) {
  const df = d.defaults;
  put(el, html`<div class="page-h"><h1>set up Panko</h1><span class="sub">a few answers, then a config file you can change any time</span></div>
    ${d.config ? html`<section class="box warn"><div class="t">starting again</div><p class="muted-p">Writing replaces your config; the old one is kept as <code>panko.toml.bak</code>. <a href="#/setup">keep the current one</a></p></section>` : ''}
    <section class="box welcome accent"><div class="t">welcome</div><div class="hero-mark"><img src="/static/logo.svg" alt="" width="64" height="64"><pre class="logo" aria-hidden="true">${LOGO}</pre></div>
      <p class="muted-p">Panko turns what you learn from into checked Anki cards.
      Pick your language to start from its preset, or type any other language.</p></section>
    <section class="box"><div class="t">your language</div>
      <div class="acts">${d.presets.map(p => html`<button data-a="preset" data-slug="${p.slug}">${p.language}</button>`)}<button data-a="preset" data-slug="">another language</button></div>
      <form id="wiz" class="form mt" autocomplete="off">
        <label class="f"><span>language you're learning</span><input name="language" placeholder="Spanish, Japanese, Moroccan Darija…" required></label>
        <label class="f"><span>glosses in</span><input name="gloss_language" value="${df.gloss_language}"></label>
        <label class="f"><span>varieties <span class="faint">comma separated, e.g. darija, fusha</span></span><input name="varieties" placeholder="leave empty for just one"></label>
        <label class="f"><span>script <span class="faint">Unicode name: Arabic, Latin, Cyrillic…</span></span><input name="script" placeholder="empty: any script is accepted"></label>
        <label class="f"><span>transliteration <span class="faint">empty for the usual one, "none" for none</span></span><input name="translit" placeholder="a learner-friendly romanisation"></label>
        <label class="f"><span>Wiktionary language name</span><input name="wiktionary" placeholder="same as the language"></label>
        <label class="f"><span>top deck in Anki</span><input name="deck_root" value="${df.deck_root}"></label>
        <label class="f"><span>Anki profile</span>${d.profiles.length ? html`<select name="profile">${d.profiles.map(p => html`<option>${p}</option>`)}</select>` : html`<input name="profile" value="${df.profile}">`}</label>
      </form>
      <div class="acts mt"><button data-a="preview">preview the config</button><button class="pri" data-a="write">write it</button></div>
      <div id="wiz-out"></div></section>`);
  const answers = () => {
    const f = $('#wiz').elements, a = {};
    for (const k of ['language', 'gloss_language', 'script', 'translit', 'wiktionary', 'deck_root', 'profile']) a[k] = f[k].value.trim();
    if (!a.translit) delete a.translit; else if (a.translit.toLowerCase() === "none") a.translit = "";   // empty: the usual one
    a.varieties = f.varieties.value.split(',').map(x => x.trim().toLowerCase()).filter(Boolean);
    return a;
  };
  const lit = slug => $$('[data-a=preset]', el).forEach(b => b.classList.toggle('on', b.dataset.slug === slug));
  $('#wiz').elements.language.oninput = e => lit(d.presets.find(p => p.language.toLowerCase() === e.target.value.trim().toLowerCase())?.slug ?? null);
  const need = () => { const f = $('#wiz').elements.language; if (f.value.trim()) return true; f.focus(); put($('#wiz-out'), html`<p class="warn mt">Type the language you're learning first, or pick one above.</p>`); return false; };
  actions(el, {
    preset: b => {
      const p = d.presets.find(x => x.slug === b.dataset.slug);
      const f = $('#wiz').elements;
      lit(b.dataset.slug);
      if (!p) { for (const k of ['language', 'varieties', 'script', 'translit', 'wiktionary']) f[k].value = ''; f.language.focus(); return; }
      f.language.value = p.language; f.varieties.value = p.varieties.join(', '); f.script.value = p.script; f.translit.value = p.translit; f.wiktionary.value = p.wiktionary;
    },
    preview: async () => { if (!need()) return; try { const r = await api('/setup/preview', { body: { answers: answers() } }); put($('#wiz-out'), html`<div class="snippet mt"><pre>${r.text}</pre></div>`); } catch (e) { put($('#wiz-out'), errorBox(e)); } },
    write: async () => {
      if (!need()) return;
      try {
        const r = await api('/setup', { body: { answers: answers(), force: !!d.config } });
        toast(html`<span class="ok">✔</span> wrote ${tilde(r.path)}`, 'ok');
        S.meta = await api('/meta');
        paintNav(); paintStatus(); go('#/sources');
      } catch (e) { put($('#wiz-out'), errorBox(e)); }
    },
  });
}

// ---- card design --------------------------------------------------------------------------------------------------
const CARD_ABOUT = { recognition: 'the word, you give the meaning', production: 'the meaning, you give the word',
  listening: 'you hear it, you give the meaning', picture: 'the picture, you give the word', plural: 'the singular, you give the plural',
  'verb-forms': 'the verb, you give its forms', root: 'the root, you give the word', typed: 'you type the word' };
const SLOT_NAMES = ['Mnemonic', 'Culture note', 'Grammar tip', 'Extra'];

VIEWS.design = async el => {
  const [d, pics] = await Promise.all([api('/design'), api('/pictures/prefs').catch(() => null)]);
  const st = { draft: structuredClone(d.design), kind: 'word', card: 0, side: 'back', id: '', dirty: false, names: [] };
  const key = () => st.kind + '_back';
  const all = () => (st.kind === 'word' ? d.word : d.phrase).concat(st.draft.extras.map(x => x.slot));
  const label = s => st.draft.extras.find(x => x.slot === s)?.label || d.names[s] || s;
  const range = (id, lo, hi, v, unit) => html`<div class="range"><input type="range" id="${id}" min="${lo}" max="${hi}" value="${v}"><output for="${id}">${v}${unit}</output></div>`;
  const g = st.draft;
  put(el, html`<div class="page-h"><h1>card design</h1><span class="sub">how your cards look in Anki</span><span class="grow"></span>
      <span class="dim" id="dz-state"></span><button data-a="reset">back to the default</button><button class="pri" data-a="save" disabled>save</button></div>
    <div class="design"><div>
      <section class="box"><div class="t">back of the card</div>
        <div class="acts split"><div class="seg" id="dz-kind"><button data-k="word" class="on">words</button><button data-k="phrase">phrases</button></div>
          <span class="faint">drag, or use the arrows</span></div>
        <ol class="order mt" id="dz-order"></ol>
        <p class="faint mt-s">Untick a section to hide it. The answer always shows.</p></section>
      <section class="box"><div class="t">your own sections</div>
        <p class="muted-p">Add up to four, such as a mnemonic or a culture note. You write what each card says in them from the card's edit form, and empty ones don't show.</p>
        <div class="slots mt" id="dz-slots"></div>
        <div class="acts mt-s"><button class="ghost" data-a="slot-add">+ a section</button></div></section>
      <section class="box"><div class="t">fronts</div>
        <label class="chk-l"><input type="checkbox" id="dz-faudio" ${g.front_audio ? 'checked' : ''}> play the word on the front of recognition cards</label>
        <label class="chk-l"><input type="checkbox" id="dz-fpic" ${g.production_picture ? 'checked' : ''}> show the picture on the front of production cards</label>
        <h4 class="sub-h">cards new words get</h4>
        <div id="dz-cards-def">${d.card_types.map(c => html`<label class="chk-l"><input type="checkbox" value="${c}" ${g.default_cards.includes(c) ? 'checked' : ''} ${c === 'recognition' ? 'disabled' : ''}> ${c} <span class="dim">${CARD_ABOUT[c] || ''}</span></label>`)}</div>
        <p class="faint mt-s">Cards you already have keep theirs; change one from its edit form.</p></section>
      <section class="box"><div class="t">type and size</div>
        <div class="form">
          <label class="f"><span>font for English and transliteration</span><select id="dz-font">${d.fonts.map(f => html`<option ${g.font === f ? 'selected' : ''}>${f}</option>`)}</select></label>
          <label class="f"><span>alignment</span><select id="dz-align"><option value="center" ${g.align === 'center' ? 'selected' : ''}>centred</option><option value="left" ${g.align === 'left' ? 'selected' : ''}>left</option></select></label>
          <label class="f"><span>word size</span>${range('dz-ws', 24, 96, g.word_size, 'px')}</label>
          <label class="f"><span>meaning size</span>${range('dz-gs', 14, 48, g.gloss_size, 'px')}</label>
          <label class="f"><span>picture height</span>${range('dz-ph', 80, 480, g.picture_height, 'px')}</label>
        </div>
        <details class="mt"><summary>your own CSS</summary><textarea id="dz-css" class="mt-s" rows="6" spellcheck="false" placeholder=".gloss { color: #2160c4; }">${g.custom_css}</textarea>
          <p class="faint">Added after Panko's styles, so it wins.</p></details></section>
      ${pics ? picturePanel(pics) : ''}
    </div>
    <div class="stage"><section class="box"><div class="t">preview <span class="dim">nothing is saved until you press save</span></div>
      <div class="pv-bar"><div class="tabs" id="dz-cards"></div><div class="seg" id="dz-side"><button data-side="front">front</button><button data-side="back" class="on">back</button></div></div>
      <iframe class="pv tall" sandbox="allow-scripts" title="card preview"></iframe>
      <div class="hint split"><span id="dz-entry"></span><label>another card <input id="dz-id" placeholder="id, e.g. dw-00012" size="16" autocomplete="off"></label></div>
    </section>
    <p class="faint">A saved design reaches Anki on your next sync. Only templates and styles change, so Anki never asks for a full sync.</p></div></div>`);

  const f = $('iframe.pv', el);
  let t;
  const preview = () => { clearTimeout(t); t = setTimeout(async () => {
    try {
      const r = await fetch('/api/design/preview', { method: 'POST', headers: { 'X-Panko': '1', 'Content-Type': 'application/json' },
        body: JSON.stringify({ design: st.draft, id: st.id, kind: st.kind, card: st.card, side: st.side, theme: theme() }) });
      if (!r.ok) { const e = await r.json().catch(() => ({})); put($('#dz-entry'), html`<span class="bad">${e.error || r.statusText}</span>`); return; }
      const names = (r.headers.get('X-Panko-Cards') || '').split(',').filter(Boolean), id = r.headers.get('X-Panko-Entry');
      f.srcdoc = await r.text();
      put($('#dz-cards'), names.map((nm, i) => html`<button data-card="${i}" class="${i === st.card ? 'on' : ''}">${nm}</button>`));
      put($('#dz-entry'), html`showing <a href="#/cards?status=all&id=${id}">${id}</a>`);
    } catch (e) { put($('#dz-entry'), html`<span class="bad">${e.message}</span>`); }
  }, 180); };
  const flip = () => { st.side = st.side === 'front' ? 'back' : 'front'; $$('#dz-side button').forEach(x => x.classList.toggle('on', x.dataset.side === st.side)); preview(); };
  S.onTheme = preview;
  S.flip = flip;
  S.keys = e => { if (e.key === ' ') { e.preventDefault(); flip(); } };
  S.cleanup = () => { S.onTheme = null; };
  const dirty = () => { st.dirty = true; $('[data-a=save]', el).disabled = false; put($('#dz-state'), 'not saved yet'); preview(); };

  const order = $('#dz-order');
  const paintOrder = () => {
    const on = st.draft[key()];
    const rows = on.concat(all().filter(s => !on.includes(s)));
    put(order, rows.map(s => {
      const req = d.required.includes(s), own = s.startsWith('extra');
      return html`<li draggable="true" data-s="${s}" class="${on.includes(s) ? '' : 'off'}"><span class="grip" aria-hidden="true">⋮⋮</span>
        <label class="nm"><input type="checkbox" ${on.includes(s) ? 'checked' : ''} ${req ? 'disabled' : ''}> ${label(s)}${req ? html`<small>always shown</small>` : ''}${s === 'mine' ? html`<small>your MyNotes field</small>` : ''}${own ? html`<small>your own</small>` : ''}</label>
        <span class="mv"><button class="ghost" data-mv="-1" aria-label="move ${label(s)} up">↑</button><button class="ghost" data-mv="1" aria-label="move ${label(s)} down">↓</button></span></li>`;
    }));
  };
  const readOrder = () => { st.draft[key()] = $$('li', order).filter(li => $('input', li).checked).map(li => li.dataset.s); dirty(); };
  order.onchange = e => { e.target.closest('li').classList.toggle('off', !e.target.checked); readOrder(); };
  order.onclick = e => {
    const b = e.target.closest('[data-mv]');
    if (!b) return;
    const li = b.closest('li'), to = +b.dataset.mv < 0 ? li.previousElementSibling : li.nextElementSibling?.nextElementSibling;
    if (+b.dataset.mv < 0 && !to) return;
    order.insertBefore(li, to || null);
    $(`[data-mv="${b.dataset.mv}"]`, li).focus();
    readOrder();
  };
  let drag = null;
  order.ondragstart = e => { drag = e.target.closest('li'); drag?.classList.add('drag'); e.dataTransfer.effectAllowed = 'move'; };
  order.ondragover = e => {
    e.preventDefault();
    const li = e.target.closest('li');
    if (!drag || !li || li === drag) return;
    const r = li.getBoundingClientRect();
    order.insertBefore(drag, e.clientY > r.top + r.height / 2 ? li.nextElementSibling : li);
  };
  order.ondragend = () => { drag?.classList.remove('drag'); drag = null; readOrder(); };

  const paintSlots = () => {
    put($('#dz-slots'), st.draft.extras.length ? st.draft.extras.map(x => html`<div class="slot"><span class="k">${x.slot}</span>
      <input data-slot="${x.slot}" value="${x.label}" maxlength="40" aria-label="name of ${x.slot}"><button class="ghost" data-a="slot-del" data-slot="${x.slot}">remove</button></div>`)
      : html`<p class="faint">None yet.</p>`);
    $('[data-a=slot-add]', el).disabled = st.draft.extras.length >= d.slots.length;
  };
  $('#dz-slots').oninput = e => {
    const x = st.draft.extras.find(y => y.slot === e.target.dataset.slot);
    if (!x) return;
    x.label = e.target.value; paintOrder(); dirty();
  };

  $$('#dz-kind button').forEach(b => { b.onclick = () => { st.kind = b.dataset.k; st.card = 0; $$('#dz-kind button').forEach(x => x.classList.toggle('on', x === b)); paintOrder(); preview(); }; });
  $('#dz-side').onclick = e => { const b = e.target.closest('[data-side]'); if (!b) return; st.side = b.dataset.side; $$('#dz-side button').forEach(x => x.classList.toggle('on', x === b)); preview(); };
  $('#dz-cards').onclick = e => { const b = e.target.closest('[data-card]'); if (!b) return; st.card = +b.dataset.card; preview(); };
  $('#dz-id').onchange = e => { st.id = e.target.value.trim().toLowerCase(); st.card = 0; preview(); };
  $('#dz-faudio').onchange = e => { st.draft.front_audio = e.target.checked; st.side = 'front'; $$('#dz-side button').forEach(x => x.classList.toggle('on', x.dataset.side === 'front')); dirty(); };
  $('#dz-fpic').onchange = e => { st.draft.production_picture = e.target.checked; dirty(); };
  $('#dz-cards-def').onchange = () => { st.draft.default_cards = $$('#dz-cards-def input:checked').map(x => x.value); dirty(); };
  $('#dz-font').onchange = e => { st.draft.font = e.target.value; dirty(); };
  $('#dz-align').onchange = e => { st.draft.align = e.target.value; dirty(); };
  for (const [id, k] of [['#dz-ws', 'word_size'], ['#dz-gs', 'gloss_size'], ['#dz-ph', 'picture_height']]) {
    $(id).oninput = e => { st.draft[k] = +e.target.value; e.target.nextElementSibling.value = e.target.value + 'px'; dirty(); };
  }
  $('#dz-css').oninput = e => { st.draft.custom_css = e.target.value; dirty(); };

  actions(el, {
    'slot-add': () => {
      const slot = d.slots.find(s => !st.draft.extras.some(x => x.slot === s));
      if (!slot) return;
      st.draft.extras.push({ slot, label: SLOT_NAMES[d.slots.indexOf(slot)] });
      for (const k of ['word_back', 'phrase_back']) { const l = st.draft[k], i = l.indexOf('mine'); l.splice(i < 0 ? l.length : i, 0, slot); }
      paintSlots(); paintOrder(); dirty();
      $(`#dz-slots [data-slot=${slot}]`)?.select();
    },
    'slot-del': b => {
      const slot = b.dataset.slot;
      st.draft.extras = st.draft.extras.filter(x => x.slot !== slot);
      for (const k of ['word_back', 'phrase_back']) st.draft[k] = st.draft[k].filter(s => s !== slot);
      paintSlots(); paintOrder(); dirty();
    },
    save: async () => {
      try {
        const r = await api('/design', { body: { design: st.draft } });
        S.design = r.design; st.draft = structuredClone(r.design); st.dirty = false;
        $('[data-a=save]', el).disabled = true; put($('#dz-state'), '');
        paintOrder(); paintSlots();
        toast(html`<span class="ok">✔</span> card design saved<div class="dim">Anki gets it on the next sync.</div>`, 'ok');
      } catch (e) { toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); }
    },
    reset: async () => {
      if (!await confirmIt('go back to the default design?', html`<p>Your section order, sizes, fonts and own sections go. What your cards say in those sections stays, and comes back if you add the sections again.</p>`)) return;
      try { const r = await api('/design', { body: { reset: true } }); S.design = r.design; VIEWS.design(el); toast('back to the default design'); }
      catch (e) { toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); }
    },
    ...pictureActions(el, pics),
  });
  paintOrder(); paintSlots(); preview();
};

/* Where pictures come from: the [images] chain in order, drawings on or off, and the rules every picture follows. */
function picturePanel(p) {
  const rows = p.providers.filter(x => x.name !== 'generate');
  const gen = p.providers.find(x => x.name === 'generate');
  return html`<section class="box" id="pictures"><div class="t">pictures</div>
    <p class="muted-p">Panko looks for a real photo first, trying these in order. Tick the ones to use.</p>
    <ol class="order mt" id="pp-chain">${rows.map(x => html`<li data-s="${x.name}" class="${x.on ? '' : 'off'}"><span class="grip" aria-hidden="true">⋮⋮</span>
      <label class="nm"><input type="checkbox" ${x.on ? 'checked' : ''}> ${x.name}<small>${x.about}</small>${x.ready ? '' : html`<small class="warn">needs ${x.needs.length ? x.needs.join(', ') : 'setting up'}</small>`}</label>
      <span class="mv"><button class="ghost" data-pmv="-1" aria-label="move ${x.name} up">↑</button><button class="ghost" data-pmv="1" aria-label="move ${x.name} down">↓</button></span></li>`)}</ol>
    <h4 class="sub-h">drawings</h4>
    <label class="chk-l"><input type="checkbox" id="pp-draw" ${p.drawings ? 'checked' : ''} ${gen ? '' : 'disabled'}> draw a picture when no photo fits <span class="dim">paid, made by an image model${gen && !gen.ready ? ', needs ' + (gen.needs.join(', ') || 'a key') : ''}</span></label>
    <div class="form mt-s">
      <label class="f wide"><span>drawing style</span><textarea id="pp-style" rows="3">${p.style}</textarea></label>
      <label class="f"><span>drawing quality <span class="faint">higher costs more</span></span><select id="pp-quality">${['low', 'medium', 'high'].map(q => html`<option ${p.quality === q ? 'selected' : ''}>${q}</option>`)}</select></label>
      <label class="f wide"><span>rules for every picture <span class="faint">one per line</span></span><textarea id="pp-rules" rows="4">${p.rules.join('\n')}</textarea></label>
      <label class="f wide"><span>words that get no picture</span><input id="pp-skip" value="${p.skip}"></label>
    </div>
    <div class="acts mt"><button data-a="pp-save">save picture choices</button><span class="faint">For one card, open it and press edit: ask for a photo, a drawing or none, and say what it should show.</span></div>
  </section>`;
}

function pictureActions(el, p) {
  if (!p) return {};
  setTimeout(() => {
    const list = $('#pp-chain');
    if (!list) return;
    list.onchange = e => e.target.closest('li')?.classList.toggle('off', !e.target.checked);
    list.onclick = e => {
      const b = e.target.closest('[data-pmv]');
      if (!b) return;
      const li = b.closest('li'), to = +b.dataset.pmv < 0 ? li.previousElementSibling : li.nextElementSibling?.nextElementSibling;
      if (+b.dataset.pmv < 0 && !to) return;
      list.insertBefore(li, to || null);
      $(`[data-pmv="${b.dataset.pmv}"]`, li).focus();
    };
  });
  return {
    'pp-save': async () => {
      const chain = $$('#pp-chain li').filter(li => $('input', li).checked).map(li => li.dataset.s);
      if ($('#pp-draw').checked) chain.push('generate');
      try {
        await api('/pictures/prefs', { body: { chain, style: $('#pp-style').value.trim(), quality: $('#pp-quality').value,
          rules: $('#pp-rules').value.split('\n'), skip: $('#pp-skip').value } });
        toast(html`<span class="ok">✔</span> picture choices saved`, 'ok');
      } catch (e) { toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); }
    },
  };
}

// ---- voices -------------------------------------------------------------------------------------------------------
const GENDER = { male: 'man', female: 'woman', neutral: 'neutral' };
const langName = c => { try { return c ? new Intl.DisplayNames(['en'], { type: 'language' }).of(c) : ''; } catch (e) { return c; } };

VIEWS.voices = async (el, r) => {
  const first = await api('/voices' + (r.q.variety ? '?variety=' + encodeURIComponent(r.q.variety) : ''));
  const vs = first.varieties;
  const audio = new Audio();
  S.cleanup = () => audio.pause();
  const st = { variety: first.variety, chosen: first.chosen, picks: Object.fromEntries(vs.map(v => [v, []])),
    q: { source: '', gender: '', q: '', accent: '', page: 0 }, found: first.voices, more: first.more, filter: first.filter };
  const shown = v => v.name.replace(/^panko-/, '');
  const meta = v => [GENDER[v.gender] || v.gender, v.accent, v.age && v.age.replace(/_/g, ' ')].filter(Boolean).join(', ');
  const playBtn = v => v.sample ? html`<button class="play" data-a="play" data-src="${v.sample}" aria-label="play ${shown(v)}">${icon('play')}</button>` : html`<span class="play-gap"></span>`;
  put(el, html`<div class="page-h"><h1>voices</h1><span class="sub">who reads your cards aloud</span></div>
    ${!first.ready ? html`<section class="box warn"><div class="t">no ElevenLabs key</div><p class="muted-p">Voices come from ElevenLabs. <a href="#/setup">Add <code>ELEVENLABS_API_KEY</code> in setup</a>.
      Listening is free; library voices need a paid ElevenLabs plan to speak.</p></section>`
      : !first.in_chain ? html`<section class="box warn"><div class="t">not in use yet</div><p class="muted-p">ElevenLabs isn't in your <code>[audio] chain</code>, so cards are read by another provider. Add it in your config to use what you choose here.</p></section>` : ''}
    ${vs.length > 1 ? html`<div class="tabs mb-s" id="vc-var">${vs.map(v => html`<button data-v="${v}" class="${v === st.variety ? 'on' : ''}">${V(v).title}</button>`)}</div>` : ''}
    <section class="box" id="vc-now"></section>
    ${first.ready ? html`<section class="box"><div class="t" id="vc-head"></div>
      <div class="filters"><div class="line">
        <div class="seg" id="vc-src"><button data-src="" class="on">yours</button><button data-src="library">library</button></div>
        <div class="seg" id="vc-g">${[['', 'anyone'], ['male', 'men'], ['female', 'women']].map(([k, l]) => html`<button data-g="${k}" class="${k ? '' : 'on'}">${l}</button>`)}</div>
        <label class="prompt"><input id="vc-q" placeholder="search names and descriptions" autocomplete="off"></label>
        <label class="chk-l"><input type="checkbox" id="vc-any"> any accent</label>
      </div></div>
      <ul class="vlist mt" id="vc-list"></ul>
      <div class="acts mt" id="vc-more"></div></section>` : ''}`);

  const paintNow = () => {
    const v = st.variety, title = V(v).title, picks = st.picks[v], now = st.chosen[v] || [];
    put($('#vc-now'), html`<div class="t">${title} <span class="dim">is read by</span></div>
      ${now.length ? html`<ul class="vlist">${now.map((x, i) => html`<li><span class="n">${i + 1}.</span>${playBtn(x)}<b>${shown(x)}</b><span class="dim">${meta(x)}</span><span></span></li>`)}</ul>`
        : html`<p class="empty">No voices chosen yet.</p>`}
      ${first.ready ? html`<h4 class="sub-h">your new choice</h4>
        ${picks.length ? html`<ul class="vlist">${picks.map((x, i) => html`<li><span class="n">${i + 1}.</span>${playBtn(x)}<b>${shown(x)}</b><span class="dim">${meta(x)}</span><button class="ghost" data-a="unpick" data-i="${i}">remove</button></li>`)}</ul>`
          : html`<p class="faint">Pick up to four voices below. Every word is read by each, in this order.</p>`}
        <div class="acts mt-s"><button class="pri" data-a="use" ${picks.length ? '' : 'disabled'}>use these for ${title}</button>
          <span class="faint">the next sync makes new audio for ${title} cards (paid; the sync plan prices it first)</span></div>` : ''}`);
  };
  const isPicked = v => st.picks[st.variety].some(p => p.voice_id === v.voice_id);
  const paintList = () => {
    if (!first.ready) return;
    const f = st.filter, lib = st.q.source === 'library';
    put($('#vc-head'), html`voices for ${V(st.variety).title} <span class="dim">${[lib ? 'from the library' : 'in your account', langName(f.language), st.q.accent === 'any' ? 'any accent' : f.accent && f.accent + ' accent'].filter(Boolean).join(', ')}</span>`);
    const full = st.picks[st.variety].length >= 4;
    put($('#vc-list'), st.found.length ? st.found.map((v, i) => html`<li class="${isPicked(v) ? 'picked' : ''}">${playBtn(v)}
        <span class="who"><b title="${v.name}">${shown(v)}</b><span class="dim">${meta(v)}</span></span>
        <span class="about" title="${v.about}">${v.about}</span>
        <button data-a="pick" data-i="${i}" ${isPicked(v) || full ? 'disabled' : ''}>${isPicked(v) ? 'picked' : 'pick'}</button></li>`)
      : html`<li class="none">${lib ? 'No library voices match.' : html`None of your voices suit ${V(st.variety).title} yet. <button class="link" data-a="to-lib">Look in the library</button>`}</li>`);
    put($('#vc-more'), st.more ? html`<button data-a="more">more voices</button>` : '');
  };
  const load = async (append = false) => {
    if (!append) { st.q.page = 0; put($('#vc-list'), html`<li class="none">${loading('asking ElevenLabs')}</li>`); }
    history.replaceState(null, '', '#/voices?variety=' + encodeURIComponent(st.variety));
    try {
      const p = new URLSearchParams({ ...st.q, variety: st.variety, only: 'list' });
      const x = await api('/voices?' + p);
      st.found = append ? st.found.concat(x.voices) : x.voices; st.more = x.more; st.filter = x.filter;
      paintList();
    } catch (e) { put($('#vc-list'), html`<li class="none">${errorBox(e)}</li>`); }
  };
  const seg = (id, key, attr) => $$(`#${id} button`).forEach(b => { b.onclick = () => {
    st.q[key] = b.dataset[attr]; $$(`#${id} button`).forEach(x => x.classList.toggle('on', x === b)); load();
  }; });
  if (first.ready) {
    seg('vc-src', 'source', 'src'); seg('vc-g', 'gender', 'g');
    let typing;
    $('#vc-q').oninput = e => { clearTimeout(typing); typing = setTimeout(() => { st.q.q = e.target.value.trim(); load(); }, 300); };
    $('#vc-any').onchange = e => { st.q.accent = e.target.checked ? 'any' : ''; load(); };
  }
  $$('#vc-var button').forEach(b => { b.onclick = () => {
    st.variety = b.dataset.v; $$('#vc-var button').forEach(x => x.classList.toggle('on', x === b));
    paintNow(); load();
  }; });
  audio.onended = audio.onpause = () => $$('.play.on', el).forEach(b => { b.classList.remove('on'); put(b, icon('play')); });
  actions(el, {
    play: b => {
      const again = b.classList.contains('on');
      audio.pause();
      if (again) return;
      audio.src = b.dataset.src;
      audio.play().then(() => { b.classList.add('on'); put(b, icon('stop')); }).catch(e => toast(html`<span class="bad">✘</span> couldn't play it: ${e.message}`, 'bad'));
    },
    pick: b => { const v = st.found[+b.dataset.i], P = st.picks[st.variety]; if (v && !isPicked(v) && P.length < 4) { P.push(v); paintNow(); paintList(); } },
    unpick: b => { st.picks[st.variety].splice(+b.dataset.i, 1); paintNow(); paintList(); },
    'to-lib': () => $('#vc-src [data-src=library]').click(),
    more: async b => { b.disabled = true; st.q.page += 1; await load(true); },
    use: async () => {
      const v = st.variety, title = V(v).title, P = st.picks[v];
      const fromLib = P.filter(x => !x.mine).length;
      if (!await confirmIt(`use ${plural(P.length, 'voice')} for ${title}?`, html`<ol class="steps">
          ${fromLib ? html`<li><span>${plural(fromLib, 'library voice')} ${fromLib === 1 ? 'is' : 'are'} added to your ElevenLabs account. Library voices need a paid plan to speak.</span></li>` : ''}
          <li><span>On the next sync every ${title} card gets new audio in ${P.length === 1 ? 'this voice' : 'these voices'}. That costs money; the sync plan shows how much before anything is made.</span></li></ol>`,
        'Yes, use them')) return;
      try {
        const res = await api('/voices/choose', { body: { variety: v, picks: P.map(x => ({ voice_id: x.voice_id, name: shown(x), owner: x.mine ? '' : x.owner })) } });
        toast(html`<span class="ok">✔</span> ${title} is read by ${res.voices.join(', ')}<div class="dim">New audio is made on the next sync.</div>`, 'ok', 9000);
        st.picks[v] = [];
        st.chosen = (await api('/voices?only=chosen&variety=' + encodeURIComponent(v))).chosen || st.chosen;
        paintNow(); paintList();
      } catch (e) { toast(html`<span class="bad">✘</span> ${e.message}`, 'bad', 0); }
    },
  });
  paintNow(); paintList();
};

// ---- walkthrough --------------------------------------------------------------------------------------------------
const TOUR = [
  ['#/', '#nav', 'every page', 'The sidebar has every page. Press g and a letter to jump, like g then i for the inbox.'],
  ['#/', '.welcome', 'overview', 'What you are learning, what it has cost, and how many words came in over the last two weeks.'],
  ['#/', '.tiles', 'what needs doing', 'Each of these opens the cards behind it.'],
  ['#/sources', '[data-a=add]', 'sources', 'Add what you learn from here: a PDF, photos of pages, a lesson recording or an Anki deck you already have.'],
  ['#/inbox', '#c-status', 'every card', 'New words wait in the inbox. Active cards go to Anki. Duplicates point at the card that was kept, and rejected words stay out when a source has them again.'],
  ['#/inbox', '#c-table tbody tr', 'the inbox', 'Open a word to see the card it would make, where it came from and how it was checked, then activate it (a) or reject it (r).'],
  ['#/inbox', '.filters', 'finding cards', 'Search words, glosses, ids and tags, or narrow to one variety, words or phrases, one source, a flag or a tag.'],
  ['#/inbox', '#detail .box > .t .q', 'what a box means', 'Hover the ? beside a box title to see what it shows. Every box has one.',
    () => { if (!C.open) $('#c-table tbody tr')?.click(); }],
  ['#/design', '#dz-order', 'card design', 'Choose what the back of a card shows and in what order. The preview beside it changes as you go.'],
  ['#/design', '#pictures', 'pictures', 'Where pictures come from, and whether Panko may draw one when no photo fits.'],
  ['#/library', '.page-h', 'ready-made decks', 'Decks from the library, checked and with pictures. Adding one runs the usual duplicate checks, and the new cards land in your inbox.'],
  ['#/voices', '.page-h', 'voices', 'Listen to voices and choose the ones that read your cards.'],
  ['#/sync', '[data-a=plan]', 'sync', 'Check what a sync would change, for free, then send your active cards to Anki.'],
  ['#/sync', '#share', 'share as a file', 'Make an .apkg of your active cards for a friend: pictures and audio, no review history and nothing personal.'],
  ['', '#cmd-btn', 'commands', 'Press / anywhere to search your cards or run a command. That is the tour.'],
];
function tourDone() { try { localStorage.setItem('panko-tour-done', '1'); } catch (e) { /* private window */ } }
function tourSeen() { try { return localStorage.getItem('panko-tour-done') === '1'; } catch (e) { return true; } }
const tourOffer = () => tourSeen() ? '' : html`<section class="box accent" id="tour-offer"><div class="acts split"><span><b>New here?</b> <span class="dim">A walk through the hub takes about a minute.</span></span>
  <span class="acts"><button class="pri" data-a="tour">show me around</button><button class="ghost" data-a="tour-no">not now</button></span></div></section>`;

async function tour(i = 0) {
  S.tourEnd?.();
  if (i >= TOUR.length) return tourDone();
  const [to, sel, title, text, prep] = TOUR[Math.max(0, i)];   // prep: what to open first, once the page is there
  if (to && location.hash !== to && !(to === '#/' && (location.hash === '' || location.hash === '#'))) go(to);
  let el = null;
  const ready = x => x && !$('#view .loading') && x.getBoundingClientRect().height > 8;
  let prepped = !prep;
  for (let k = 0; k < 50; k++) {
    await new Promise(r => setTimeout(r, k ? 100 : 30));      // the first wait lets a page change start
    el = $(sel); if (ready(el)) break;
    if (!prepped && !$('#view .loading') && $('#c-table tbody tr')) { prepped = true; prep(); }
  }
  if (el && !ready(el)) el = null;
  el?.scrollIntoView({ block: el.getBoundingClientRect().height > innerHeight * 0.6 ? 'start' : 'center' });
  const ring = document.createElement('div'), card = document.createElement('div');
  ring.className = 'tour-ring' + (el ? '' : ' none');
  card.className = 'tour-card';
  card.setAttribute('role', 'dialog'); card.setAttribute('aria-label', 'walkthrough'); card.tabIndex = -1;
  put(card, html`<div class="n">${i + 1} of ${TOUR.length}</div><h4>${title}</h4><p>${text}</p>
    <div class="acts"><button class="ghost" data-t="end">end the tour</button><span class="grow"></span>${i ? html`<button data-t="back">back</button>` : ''}<button class="pri" data-t="next">${i === TOUR.length - 1 ? 'done' : 'next'}</button></div>`);
  document.body.append(ring, card);
  const place = () => {
    const m = 12, cw = card.offsetWidth, ch = card.offsetHeight;
    let top = innerHeight / 2 - ch / 2, left = innerWidth / 2 - cw / 2;
    if (el) {
      const r = el.getBoundingClientRect();
      const t = Math.max(4, r.top - 6), b = Math.min(innerHeight - 4, r.bottom + 6);   // only the part on screen
      Object.assign(ring.style, { top: t + 'px', left: Math.max(4, r.left - 6) + 'px', width: Math.min(innerWidth - 8, r.width + 12) + 'px', height: Math.max(0, b - t) + 'px' });
      if (b - t > innerHeight * 0.5 && r.right + m + cw < innerWidth) { left = r.right + m; top = Math.min(innerHeight - ch - m, Math.max(m, t + 40)); }
      else if (b + m + ch < innerHeight) { top = b + m; left = r.left; }
      else if (t - m - ch > 0) { top = t - m - ch; left = r.left; }
      else { top = innerHeight - ch - m; left = r.left + r.width / 2 - cw / 2; }
    }
    Object.assign(card.style, { top: Math.max(m, top) + 'px', left: Math.max(m, Math.min(innerWidth - cw - m, left)) + 'px' });
  };
  place();
  const key = e => {
    if (e.key === 'Escape') { end(); tourDone(); }
    else if (e.key === 'ArrowRight' || e.key === 'Enter') tour(i + 1);
    else if (e.key === 'ArrowLeft' && i) tour(i - 1);
    else return;
    e.preventDefault(); e.stopPropagation();
  };
  const seen = el && new ResizeObserver(place);
  seen?.observe(el);
  const end = () => { ring.remove(); card.remove(); seen?.disconnect(); removeEventListener('resize', place); removeEventListener('scroll', place, true); document.removeEventListener('keydown', key, true); S.tourEnd = null; };
  S.tourEnd = end;
  addEventListener('resize', place);
  addEventListener('scroll', place, true);
  document.addEventListener('keydown', key, true);
  card.onclick = e => {
    const b = e.target.closest('[data-t]');
    if (!b) return;
    if (b.dataset.t === 'end') { end(); tourDone(); }
    else tour(i + (b.dataset.t === 'next' ? 1 : -1));
  };
  $('[data-t=next]', card).focus({ preventScroll: true });
}

/* Messages from a card preview: how tall it is (its frame grows to fit, within reason), a click on the card (flips
   it), and keys pressed while it has focus (handled as if pressed on the page, so space still flips). */
function frameMessage(e) {
  const d = e.data || {};
  const f = $$('iframe.pv').find(x => x.contentWindow === e.source);
  if (!f) return;
  if (d.pankoHeight) f.style.height = Math.max(160, Math.min(f.classList.contains('tall') ? 760 : 560, d.pankoHeight + 2)) + 'px';
  else if (d.pankoFlip) S.flip?.(f);
  else if (d.pankoAudio) { if (d.pankoAudio !== 'play') toast(html`<span class="bad">✘</span> the audio didn't play: ${String(d.detail || d.pankoAudio).slice(0, 160)}`, 'bad'); }
  else if (typeof d.pankoKey === 'string' && d.pankoKey.length < 12) document.dispatchEvent(new KeyboardEvent('keydown', { key: d.pankoKey, bubbles: true }));
}

// ---- start --------------------------------------------------------------------------------------------------------
async function start() {
  $('#theme-btn').onclick = toggleTheme;
  $('#nav').addEventListener('click', e => { if (e.target.closest('[data-tour]')) tour(); });
  addEventListener('message', frameMessage);
  $('#cmd-btn').onclick = () => palette();
  try { S.meta = await api('/meta'); } catch (e) { if (e.status !== 401) put($('#view'), errorBox(e)); return; }
  const fonts = [...new Set((S.meta.varieties || []).map(v => v.font).filter(Boolean))];
  if (fonts.length) document.documentElement.style.setProperty('--tgtf', fonts.join(', ') + ', "Geeza Pro", "Noto Naskh Arabic"');
  paintNav(); paintStatus();
  addEventListener('hashchange', route);
  await route();
  refreshCounts();
  pollJobs();
}
start();
