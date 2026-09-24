'use strict';

/* 画面の状態はここ 1 つに集める。描画関数はこの状態だけを読み、
   状態を変えた側が必要な描画を呼ぶ (= どこかの DOM が真値になるのを避ける)。 */
const S = {
  title: '',
  decks: [],        // 一覧用の軽い情報
  active: null,     // 開いているデッキ名
  project: null,    // この画面が見ている案件 (= 束ねて見る時だけ。問い合わせのたびに名乗る)
  details: {},      // デッキ名 -> 全情報 (= 開いている 1 本と、並べ比較の相手)
  page: 1,          // 1 始まりの現在頁
  notesOpen: false,
  overlay: null,    // 'grid' | 'viewer' | 'compare' | 'help' | null
  cmpLeft: null,    // 並べ比較の左のデッキ
  cmpRight: null,   // 並べ比較の右のデッキ
  cmpLeftPage: 1,   // 並べ比較の左で見ている頁 (= 本体の現在頁とは独立)
  cmpRightPage: 1,  // 並べ比較の右で見ている頁
  numBuf: '',       // 数字キーで組み立て中の頁番号
  scrolling: false, // 自前スクロール中は位置からの頁更新を止める
};

const $ = (id) => document.getElementById(id);

/* 開いているデッキの全情報。真値は S.details だけに置き、「今どれを見ているか」は
   S.active が決める (= 同じものを 2 つの入れ物に持たない)。 */
const current = () => (S.active && S.details[S.active]) || null;

/* 自分がどの住所の下に置かれているかを、開かれている URL から決める。

   素の相対参照 (= ./api/...) だと、末尾のスラッシュ有無で解決先が変わる。
   別の住所の下に相乗りで配信されている場合 (= tailscale serve の /pptx など)、
   スラッシュ無しで開かれた瞬間に全部が親の住所へ飛び、隣のサービスに当たる。 */
const BASE = location.pathname.endsWith('/') ? location.pathname : location.pathname + '/';
/* 画面ごとに見ている案件を、server への問い合わせのたびに名乗る (= ほかの画面が案件を
   替えても、この画面は動かない。発表用に 1 案件へ絞った画面が別の会社の資料に替わらない)。 */
const at = (path) => {
  const url = BASE + path;
  const scoped = (path.startsWith('api/') && !path.startsWith('api/projects')) || path === 'events';
  if (!S.project || !scoped) return url;
  return url + (url.includes('?') ? '&' : '?') + 'p=' + encodeURIComponent(S.project);
};

/* 画面に入るまで絵を取りに行かない。

   loading="lazy" は当てにできない: Chromium は「画面から遠いか」を一番外側の
   スクロール領域を基準に判定するが、この画面は body が動かず中央だけが自前で
   スクロールする。外から見ると中身は一度も動いていないので全頁が「すぐそば」と
   見なされ、全頁を一度に取りに行く。 */
const lazily = new IntersectionObserver((entries) => {
  for (const e of entries) {
    if (!e.isIntersecting) continue;
    const img = e.target;
    if (img.dataset.src) {
      img.src = img.dataset.src;
      img.removeAttribute('data-src');
    }
    lazily.unobserve(img);
  }
}, { rootMargin: '600px' });  // 少し手前から読み始めて、スクロールに間に合わせる

function lazyImage(src, alt) {
  const img = document.createElement('img');
  img.dataset.src = src;
  img.alt = alt;
  lazily.observe(img);
  return img;
}

/* ---------- helpers ---------- */

function pageUrl(deck, hash) {
  return at('api/pages/' + encodeURIComponent(deck) + '/' + hash + '.jpg');
}
function thumbUrl(deck, hash) {
  return at('api/thumbs/' + encodeURIComponent(deck) + '/' + hash + '.jpg');
}
function fmtTime(epochSeconds) {
  if (!epochSeconds) return 'not rendered yet';
  return new Date(epochSeconds * 1000).toLocaleTimeString();
}
function visiblePages() {
  const d = current();
  return d ? d.pages.map((_, i) => i) : [];
}
function toast(message) {
  const el = $('toast');
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 1600);
}

/* ---------- deck picker ---------- */

function renderPicker() {
  const menu = $('pickerMenu');
  menu.innerHTML = '';
  if (!S.decks.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'no .pptx here yet';
    menu.appendChild(empty);
  }
  for (const d of S.decks) {
    const row = document.createElement('div');
    row.className = 'row' + (d.name === S.active ? ' active' : '');
    row.setAttribute('role', 'option');
    const dot = document.createElement('span');
    dot.className = 'dot' + (d.error ? ' err' : '');
    const name = document.createElement('span');
    name.textContent = d.name;
    const n = document.createElement('span');
    n.className = 'n';
    n.textContent = d.error ? 'render error' : d.slides + ' pages';
    row.append(dot, name, n);
    row.onclick = () => { closePicker(); selectDeck(d.name); };
    menu.appendChild(row);
  }

  const cur = S.decks.find((d) => d.name === S.active);
  $('deckName').textContent = cur ? cur.name : (S.decks.length ? '-' : '(no decks)');
  $('deckDot').className = 'dot' + (cur && cur.error ? ' err' : '');
  $('deckDot').hidden = !cur;  // デッキが無い時に「正常」の緑を出さない
  $('meta').textContent = cur && !cur.error
    ? cur.slides + ' pages · ' + (cur.last_ms / 1000).toFixed(1) + 's · '
      + fmtTime(cur.last_rendered_at)
    : '';
}

function openPicker() {
  $('pickerMenu').hidden = false;
  $('pickerBtn').setAttribute('aria-expanded', 'true');
}
function closePicker() {
  $('pickerMenu').hidden = true;
  $('pickerBtn').setAttribute('aria-expanded', 'false');
}
function togglePicker() {
  $('pickerMenu').hidden ? openPicker() : closePicker();
}

function stepDeck(delta) {
  if (S.decks.length < 2) return;
  const i = S.decks.findIndex((d) => d.name === S.active);
  const next = S.decks[(i + delta + S.decks.length) % S.decks.length];
  selectDeck(next.name);
  toast(next.name);
}

/* ---------- filmstrip + stage ---------- */

function renderStrip() {
  const strip = $('filmstrip');
  // 引き出しが閉じている間は組み立てない。開いたときに組む (= stripBtn 参照)。
  if (getComputedStyle(strip).display === 'none') {
    strip.innerHTML = '';
    strip.dataset.key = '';
    return;
  }
  const d = current();
  if (!d || !d.pages.length) { strip.innerHTML = ''; strip.dataset.key = ''; return; }

  const wanted = visiblePages();
  const key = S.active + '|' + wanted.join(',') + '|' + d.pages.join(',');
  if (strip.dataset.key !== key) {
    strip.innerHTML = '';
    for (const i of wanted) {
      const cell = document.createElement('div');
      cell.className = 'thumb';
      cell.dataset.page = String(i + 1);
      const img = lazyImage(thumbUrl(S.active, d.pages[i]), 'page ' + (i + 1));
      const num = document.createElement('span');
      num.className = 'num';
      num.textContent = String(i + 1);
      cell.append(img, num);
      cell.onclick = () => { closeStrip(); setPage(i + 1, { scroll: true }); };
      strip.appendChild(cell);
    }
    strip.dataset.key = key;
  }
  markCurrent();
}

/* 細い画面では頁一覧を引き出しとして開閉する。広い画面では常に出ているので
   このボタン自体が現れない。 */
function toggleStrip() {
  const open = document.body.classList.toggle('stripOpen');
  if (open) { renderStrip(); scrollStripIntoView(); }
}

function closeStrip() {
  if (document.body.classList.contains('stripOpen')) {
    document.body.classList.remove('stripOpen');
  }
}

function markCurrent() {
  for (const cell of $('filmstrip').children) {
    cell.classList.toggle('current', Number(cell.dataset.page) === S.page);
  }
  for (const cell of $('gridCells').children) {
    cell.classList.toggle('current', Number(cell.dataset.page) === S.page);
  }
}

function renderStage() {
  const host = $('pages');
  const box = $('errorBox');
  const d = current();

  box.classList.remove('info');
  if (d && d.error) {
    host.innerHTML = '';
    host.dataset.key = '';
    box.hidden = false;
    box.textContent = d.error;
    return;
  }
  if (!S.decks.length) {
    // エラーではない案内 (= 赤い文字だと壊れて見える)
    host.innerHTML = '';
    host.dataset.key = '';
    box.hidden = false;
    box.classList.add('info');
    box.textContent = 'No decks here yet. They show up as soon as they are built.';
    return;
  }
  box.hidden = true;
  if (!d) { host.innerHTML = ''; host.dataset.key = ''; return; }

  const wanted = visiblePages();
  const key = S.active + '|' + wanted.join(',') + '|' + d.pages.join(',');
  if (host.dataset.key === key) return;

  // 頁が同じ位置で同じ絵なら DOM ごと残す (= スクロール位置と読み込み済みの
  // 絵を保つ。全消し + 再構築だと更新のたびに一番上へ飛ぶ)。
  const existing = new Map();
  for (const fig of host.children) existing.set(fig.dataset.page, fig);

  host.innerHTML = '';
  for (const i of wanted) {
    const num = String(i + 1);
    const url = pageUrl(S.active, d.pages[i]);
    let fig = existing.get(num);
    if (fig && fig.dataset.url === url) {
      host.appendChild(fig);
      continue;
    }
    fig = document.createElement('figure');
    fig.dataset.page = num;
    fig.dataset.url = url;
    // 頁そのものは押しても何も起きない。触れば開く作りにすると、スクロール中の
    // 指の当たりで別の見え方に飛ばされる (= 一度撤去した挙動を形を変えて戻さない)。
    // 全画面は f キーと上のボタンから。
    fig.appendChild(lazyImage(url, 'page ' + num));
    host.appendChild(fig);
  }
  host.dataset.key = key;
}

/* 画面上部に引いた線をまたいでいる頁を現在頁とみなす。

   「中心が線に一番近い頁」ではない: 頁が画面より小さいと (= 細い画面で 3〜4 頁が同時に
   見える) 中心の比べ合いが隣の頁を拾い、頁を指定して飛んでも 1 つ先に着く。またぐ頁を
   採れば、頁と画面の大小に関わらず「今読んでいる頁」と一致する。

   交差監視は使わない: 「交差が変わった瞬間」にしか鳴らないので、自前スクロール中に
   1 度無視するとその変化は二度と届かず、現在頁が古いまま残る (= 先頭へ飛ばした
   直後に手でスクロールしても頁番号が動かない)。位置から毎回求めれば取りこぼさない。 */
function syncPageFromScroll() {
  const stage = $('stage');
  const box = stage.getBoundingClientRect();
  const line = box.top + stage.clientHeight * 0.1;  // 上端寄り = 「一番上に見えている頁」
  let best = null;
  for (const fig of $('pages').children) {
    const r = fig.getBoundingClientRect();
    if (r.bottom >= line) { best = fig; break; }  // 線をまたぐ / 線より下で最初の頁
  }
  if (!best) best = $('pages').lastElementChild;  // 末尾まで送り切った時
  if (!best) return;
  const n = Number(best.dataset.page);
  if (n && n !== S.page) { S.page = n; afterPageChange(false); }
}

/* ---------- page movement ---------- */

function setPage(n, opts) {
  const d = current();
  if (!d || !d.pages.length) return;
  const wanted = visiblePages().map((i) => i + 1);
  if (!wanted.length) return;
  // 絞り込み中は表示されている頁の中で一番近いところへ寄せる
  if (!wanted.includes(n)) {
    n = wanted.reduce((best, x) => (Math.abs(x - n) < Math.abs(best - n) ? x : best), wanted[0]);
  }
  S.page = Math.min(Math.max(n, 1), d.pages.length);
  afterPageChange(opts && opts.scroll);
}

function stepPage(delta) {
  const wanted = visiblePages().map((i) => i + 1);
  if (!wanted.length) return;
  const at = wanted.indexOf(S.page);
  const next = at === -1 ? wanted[0] : wanted[Math.min(Math.max(at + delta, 0), wanted.length - 1)];
  setPage(next, { scroll: true });
}

/* 現在頁を画面へ運ぶ。頁送りは滑らせ、デッキを開き直したときは即座に置く
   (= 別のデッキの頁の間を滑って見せても意味がない)。 */
function scrollStageToPage(behavior) {
  const fig = [...$('pages').children].find((f) => Number(f.dataset.page) === S.page);
  if (!fig) return;
  beginProgrammaticScroll();
  fig.scrollIntoView({ block: 'start', behavior: behavior || 'smooth' });
}

function afterPageChange(scroll) {
  $('pageInput').value = String(S.page);
  markCurrent();
  renderNotes();
  if (S.overlay === 'viewer') renderViewer();
  scrollStripIntoView();
  if (scroll) scrollStageToPage('smooth');
}

/* 自前でスクロールしている間は、交差監視からの現在頁の更新を止める。
   固定時間で解除すると、遠くの頁へ飛んだときに到着前に解除され、通り過ぎた
   途中の頁が現在頁として書き込まれてしまう (= 20 頁を指定して 16 頁に着く)。
   解除はスクロールが静まったことで判断し、1 px も動かなかった場合のために
   保険の上限だけ置く。 */
function beginProgrammaticScroll() {
  S.scrolling = true;
  clearTimeout(beginProgrammaticScroll._fallback);
  beginProgrammaticScroll._fallback = setTimeout(endProgrammaticScroll, 2500);
}

function endProgrammaticScroll() {
  clearTimeout(beginProgrammaticScroll._fallback);
  clearTimeout(endProgrammaticScroll._quiet);
  S.scrolling = false;
  syncPageFromScroll();  // 無視していた間に動いた分をここで拾い直す
}

let scrollFrame = 0;
$('stage').addEventListener('scroll', () => {
  if (S.scrolling) {
    // 自前スクロールが静まるのを待つ (= 到着したら endProgrammaticScroll が拾う)
    clearTimeout(endProgrammaticScroll._quiet);
    endProgrammaticScroll._quiet = setTimeout(endProgrammaticScroll, 160);
    return;
  }
  // 手でのスクロールは 1 フレームに 1 回だけ見る (= scroll は高頻度に飛ぶ)
  if (scrollFrame) return;
  scrollFrame = requestAnimationFrame(() => {
    scrollFrame = 0;
    syncPageFromScroll();
  });
}, { passive: true });

function scrollStripIntoView() {
  const cell = [...$('filmstrip').children].find((c) => Number(c.dataset.page) === S.page);
  if (!cell) return;
  const strip = $('filmstrip');
  const top = cell.offsetTop - strip.offsetTop;
  if (top < strip.scrollTop || top + cell.offsetHeight > strip.scrollTop + strip.clientHeight) {
    strip.scrollTo({ top: top - strip.clientHeight / 2 + cell.offsetHeight / 2, behavior: 'smooth' });
  }
}

/* ---------- notes ---------- */

function renderNotes() {
  if (!S.notesOpen) return;
  const body = $('notesBody');
  const d = current();
  const text = d && d.notes ? (d.notes[S.page - 1] || '') : '';
  if (text.trim()) {
    body.textContent = text;
  } else {
    body.innerHTML = '<span class="none">no notes on this page</span>';
  }
}

function toggleNotes(force) {
  S.notesOpen = force === undefined ? !S.notesOpen : force;
  $('notesPane').hidden = !S.notesOpen;
  $('notesBtn').classList.toggle('on', S.notesOpen);
  renderNotes();
}

/* ---------- overlays ---------- */

function closeOverlay() {
  for (const id of ['grid', 'viewer', 'compare', 'help']) $(id).hidden = true;
  S.overlay = null;
  $('gridBtn').classList.remove('on');
  $('compareBtn').classList.remove('on');
}

function openOverlay(name) {
  if (S.overlay === name) { closeOverlay(); return; }
  closeOverlay();
  S.overlay = name;
  $(name).hidden = false;
  if (name === 'grid') { renderGrid(); $('gridBtn').classList.add('on'); }
  if (name === 'viewer') renderViewer();
  if (name === 'compare') { $('compareBtn').classList.add('on'); openCompare(); }
}

function renderViewer() {
  const d = current();
  if (!d || !d.pages.length) return;
  $('viewerImg').src = pageUrl(S.active, d.pages[S.page - 1]);
  $('viewerLabel').textContent = S.active + ' · page ' + S.page + ' / ' + d.pages.length;
}

function renderGrid() {
  const host = $('gridCells');
  const d = current();
  host.innerHTML = '';
  if (!d) return;
  for (const i of visiblePages()) {
    const cell = document.createElement('div');
    cell.className = 'cell';
    cell.dataset.page = String(i + 1);
    const img = lazyImage(thumbUrl(S.active, d.pages[i]), 'page ' + (i + 1));
    const num = document.createElement('span');
    num.className = 'num';
    num.textContent = String(i + 1);
    cell.append(img, num);
    cell.onclick = () => { closeOverlay(); setPage(i + 1, { scroll: true }); };
    host.appendChild(cell);
  }
  markCurrent();
}

/* 2 つのデッキを同じ頁番号で並べる。同じ骨格から派生したデッキ (= w1 / w2 / w3) を
   突き合わせて、どこが揃っていてどこがずれたかを見るための道具。 */

async function detailOf(name) {
  if (!name) return null;
  if (S.details[name]) return S.details[name];
  try {
    const r = await fetch(at('api/decks/' + encodeURIComponent(name)));
    if (!r.ok) return null;
    S.details[name] = await r.json();
    return S.details[name];
  } catch (e) {
    return null;
  }
}

function fillComparePickers() {
  for (const [id, chosen] of [['cmpLeftPick', S.cmpLeft], ['cmpRightPick', S.cmpRight]]) {
    const sel = $(id);
    sel.innerHTML = '';
    for (const d of S.decks) {
      const opt = document.createElement('option');
      opt.value = d.name;
      opt.textContent = d.name;
      opt.selected = d.name === chosen;
      sel.appendChild(opt);
    }
  }
}

async function openCompare() {
  if (!S.decks.length) return;
  // 既定は「今見ているデッキ」と「その次のデッキ」。1 本しかなければ自分同士。
  const i = Math.max(0, S.decks.findIndex((d) => d.name === S.active));
  S.cmpLeft = S.cmpLeft || S.decks[i].name;
  S.cmpRight = S.cmpRight || S.decks[(i + 1) % S.decks.length].name;
  // 本文で止まっていた頁から左右とも始める (= 見比べたいのは今いる場所)。
  // 開いたあとは左右を別々に送れる (= 頁のずれた版どうしを対応させるため)。
  S.cmpLeftPage = S.page;
  S.cmpRightPage = S.page;
  fillComparePickers();
  await renderCompare();
}

function clampPage(n, detail) {
  const span = detail ? detail.pages.length : 0;
  if (!span) return 1;
  return Math.min(Math.max(n, 1), span);
}

async function renderCompare() {
  const [left, right] = await Promise.all([detailOf(S.cmpLeft), detailOf(S.cmpRight)]);
  S.cmpLeftPage = clampPage(S.cmpLeftPage, left);
  S.cmpRightPage = clampPage(S.cmpRightPage, right);

  paintCompareSide('left', left);
  paintCompareSide('right', right);

  const lh = left && left.pages[S.cmpLeftPage - 1];
  const rh = right && right.pages[S.cmpRightPage - 1];
  $('cmpLabel').textContent = lh && rh && lh === rh ? 'identical' : '';
}

function paintCompareSide(side, detail) {
  const isLeft = side === 'left';
  const deck = isLeft ? S.cmpLeft : S.cmpRight;
  const page = isLeft ? S.cmpLeftPage : S.cmpRightPage;
  const total = detail ? detail.pages.length : 0;

  const img = $(isLeft ? 'cmpLeftImg' : 'cmpRightImg');
  const hash = detail && detail.pages[page - 1];
  if (hash) {
    img.src = pageUrl(deck, hash);
    img.classList.remove('missing');
    img.alt = deck + ' page ' + page;
  } else {
    img.removeAttribute('src');
    img.classList.add('missing');
    img.alt = 'no page ' + page + ' in ' + deck;
  }

  $(isLeft ? 'cmpLeftName' : 'cmpRightName').textContent = deck + '  ' + page + ' / ' + total;

  // 帯は中身が変わったときだけ組み直す (= 頁を送るたびに作り直すと画像を読み直す)
  const strip = $(isLeft ? 'cmpLeftStrip' : 'cmpRightStrip');
  const key = deck + '|' + (detail ? detail.pages.join(',') : '');
  if (strip.dataset.key !== key) {
    strip.innerHTML = '';
    if (detail) {
      detail.pages.forEach((h, i) => {
        const cell = document.createElement('div');
        cell.className = 'cell';
        cell.dataset.page = String(i + 1);
        const thumb = lazyImage(thumbUrl(deck, h), deck + ' page ' + (i + 1));
        const num = document.createElement('span');
        num.className = 'num';
        num.textContent = String(i + 1);
        cell.append(thumb, num);
        cell.onclick = () => setComparePage(side, i + 1);
        strip.appendChild(cell);
      });
    }
    strip.dataset.key = key;
  }

  for (const cell of strip.children) {
    const on = Number(cell.dataset.page) === page;
    cell.classList.toggle('current', on);
    if (on) keepCellInView(strip, cell);
  }
}

function keepCellInView(strip, cell) {
  const left = cell.offsetLeft - strip.offsetLeft;
  if (left < strip.scrollLeft || left + cell.offsetWidth > strip.scrollLeft + strip.clientWidth) {
    strip.scrollTo({ left: left - strip.clientWidth / 2 + cell.offsetWidth / 2, behavior: 'smooth' });
  }
}

function setComparePage(side, n) {
  if (side === 'left') S.cmpLeftPage = n; else S.cmpRightPage = n;
  renderCompare();
}

/* 左右そろって送るのが既定。ずれを保ったまま流し見できる。
   片側だけ動かすのは対応を合わせるときなので、右を Shift 付きで動かす。 */
function stepComparePage(which, delta) {
  if (which !== 'right') S.cmpLeftPage += delta;
  S.cmpRightPage += delta;
  renderCompare();
}

/* ---------- filters ---------- */

/* ---------- loading ---------- */

async function selectDeck(name) {
  S.active = name;
  location.hash = encodeURIComponent(name);
  // 最後に開いた物を server に覚えさせる (= 開き直した時、どの端末からでもここに戻る)
  fetch(at('api/opened/' + encodeURIComponent(name))).catch(() => {});
  renderPicker();
  // 見ていた頁のまま隣のデッキへ移る (= 同じ骨格から育ったデッキを突き合わせるとき、
  // 毎回先頭へ戻されると同じところまで送り直すことになる)
  await loadDetail({ keepPage: true, scroll: true });
}

async function loadDetail(opts) {
  if (!S.active) {
    // デッキが 1 冊も無い (= 前に見ていた案件の頁数と頁の位置を残さない)
    S.page = 0;
    $('pageTotal').textContent = '/ 0';
    $('pageInput').value = '';
    renderStage(); renderStrip(); renderNotes();
    return;
  }
  let detail = null;
  try {
    const r = await fetch(at('api/decks/' + encodeURIComponent(S.active)));
    if (r.ok) detail = await r.json();
  } catch (e) { return; }
  S.details[S.active] = detail;
  $('pageTotal').textContent = '/ ' + (detail ? detail.pages.length : 0);
  if (!opts || !opts.keepPage) {
    S.page = 1;
    $('stage').scrollTop = 0;
  } else {
    // 頁の少ないデッキへ移ったら末尾に丸める (= 並べ比較と同じ寄せ方)
    S.page = clampPage(S.page, detail);
  }
  renderStage();
  renderStrip();
  renderNotes();
  if (S.overlay === 'grid') renderGrid();
  if (S.overlay === 'viewer') renderViewer();
  if (S.overlay === 'compare') renderCompare();
  $('pageInput').value = String(S.page);
  if (opts && opts.scroll) scrollStageToPage('auto');
}

/* 開いた時に出すデッキ。⚠ URL の末尾 (#w2) は見ない ― ブックマークの URL が古い回を
   指したまま、開き直すたびにその回が出ていた。最後に開いた物、無ければ一番新しく触った物。 */
async function firstDeck(names) {
  if (!names.length) return null;
  try {
    const r = await fetch(at('api/opened'));
    if (r.ok) {
      const remembered = (await r.json()).deck;
      if (remembered && names.includes(remembered)) return remembered;
    }
  } catch (e) { /* 覚えが読めなくても、一番新しい物を出す */ }
  const newest = S.decks.reduce((a, b) => ((b.modified || 0) > (a.modified || 0) ? b : a));
  return newest.name;
}

async function loadDecks() {
  try {
    const r = await fetch(at('api/decks'));
    S.decks = await r.json();
  } catch (e) { return; }

  // 覚えている全情報のうち、描き直されたデッキのぶんは捨てる。開いている 1 本だけ
  // 更新していると、並べ比較の相手が古い絵のまま残る。
  for (const d of S.decks) {
    const known = S.details[d.name];
    if (known && known.version !== d.version) delete S.details[d.name];
  }
  for (const name of Object.keys(S.details)) {
    if (!S.decks.some((d) => d.name === name)) delete S.details[name];
  }

  const names = S.decks.map((d) => d.name);
  if (S.active === null || !names.includes(S.active)) {
    S.active = await firstDeck(names);
    renderPicker();
    await loadDetail({ keepPage: false });
    return;
  }
  renderPicker();
  await loadDetail({ keepPage: true });
}

/* ---------- keyboard ---------- */

function onKey(e) {
  const typing = e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA';
  if (typing) {
    if (e.key === 'Enter') {
      const n = parseInt($('pageInput').value, 10);
      if (!Number.isNaN(n)) setPage(n, { scroll: true });
      e.target.blur();
    } else if (e.key === 'Escape') {
      e.target.blur();
    }
    return;
  }

  if (e.key >= '0' && e.key <= '9') {
    S.numBuf += e.key;
    toast('page ' + S.numBuf);
    clearTimeout(onKey._t);
    onKey._t = setTimeout(() => { S.numBuf = ''; }, 1200);
    return;
  }
  if (e.key === 'Enter' && S.numBuf) {
    setPage(parseInt(S.numBuf, 10), { scroll: true });
    S.numBuf = '';
    return;
  }

  // 並べ比較は自分の頁を持つので、本体の頁送りとは別に動かす
  if (S.overlay === 'compare' && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) {
    e.preventDefault();
    stepComparePage(e.shiftKey ? 'right' : 'both', e.key === 'ArrowRight' ? 1 : -1);
    return;
  }

  switch (e.key) {
    case ' ':
      // 覆いを閉じる。開いていなければ本来のスクロールに任せる。
      if (S.overlay) { e.preventDefault(); closeOverlay(); }
      break;
    case 'ArrowRight':
    case 'PageDown':
      e.preventDefault();
      e.ctrlKey || e.metaKey ? stepDeck(1) : stepPage(1);
      break;
    case 'ArrowLeft':
    case 'PageUp':
      e.preventDefault();
      e.ctrlKey || e.metaKey ? stepDeck(-1) : stepPage(-1);
      break;
    case 'Home': e.preventDefault(); setPage(1, { scroll: true }); break;
    case 'End':
      e.preventDefault();
      { const d = current(); if (d) setPage(d.pages.length, { scroll: true }); }
      break;
    case 'f': openOverlay('viewer'); break;
    case 'g': openOverlay('grid'); break;
    case 'c': openOverlay('compare'); break;
    case 'n': toggleNotes(); break;
    case '?': openOverlay('help'); break;
    case 'Escape': closeOverlay(); closePicker(); break;
    default: break;
  }
}

/* ---------- wiring ---------- */

$('pickerBtn').onclick = (e) => { e.stopPropagation(); togglePicker(); };
document.addEventListener('click', (e) => {
  if (!$('picker').contains(e.target)) closePicker();
});

$('stripBtn').onclick = () => toggleStrip();
for (const btn of document.querySelectorAll('.overlayClose')) {
  btn.onclick = (e) => { e.stopPropagation(); closeOverlay(); };
}
$('gridBtn').onclick = () => openOverlay('grid');
$('notesBtn').onclick = () => toggleNotes();
$('compareBtn').onclick = () => openOverlay('compare');
$('cmpLeftPick').onchange = (e) => { S.cmpLeft = e.target.value; renderCompare(); };
$('cmpRightPick').onchange = (e) => { S.cmpRight = e.target.value; renderCompare(); };
$('fullBtn').onclick = () => openOverlay('viewer');
$('helpBtn').onclick = () => openOverlay('help');
for (const id of ['grid', 'viewer', 'compare', 'help']) {
  $(id).onclick = (e) => { if (e.target === $(id)) closeOverlay(); };
}

$('refreshBtn').onclick = async () => {
  const btn = $('refreshBtn');
  btn.classList.add('spinning');
  try {
    await fetch(at('api/refresh'));
  } finally {
    setTimeout(() => btn.classList.remove('spinning'), 800);
  }
};

$('pageInput').onchange = () => {
  const n = parseInt($('pageInput').value, 10);
  if (!Number.isNaN(n)) setPage(n, { scroll: true });
};

// 幅が変わって頁一覧が現れたら組み立て直す (= 回転や窓のサイズ変更)
let resizeFrame = 0;
window.addEventListener('resize', () => {
  if (resizeFrame) return;
  resizeFrame = requestAnimationFrame(() => { resizeFrame = 0; renderStrip(); });
});

document.addEventListener('keydown', onKey);
window.addEventListener('hashchange', () => {
  const h = decodeURIComponent(location.hash.slice(1));
  if (h && h !== S.active) selectDeck(h);
});

let events = null;
function connectEvents() {
  if (events) events.close();
  events = new EventSource(at('events'));
  events.onmessage = () => loadDecks();
}

function loadMeta() {
  fetch(at('api/meta'))
    .then((r) => r.json())
    .then((m) => { S.title = m.title; document.title = m.title + ' · pptx-live-preview'; })
    .catch(() => {});
}

/* 案件を束ねて起動した時だけ、上に案件を選ぶ欄を出す (= 1 案件の起動では /api/projects が 404)。
   選び直したら、覚えているデッキの情報は全部前の案件のものなので捨てる。 */
async function loadProjects() {
  let listing;
  try {
    const r = await fetch(at('api/projects'));
    if (!r.ok) return;
    listing = await r.json();
  } catch (e) { return; }
  // 発表用のリンク (?only=<表示名>) = その案件だけ。欄を出さず、画面から切り替えられない
  const only = new URLSearchParams(location.search).get('only');
  if (only !== null) {
    S.project = listing.projects.includes(only) ? only : null;
    return;
  }
  S.project = listing.active;
  const select = $('projectSelect');
  select.innerHTML = '';
  for (const name of listing.projects) {
    const option = document.createElement('option');
    option.value = name;
    option.textContent = name;
    option.selected = name === listing.active;
    select.appendChild(option);
  }
  select.hidden = false;
  select.onchange = async () => {
    S.project = select.value;
    // 既定の案件として覚えさせる (= 名乗らずに開いた画面と、次の起動がここから始まる)
    await fetch(at('api/projects/select/' + encodeURIComponent(select.value)));
    S.active = null;
    S.details = {};
    history.replaceState(null, '', location.pathname + location.search);
    connectEvents();
    loadMeta();
    loadDecks();
  };
}

(async () => {
  await loadProjects();  // 見る案件が決まってから、デッキと通知を取りに行く
  connectEvents();
  loadMeta();
  loadDecks();
})();
