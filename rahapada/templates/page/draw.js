(() => {
  const {F, LABELS} = window.FA;
  const D = window.FA.draw,
    HID = window.FA.isHidden;
  const share = (v, base) => (base ? F.pct(v / base) : '');
  const shareS = (v, base) => {
    if (!base) return '';
    const p = Math.round((v / base) * 100);
    return (p > 0 ? '+' : p < 0 ? '−' : '') + Math.abs(p) + '%';
  };
  // popover on position:fixed, et tabeli kerimisala seda ei lõikaks; asukoht arvutatakse avamisel
  const fixPop = (host, p, anchor) => {
    const place = () => {
      const r = (anchor || host).getBoundingClientRect(),
        w = p.offsetWidth,
        h = p.offsetHeight;
      const x = Math.max(8, Math.min(r.left, window.innerWidth - w - 8));
      const y = r.bottom + 4 + h > window.innerHeight ? Math.max(8, r.top - h - 4) : r.bottom + 4;
      // mõni eellane (nt transform) võib olla fixed-elemendi alus: paranda nihe mõõtmise järgi
      p.style.left = '0px';
      p.style.top = '0px';
      const o = p.getBoundingClientRect();
      p.style.left = x - o.left + 'px';
      p.style.top = y - o.top + 'px';
    };
    host.addEventListener('mouseenter', place);
    host.addEventListener('focus', place);
  };
  const popList = (cell, items) => {
    cell.classList.add('mitu');
    const p = document.createElement('div');
    p.className = 'pop';
    for (const it of items) {
      const r = document.createElement('div');
      r.textContent = it;
      p.append(r);
    }
    cell.append(p);
    fixPop(cell, p);
  };
  const yearOn = window.FA.yearOn;
  // aastad ja perioodid tulevad andmetest (window.FA.PI: aastad, per); uue aasta jaoks ei ole vaja midagi muuta
  const PI = window.FA.PI,
    YEARS = PI.years,
    selectedYears = () => YEARS.filter((y) => yearOn(y)),
    ALL_YEARS = () => selectedYears().length === YEARS.length;
  const periodYear = (k) => PI.periods[k][0].slice(0, 4);
  // nähtavad veerud: üks aasta valitud -> selle kvartalid (q), mitu -> valitud aastate poolaastad (p)
  const visiblePeriods = () => {
    const ys = selectedYears(),
      t = ys.length === 1 ? 'q' : 'p';
    return Object.keys(PI.periods).filter((k) => k[0] === t && ys.includes(periodYear(k)));
  };
  const ROMAN = ['I', 'II', 'III', 'IV'];
  const periodLabel = (k) => {
    const a = PI.periods[k][0],
      mo = +a.slice(5, 7);
    return (k[0] === 'p' ? ROMAN[(mo - 1) / 6] + ' pa ' : ROMAN[(mo - 1) / 3] + ' kv ') + a.slice(2, 4);
  };
  // tabeli päis perioodide kaupa: esimene veerg, nähtavad perioodid, soovi korral tulba veerg
  const phead = (tb, first, bar) => {
    const tr = tb.closest('table').querySelector('thead tr');
    if (!tr) return;
    tr.replaceChildren();
    const th = (t, cls) => {
      const e = document.createElement('th');
      e.textContent = t;
      if (cls) e.className = cls;
      tr.append(e);
    };
    th(first);
    for (const p of visiblePeriods()) th(periodLabel(p), 'num');
    if (bar) th('', 'wfh');
  };
  const inY = (r) => yearOn((r.month || r.date || '').slice(0, 4));
  const groupName = (s) =>
    String(s ?? '')
      .replace(/\s*\([^)]*\)/g, '')
      .trim();
  const catName = (c) => {
    const n = groupName(String(c).replace(/^[^:()]+:\s*/, ''));
    return n.charAt(0).toUpperCase() + n.slice(1);
  };

  const failed = (el) => {
    el.replaceChildren();
    const p = document.createElement('div');
    p.className = 'fail';
    p.textContent = 'Failed to load';
    el.append(p);
  };
  const state = (el, ...ids) => {
    const ds = ids.map((id) => dash.data(id));
    el.classList.toggle(
      'dash-skeleton',
      ds.some((d) => d.status === 'loading')
    );
    if (ds.every((d) => d.status === 'ok')) return ds.map((d) => d.data);
    if (ds.some((d) => d.status === 'error')) failed(el);
    else el.replaceChildren();
    return null;
  };
  const tipFor = (box) => {
    const t = document.createElement('div');
    t.className = 'tip';
    t.hidden = true;
    box.append(t);
    return t;
  };
  const tipRows = (rows) => {
    const anySw = rows.some((r) => r[0]);
    const t = document.createElement('table');
    t.className = 'tt';
    for (const [color, label, val, cls] of rows) {
      const tr = document.createElement('tr');
      if (cls) tr.className = cls;
      const a = document.createElement('td');
      if (anySw) {
        const s = document.createElement('span');
        s.className = 'sw';
        if (color) s.style.background = color;
        else s.style.visibility = 'hidden';
        a.append(s);
      }
      a.append(label);
      const b = document.createElement('td');
      b.className = 'num';
      if (val === F.MASK) {
        const s = document.createElement('span');
        s.className = 'amtm';
        s.textContent = val;
        b.append(s);
      } else {
        b.textContent = val;
        if (/^[−-]\s*\d/.test(String(val))) b.classList.add('neg');
      }
      tr.append(a, b);
      t.append(tr);
    }
    return t;
  };
  const showTip = (box, tip, ev, title, lines) => {
    tip.replaceChildren();
    const h = document.createElement('div');
    h.className = 't';
    h.textContent = title;
    tip.append(h);
    tip.append(tipRows(lines.map(([c, l, v]) => [c, l, v, /^(Kokku|Kuumakse kokku)/.test(l) ? 'tot' : ''])));
    tip.hidden = false;
    const r = box.getBoundingClientRect();
    let x = ev.clientX - r.left + 12;
    if (x + tip.offsetWidth > r.width) x = ev.clientX - r.left - tip.offsetWidth - 12;
    tip.style.left = Math.max(0, x) + 'px';
    tip.style.top = ev.clientY - r.top + 12 + 'px';
  };
  const muteAxis = (g) => {
    g.attr('font-size', null).attr('font-family', null);
    g.selectAll('text').attr('fill', 'var(--color-fg-muted)').style('font-size', 'var(--cds-font-size-caption)');
    g.selectAll('line,path').attr('stroke', 'var(--cds-chart-axis)');
  };
  const yAxis = (svg, y, m) =>
    svg
      .append('g')
      .attr('transform', `translate(${m.l},0)`)
      .call(
        d3
          .axisLeft(y)
          .ticks(5)
          .tickFormat((v) => (HID() ? '' : d3.format(',')(v).replace(/,/g, ' ')))
          .tickSize(0)
      )
      .call(muteAxis)
      .call((g) => g.select('.domain').remove());
  const grid = (svg, y, m, W) =>
    svg
      .append('g')
      .selectAll('line')
      .data(y.ticks(5))
      .join('line')
      .attr('x1', m.l)
      .attr('x2', W - m.r)
      .attr('y1', y)
      .attr('y2', y)
      .attr('stroke', 'var(--cds-chart-grid)');
  const td = (tr, text, cls) => {
    const c = document.createElement('td');
    if (text === F.MASK) {
      const s = document.createElement('span');
      s.className = 'amtm';
      s.textContent = text;
      c.append(s);
    } else c.textContent = text;
    if (cls) c.className = cls;
    tr.append(c);
    return c;
  };
  const money = (v) => (v === null || v === undefined || Number.isNaN(+v) ? '' : F.eur(+v));
  const dt = (s) => (s ? (s.length > 7 ? s.slice(8, 10) + '.' : '') + s.slice(5, 7) + '.' + s.slice(0, 4) : '');
  // telje sildid: üks aasta valitud -> iga kvartal, mõlemad -> iga poolaasta
  const halfYears = (rows) => {
    const one = selectedYears().length === 1;
    return rows.map((d) => d.month).filter((mo) => (one ? /-(01|04|07|10)$/.test(mo) : /-(01|07)$/.test(mo)));
  };
  // kuu nihe: KUU('2026-10', -1) = '2026-09'
  const monthAdd = (m, n) => {
    const d = new Date(+m.slice(0, 4), +m.slice(5, 7) - 1 + n, 1);
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
  };
  const MONTHS = ['jaan', 'veebr', 'märts', 'apr', 'mai', 'juuni', 'juuli', 'aug', 'sept', 'okt', 'nov', 'dets'];
  // jooksev kuu graafikutel: kuu lõpu prognoos heleda punktiiriga tulbana; keskmistesse ei lähe
  const CURRENT = () => window.FA.PI.current;
  const monthLabel = (m) => MONTHS[+m.slice(5, 7) - 1] + ' ' + m.slice(2, 4);
  const fcBar = (svg, d, x, y, col, bw, off) =>
    svg
      .append('rect')
      .attr('x', x(d.month) + (off || 0))
      .attr('width', bw ?? x.bandwidth())
      .attr('y', y(Math.max(0, d.v)))
      .attr('height', Math.abs(y(d.v) - y(0)))
      .attr('rx', 1)
      .attr('fill', col)
      .attr('fill-opacity', 0.12)
      .attr('stroke', col)
      .attr('stroke-width', 1.2)
      .attr('stroke-dasharray', '3 2');

  document.querySelectorAll('.psearch').forEach((inp) => {
    let t = null;
    inp.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(() => dash.setParams({q: inp.value.trim() || null}), 250);
    });
  });
  dash.onData(() =>
    document.querySelectorAll('.psearch').forEach((inp) => {
      if (inp !== document.activeElement) inp.value = dash.params().q ?? '';
    })
  );
  // kuu valik: kuud, mis on valitud aastate kannetes, uuemad ees
  const monthOn = (r) => {
    const k = dash.params().month;
    return !k || r.date.startsWith(k);
  };
  D('month_select', (sel) => {
    const d = dash.data('transactions');
    const ms =
      d.status === 'ok'
        ? [...new Set(d.data.filter((r) => yearOn(r.date)).map((r) => r.date.slice(0, 7)))].sort().reverse()
        : [];
    sel.replaceChildren(
      phOpt('Kuu'),
      ...ms.map((m) => new Option(MONTHS_LONG[+m.slice(5, 7) - 1] + ' ' + m.slice(0, 4), m))
    );
    const cur = dash.params().month ?? '';
    sel.value = ms.includes(cur) ? cur : '';
    sel.classList.toggle('empty', !sel.value);
    sel.onchange = () => dash.setParams({month: sel.value || null});
  });
  D('group_select', (sel) => {
    const d = dash.data('transactions');
    const gs =
      d.status === 'ok'
        ? [...new Set(d.data.filter((r) => yearOn(r.date) && monthOn(r)).map((r) => r.grp))].sort(
            (a, b) =>
              (groupName(a) === LABELS.other) - (groupName(b) === LABELS.other) ||
              groupName(a).localeCompare(groupName(b), 'et')
          )
        : [];
    sel.replaceChildren(phOpt('Grupp'), ...gs.map((g) => new Option(groupName(g), g)));
    sel.value = dash.params().grp ?? '';
    sel.classList.toggle('empty', !sel.value);
    sel.onchange = () => dash.setParams({grp: sel.value || null, cat: null});
  });
  D('category_select', (sel) => {
    const d = dash.data('transactions'),
      g = dash.params().grp || '';
    const GR = {};
    if (d.status === 'ok') for (const r of d.data) GR[r.category] = r.grp;
    const isOther = (c) => catName(c) === LABELS.other;
    const cs =
      d.status === 'ok'
        ? [
            ...new Set(d.data.filter((r) => yearOn(r.date) && monthOn(r) && (!g || r.grp === g)).map((r) => r.category))
          ].sort(
            (a, b) =>
              isOther(a) - isOther(b) ||
              catName(a).localeCompare(catName(b), 'et') ||
              groupName(GR[a]).localeCompare(groupName(GR[b]), 'et')
          )
        : [];
    const cnt = {};
    for (const c of cs) cnt[catName(c)] = (cnt[catName(c)] || 0) + 1;
    sel.replaceChildren(
      phOpt('Kategooria'),
      ...cs.map((c) => new Option(catName(c) + (cnt[catName(c)] > 1 ? ' (' + groupName(GR[c]) + ')' : ''), c))
    );
    const cur = dash.params().cat ?? '';
    sel.value = cs.includes(cur) ? cur : '';
    sel.classList.toggle('empty', !sel.value);
    sel.onchange = () => dash.setParams({cat: sel.value || null});
  });
  // kohatäide: näha tühjas lahtris, aga mitte valikute nimekirjas
  const phOpt = (t) => {
    const o = new Option(t, '');
    o.disabled = true;
    o.hidden = true;
    return o;
  };
  // valiku tühjendamine: tühi = kõik
  document.querySelectorAll('.selx').forEach((b) =>
    b.addEventListener('click', () => {
      const k = b.dataset.clear;
      if (k === 'q')
        document.querySelectorAll('.psearch').forEach((i) => {
          i.value = '';
        });
      dash.setParams(k === 'grp' ? {grp: null, cat: null} : {[k]: null});
    })
  );
  dash.onData(() => {
    const p = dash.params();
    document.querySelectorAll('.selx').forEach((b) => {
      b.hidden = !p[b.dataset.clear];
    });
  });
  document.querySelectorAll('.psearch').forEach((i) =>
    i.addEventListener('input', () => {
      const b = i.parentElement.querySelector('.selx');
      if (b) b.hidden = !i.value;
    })
  );
  const SORTS = {
    name: (a, b) => a.p.localeCompare(b.p, 'et'),
    grp: (a, b) => (a.grps.length > 1 ? 'mitu' : a.grps[0]).localeCompare(b.grps.length > 1 ? 'mitu' : b.grps[0], 'et'),
    cat: (a, b) =>
      (a.cats.length > 1 ? 'mitu' : catName(a.cats[0])).localeCompare(
        b.cats.length > 1 ? 'mitu' : catName(b.cats[0]),
        'et'
      ),
    sum: (a, b) => Math.abs(a.sum) - Math.abs(b.sum),
    n: (a, b) => a.rs.length - b.rs.length,
    date: (a, b) => a.rs[0].date.localeCompare(b.rs[0].date)
  };
  document.querySelectorAll('th[data-sort]').forEach((th) =>
    th.addEventListener('click', () => {
      const k = th.dataset.sort,
        p = dash.params(),
        cur = p.psort || 'sum',
        dir = p.pdir || 'desc';
      dash.setParams({
        psort: k,
        pdir: k === cur ? (dir === 'desc' ? 'asc' : 'desc') : k === 'sum' || k === 'n' || k === 'date' ? 'desc' : 'asc'
      });
    })
  );
  dash.onData(() => {
    const p = dash.params(),
      cur = p.psort || 'sum',
      dir = p.pdir || 'desc';
    document
      .querySelectorAll('th[data-sort]')
      .forEach((th) =>
        th.setAttribute('aria-sort', th.dataset.sort === cur ? (dir === 'asc' ? 'ascending' : 'descending') : 'none')
      );
  });
  const openP = new Set(),
    openPC = new Set();
  const dd = (s) => s.slice(8, 10) + '.' + s.slice(5, 7) + '.' + s.slice(0, 4);

  D('payees_table', (tb) => {
    const d = dash.data('transactions');
    tb.replaceChildren();
    if (d.status !== 'ok') return;
    const q = String(dash.params().q || '').toLowerCase(),
      g = dash.params().grp || '',
      cf = dash.params().cat || '';
    const tx = d.data.filter((r) => yearOn(r.date) && monthOn(r) && (!g || r.grp === g) && (!cf || r.category === cf));
    const by = d3
      .groups(tx, (r) => r.payee)
      .map(([key, rs]) => ({
        key,
        p: rs[0].payee,
        rs: rs.sort((a, b) => b.date.localeCompare(a.date)),
        sum: d3.sum(rs, (r) => +r.amount),
        cats: [...new Set(rs.map((r) => r.category))],
        grps: [...new Set(rs.map((r) => r.grp))]
      }))
      .filter(
        (o) =>
          !q ||
          o.p.toLowerCase().includes(q) ||
          o.cats.some((c) => c.toLowerCase().includes(q)) ||
          o.rs.some(
            (r) =>
              String(r.desc).toLowerCase().includes(q) ||
              String(r.name || '')
                .toLowerCase()
                .includes(q)
          )
      );
    const sk = SORTS[dash.params().psort] ? dash.params().psort : 'sum',
      sd = (dash.params().pdir || 'desc') === 'asc' ? 1 : -1;
    by.sort((a, b) => sd * SORTS[sk](a, b) || Math.abs(b.sum) - Math.abs(a.sum));
    const s2 = (v) => (HID() ? F.MASK : (v > 0 ? '+' : v < 0 ? '−' : '') + F.eur2(Math.abs(v)));
    for (const o of by) {
      const sel = q && o.p.toLowerCase() === q;
      const tr = document.createElement('tr');
      tr.className = 'g' + (sel ? ' sel' : '') + (o.sum > 0 ? ' okrow' : '');
      td(tr, o.p);
      const gc = td(tr, o.grps.length > 1 ? 'mitu (' + o.grps.length + ')' : groupName(o.grps[0]));
      if (o.grps.length > 1) {
        gc.classList.add('warn');
        popList(gc, o.grps.map(groupName));
      }
      const c = td(tr, o.cats.length > 1 ? 'mitu (' + o.cats.length + ')' : catName(o.cats[0]));
      if (o.cats.length > 1) {
        c.classList.add('warn');
        popList(c, o.cats.map(catName));
      }
      td(tr, F.signed(o.sum), 'num' + (o.sum > 0 ? ' ok' : ''));
      td(tr, String(o.rs.length), 'num');
      td(tr, dd(o.rs[o.rs.length - 1].date) + (o.rs.length > 1 ? ' – ' + dd(o.rs[0].date) : ''), 'ctr');
      tb.append(tr);
      // alamread (kategooriad ja kanded) ainult valitud saajal: teiste saajate peidetud read tegid lehe telefonis aeglaseks
      if (sel) {
        const subs = d3
          .groups(o.rs, (r) => r.category)
          .map(([cat, rs]) => ({cat, grp: rs[0].grp, rs, sum: d3.sum(rs, (r) => +r.amount), k: o.key + '\u0001' + cat}))
          .sort((x, y) => Math.abs(y.sum) - Math.abs(x.sum));
        const subRows = [],
          single = subs.length === 1;
        for (const sb of subs) {
          const sr = document.createElement('tr');
          sr.className = 's' + (openPC.has(sb.k) ? ' open' : '') + (sb.sum > 0 ? ' okrow' : '');
          sr.hidden = !sel;
          td(sr, groupName(sb.grp) + ' – ' + catName(sb.cat));
          td(sr, '');
          td(sr, '');
          td(sr, F.signed(sb.sum), 'num' + (sb.sum > 0 ? ' ok' : ''));
          td(sr, String(sb.rs.length), 'num');
          td(sr, dd(sb.rs[sb.rs.length - 1].date) + (sb.rs.length > 1 ? ' – ' + dd(sb.rs[0].date) : ''), 'ctr');
          if (!single) tb.append(sr);
          const kids = sb.rs.map((r) => {
            const kr = document.createElement('tr');
            kr.className = 'c' + (+r.amount > 0 ? ' okrow' : '');
            kr.hidden = !(sel && (single || openPC.has(sb.k)));
            const pc = td(kr, '', 'pd');
            const a = document.createElement('span');
            a.className = 'pdt';
            a.textContent = dd(r.tdate || r.date) + (r.time ? ' ' + r.time : '');
            const b = document.createElement('span');
            b.className = 'pnm';
            b.textContent = r.name || r.payee;
            const c2 = document.createElement('span');
            c2.className = 'pds';
            c2.textContent = (r.desc || '') + (r.oneoff ? (r.desc ? ' · ' : '') + 'ühekordne' : '');
            pc.append(a, b, c2);
            td(kr, '');
            td(kr, '');
            td(kr, s2(+r.amount), 'num' + (+r.amount > 0 ? ' ok' : ''));
            td(kr, '');
            td(kr, '');
            tb.append(kr);
            return kr;
          });
          subRows.push({sr, kids, k: sb.k});
          sr.addEventListener('click', () => {
            if (openPC.has(sb.k)) openPC.delete(sb.k);
            else openPC.add(sb.k);
            sr.classList.toggle('open', openPC.has(sb.k));
            for (const kr of kids) kr.hidden = !openPC.has(sb.k);
          });
        }
      }
      if (!sel) tr.addEventListener('click', () => dash.setParams({q: o.p}));
    }
    if (!by.length) {
      const tr = document.createElement('tr');
      const c = td(tr, 'Midagi ei leitud.', 'muted');
      c.colSpan = 6;
      tb.append(tr);
    }
  });

  // ---- Jooksev kuu ----
  const s2b = (v) => (HID() ? F.MASK : (v > 0 ? '+' : v < 0 ? '−' : '') + F.eur2(Math.abs(v)));
  const MONTHS_LONG = [
    'jaanuar',
    'veebruar',
    'märts',
    'aprill',
    'mai',
    'juuni',
    'juuli',
    'august',
    'september',
    'oktoober',
    'november',
    'detsember'
  ];
  D('month_name', (el) => {
    const d = dash.data('month_days');
    el.textContent =
      d.status === 'ok' && d.data.length
        ? (MONTHS_LONG[+d.data[0].date.slice(5, 7) - 1] + ' ' + d.data[0].date.slice(0, 4)).replace(/^./, (c) =>
            c.toUpperCase()
          )
        : '';
  });
  // päise lause: ainult see, mida andmed toetavad (aasta varasemaga võrdlus, kui need kuud on olemas)
  D('lead', (el) => {
    const h = dash.data('header'),
      g = dash.data('lead_group');
    el.replaceChildren();
    if (h.status !== 'ok') return;
    const m = Object.fromEntries(h.data.map((r) => [r.metric, r.value]));
    const t = (x) => el.append(x),
      b = (v, color) => {
        const e = document.createElement('b');
        e.textContent = F.signed(v);
        if (color) {
          e.classList.toggle('ok', v > 0);
          e.classList.toggle('bad', v < 0);
        }
        e.classList.toggle('amtm', e.textContent === F.MASK);
        return e;
      };
    t('Viimastel kuudel (' + windowText(window.FA.PI.window) + ') on kuu tulem pärast kulusid ja investeeringuid ');
    t(b(m.net, true));
    if (m.net_diff !== null && m.net_diff !== undefined) {
      t(', aasta varasemaga võrreldes ');
      t(b(m.net_diff, true));
      t('. Kulud koos laenumaksetega on aasta varasemaga võrreldes muutunud ');
      t(b(m.out_diff));
      t(' kuus.');
    } else t('.');
    const r = g.status === 'ok' ? g.data[0] : null;
    if (r) {
      t(' Suurim kulu on ' + groupName(r.value).toLowerCase());
      if (r.share !== null) {
        t(', ');
        const e = document.createElement('b');
        e.textContent = F.pct(r.share);
        t(e);
        t(' tulust');
      }
      t('.');
    }
  });
  D('signed_color', (el) => {
    const d = dash.data(el.dataset.source);
    const w = el.dataset.where.split('=');
    const row = d.status === 'ok' ? d.data.find((r) => String(r[w[0]]) === w[1]) : null;
    const v = row ? +row[el.dataset.field] : null;
    el.textContent = v === null ? '' : F.signed(v);
    el.classList.toggle('ok', v !== null && v > 0);
    el.classList.toggle('bad', v !== null && v < 0);
    el.classList.toggle('amtm', el.textContent === F.MASK);
  });
  D('neg', (el) => {
    const d = dash.data(el.dataset.source);
    const w = el.dataset.where.split('=');
    const row = d.status === 'ok' ? d.data.find((r) => String(r[w[0]]) === w[1]) : null;
    el.textContent = row ? F.signed(-row[el.dataset.field]) : '';
    el.classList.toggle('amtm', el.textContent === F.MASK);
  });
  D('month_chart', (el) => {
    const got = state(el, 'month_days');
    if (!got) return;
    const rows = got[0].map((r) => ({
      ...r,
      a: r.actual === null || r.actual === '' || r.actual === undefined ? null : +r.actual,
      f: r.forecast === null || r.forecast === '' || r.forecast === undefined ? null : +r.forecast,
      p: r.prev === null || r.prev === '' || r.prev === undefined ? null : +r.prev,
      lo: r.lo === null || r.lo === '' || r.lo === undefined ? null : +r.lo,
      hi: r.hi === null || r.hi === '' || r.hi === undefined ? null : +r.hi
    }));
    el.replaceChildren();
    const W = el.clientWidth || 700,
      H = 260,
      m = {t: 14, r: 64, b: 30, l: 56};
    const x = d3.scaleLinear([1, rows.length], [m.l, W - m.r]);
    const vals = rows.flatMap((r) => [r.a, r.f, r.p, r.lo, r.hi]).filter((v) => v !== null);
    const y = d3
      .scaleLinear([Math.min(0, d3.min(vals)) * 1.1, Math.max(0, d3.max(vals)) * 1.1 || 100], [H - m.b, m.t])
      .nice();
    const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
    grid(svg, y, m, W);
    yAxis(svg, y, m);
    svg
      .append('line')
      .attr('x1', m.l)
      .attr('x2', W - m.r)
      .attr('y1', y(0))
      .attr('y2', y(0))
      .attr('stroke', 'var(--cds-chart-reference)');
    const act = rows.filter((r) => r.a !== null),
      fc = rows.filter((r) => r.f !== null);
    const end = fc.length ? fc[fc.length - 1].f : act.length ? act[act.length - 1].a : 0;
    const col = end >= 0 ? 'var(--color-ok)' : 'var(--color-bad)';
    const band = rows.filter((r) => r.lo !== null && r.hi !== null);
    const bandl =
      act.length && band.length
        ? [{day: act[act.length - 1].day, lo: act[act.length - 1].a, hi: act[act.length - 1].a}, ...band]
        : band;
    if (band.length > 1)
      svg
        .append('path')
        .datum(bandl)
        .attr(
          'd',
          d3
            .area()
            .x((d) => x(d.day))
            .y0((d) => y(d.lo))
            .y1((d) => y(d.hi))
        )
        .attr('fill', col)
        .attr('fill-opacity', 0.12)
        .attr('stroke', 'none');
    svg
      .append('path')
      .datum(rows.filter((r) => r.p !== null))
      .attr(
        'd',
        d3
          .line()
          .x((d) => x(d.day))
          .y((d) => y(d.p))
      )
      .attr('fill', 'none')
      .attr('stroke', 'var(--color-fg-muted)')
      .attr('stroke-opacity', 0.55)
      .attr('stroke-width', 1)
      .attr('stroke-linejoin', 'round');
    const fcl = act.length && fc.length ? [{day: act[act.length - 1].day, f: act[act.length - 1].a}, ...fc] : fc; // prognoos algab tegelikust seisust
    svg
      .append('path')
      .datum(fcl)
      .attr(
        'd',
        d3
          .line()
          .x((d) => x(d.day))
          .y((d) => y(d.f))
      )
      .attr('fill', 'none')
      .attr('stroke', col)
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '5 4');
    svg
      .append('path')
      .datum(act)
      .attr(
        'd',
        d3
          .line()
          .x((d) => x(d.day))
          .y((d) => y(d.a))
      )
      .attr('fill', 'none')
      .attr('stroke', dash.colors[0])
      .attr('stroke-width', 2.5)
      .attr('stroke-linejoin', 'round');
    if (act.length)
      svg
        .append('circle')
        .attr('cx', x(act[act.length - 1].day))
        .attr('cy', y(act[act.length - 1].a))
        .attr('r', 4)
        .attr('fill', dash.colors[0]);
    if (fc.length)
      svg
        .append('text')
        .attr('x', x(fc[fc.length - 1].day) + 6)
        .attr('y', y(end))
        .attr('dy', '0.35em')
        .attr('fill', col)
        .style('font-size', 'var(--cds-font-size-caption)')
        .style('font-weight', 'var(--cds-font-weight-medium, 600)')
        .text(F.signed(end));
    const tip = tipFor(el);
    svg
      .append('g')
      .selectAll('rect')
      .data(rows)
      .join('rect')
      .attr('x', (d) => x(d.day) - (x(2) - x(1)) / 2)
      .attr('width', x(2) - x(1))
      .attr('y', m.t)
      .attr('height', H - m.t - m.b)
      .attr('fill', 'transparent')
      .on('mousemove', (ev, d) =>
        showTip(el, tip, ev, dd(d.date), [
          ...(d.a !== null ? [[dash.colors[0], 'Tegelik seis', F.signed(d.a)]] : []),
          ...(d.f !== null && d.a === null ? [[col, 'Prognoos', F.signed(d.f)]] : []),
          ...(d.lo !== null && d.a === null && d.lo !== d.hi
            ? [[col, 'Vahemik', F.signed(d.lo) + ' … ' + F.signed(d.hi)]]
            : []),
          ...(d.p !== null ? [['var(--color-fg-muted)', 'Eelmine kuu', F.signed(d.p)]] : [])
        ])
      )
      .on('mouseleave', () => {
        tip.hidden = true;
      });
  });
  D('month_expected', (tb) => {
    const d = dash.data('month_recurring');
    tb.replaceChildren();
    if (d.status !== 'ok') return;
    const rs = d.data.filter((r) => r.status === tb.dataset.status);
    if (tb.dataset.status === 'paid') rs.sort((a, b) => String(b.date).localeCompare(String(a.date)));
    const tx = dash.data('transactions'),
      G = {};
    if (tx.status === 'ok') for (const t of tx.data) if (!G[t.category]) G[t.category] = t.grp;
    for (const r of rs) {
      const tr = document.createElement('tr');
      if (+r.amount > 0) tr.className = 'okrow';
      td(tr, dd(r.date), 'ctr');
      td(tr, r.name);
      td(tr, G[r.category] ? groupName(G[r.category]) : catName(r.category));
      td(tr, F.signed(+r.amount), 'num' + (+r.amount > 0 ? ' ok' : ''));
      tb.append(tr);
    }
    const tot = d3.sum(rs, (r) => +r.amount);
    const tr = document.createElement('tr');
    tr.style.fontWeight = 'var(--cds-font-weight-medium)';
    td(tr, 'Kokku');
    td(tr, '');
    td(tr, '');
    td(tr, F.signed(tot), 'num' + (tot > 0 ? ' ok' : ''));
    tb.append(tr);
  });
  const openJ = new Set();
  D('month_groups_table', (tb) => {
    const g = dash.data('month_groups'),
      c = dash.data('month_categories');
    tb.replaceChildren();
    if (g.status !== 'ok' || c.status !== 'ok') return;
    const inc = g.data.find((r) => r.grp === LABELS.income);
    const income = inc ? +inc.forecast : 0;
    const val = (v, k) => (HID() ? (inc && +inc[k] ? share(v, +inc[k]) : F.MASK) : F.eur(v));
    const COLS = ['actual', 'forecast', 'typical'];
    const outs = g.data.filter((r) => r.grp !== LABELS.income);
    const rest = income - d3.sum(outs, (r) => +r.forecast);
    const lo = Math.min(0, rest),
      span = income - lo || 1;
    const pct = (v) => ((v - lo) / span) * 100;
    const OKC = dash.colors[2],
      BADC = 'var(--cds-chart-status-critical)';
    // tulp a..b; dv = prognoos miinus tavaline, tulba paremas otsas: tavalisest suurem osa tulba sees, väiksem osa tulba järel; good ütleb, kas see on hea (roheline) või halb (punane)
    const bar = (tr, a, b, color, dv = 0, good = false, op = 1) => {
      const cell = td(tr, '', 'wfb');
      const t = document.createElement('div');
      t.className = 'wft';
      const lo2 = Math.min(a, b),
        hi2 = Math.max(a, b),
        d = Math.min(Math.abs(dv), dv > 0 ? hi2 - lo2 : Infinity),
        dc = good ? OKC : BADC;
      const segs =
        Math.abs(dv) < 1
          ? [[lo2, hi2, color]]
          : dv > 0
            ? [
                [lo2, hi2 - d, color],
                [hi2 - d, hi2, dc]
              ]
            : [
                [lo2, hi2, color],
                [hi2, hi2 + d, dc]
              ];
      // üks ümarate otstega tulp, värvid selle sees: nii on ka väga lühike jupp ümara otsaga
      const q0 = Math.max(0, pct(segs[0][0])),
        q1 = Math.min(100, pct(segs[segs.length - 1][1]));
      const w = document.createElement('div');
      w.className = 'wff';
      w.style.left = q0 + '%';
      w.style.width = Math.max(0.4, q1 - q0) + '%';
      w.style.overflow = 'hidden';
      w.style.display = 'flex';
      w.style.opacity = op;
      {
        const R = 'var(--cds-radius)',
          l = Math.abs(segs[0][0]) < 1e-9 ? '0' : R,
          rr = Math.abs(segs[segs.length - 1][1]) < 1e-9 ? '0' : R;
        w.style.borderRadius = `${l} ${rr} ${rr} ${l}`;
      } // nulljoone poolne ots on sirge
      for (const [x, y, c] of segs) {
        const f = document.createElement('div');
        f.style.flex = Math.max(0, Math.min(100, pct(y)) - Math.max(0, pct(x))) + ' 0 0';
        f.style.background = c;
        w.append(f);
      }
      {
        const z = document.createElement('div');
        z.className = 'wz';
        z.style.left = pct(0) + '%';
        t.append(z);
      }
      t.append(w);
      cell.append(t);
    };
    let run = income;
    for (const r of g.data) {
      const isInc = r.grp === LABELS.income;
      const tr = document.createElement('tr');
      tr.className = 'g' + (openJ.has(r.grp) ? ' open' : '') + (isInc ? ' okrow' : '');
      td(tr, groupName(r.grp));
      const isInv = r.grp === LABELS.investments;
      const dv = +r.forecast - +r.typical,
        bad = isInc || isInv ? dv < -1 : dv > 1;
      td(
        tr,
        Math.abs(dv) < 1 ? '' : HID() ? shareS(dv, +r.typical) : F.signed(dv),
        'num' + (Math.abs(dv) < 1 ? '' : bad ? ' bad' : ' ok')
      );
      for (const k of COLS) td(tr, val(+r[k], k), 'num');
      const gcol = isInc
        ? dash.colors[2]
        : r.grp.startsWith(LABELS.loans)
          ? dash.colors[1]
          : isInv
            ? dash.colors[4]
            : dash.colors[0];
      const top = isInc ? 0 : run;
      if (isInc) bar(tr, 0, income, gcol, dv, !bad);
      else {
        bar(tr, run - +r.forecast, run, gcol, dv, !bad);
        run -= +r.forecast;
      }
      tb.append(tr);
      const kids = c.data
        .filter((k) => k.grp === r.grp && COLS.some((q) => Math.abs(+k[q]) >= 0.5))
        .sort((a, b) => +b.forecast - +a.forecast);
      let kRun = top;
      const rows = kids.map((k) => {
        const kr = document.createElement('tr');
        kr.className = 'c' + (isInc ? ' okrow' : '');
        kr.hidden = !openJ.has(r.grp);
        td(kr, catName(k.category));
        const d2 = +k.forecast - +k.typical,
          good2 = isInc || isInv ? d2 > 0 : d2 < 0;
        td(kr, Math.abs(d2) < 1 ? '' : HID() ? shareS(d2, +k.typical) : F.signed(d2), 'num');
        for (const q of COLS) td(kr, Math.round(+k[q]) ? val(+k[q], q) : '', 'num');
        if (isInc) {
          bar(kr, kRun, kRun + +k.forecast, gcol, d2, good2, 0.55);
          kRun += +k.forecast;
        } else {
          bar(kr, kRun - +k.forecast, kRun, gcol, d2, good2, 0.55);
          kRun -= +k.forecast;
        }
        tb.append(kr);
        return kr;
      });
      tr.addEventListener('click', () => {
        if (openJ.has(r.grp)) openJ.delete(r.grp);
        else openJ.add(r.grp);
        tr.classList.toggle('open', openJ.has(r.grp));
        for (const kr of rows) kr.hidden = !openJ.has(r.grp);
      });
    }
    const tr = document.createElement('tr');
    tr.className = 'tot' + (rest >= 0 ? ' okrow' : ' badrow');
    td(tr, 'Üle jääb');
    td(tr, '');
    td(tr, '');
    td(tr, HID() ? shareS(rest, income) : F.signed(rest), 'num');
    td(tr, '');
    bar(tr, Math.min(0, rest), Math.max(0, rest), rest >= 0 ? dash.colors[2] : 'var(--cds-chart-status-critical)');
    tb.append(tr);
  });
  D('month_tx', (tb) => {
    const d = dash.data('transactions'),
      p = dash.data('month_days');
    tb.replaceChildren();
    if (d.status !== 'ok' || p.status !== 'ok' || !p.data.length) return;
    const mo = p.data[0].date.slice(0, 7);
    const rs = d.data
      .filter((r) => String(r.date).slice(0, 7) === mo)
      .sort(
        (a, b) => (b.tdate || b.date).localeCompare(a.tdate || a.date) || String(b.time).localeCompare(String(a.time))
      );
    for (const r of rs) {
      const tr = document.createElement('tr');
      if (+r.amount > 0) tr.className = 'okrow';
      td(tr, dd(r.tdate || r.date), 'ctr');
      td(tr, r.time || '', 'muted ctr');
      td(tr, r.payee);
      const ds = td(tr, r.desc || '', 'muted jkd');
      ds.title = r.desc || '';
      td(tr, groupName(r.grp));
      td(tr, catName(r.category));
      td(tr, s2b(+r.amount), 'num' + (+r.amount > 0 ? ' ok' : ''));
      tb.append(tr);
    }
    if (!rs.length) {
      const tr = document.createElement('tr');
      const c = td(tr, 'Kandeid veel ei ole.', 'muted');
      c.colSpan = 7;
      tb.append(tr);
    }
  });

  // libisev aken tekstina, nt 'juuli–okt 2026'
  const windowText = (w) => {
    const [a, b] = w,
      y1 = a.slice(0, 4),
      y2 = b.slice(0, 4);
    return (
      MONTHS[+a.slice(5) - 1] + (y1 !== y2 ? ' ' + y1 : '') + (a === b ? '' : '–' + MONTHS[+b.slice(5) - 1]) + ' ' + y2
    );
  };
  D('window_months', (el) => {
    el.textContent = windowText(window.FA.PI.window);
  });
  D('window_prev', (el) => {
    el.textContent = windowText(window.FA.PI.window_prev);
  });

  const wfBars = (income, rest) => {
    const lo = Math.min(0, rest),
      span = Math.max(income, 0) - lo || 1;
    const pct = (v) => Math.max(0, Math.min(100, ((v - lo) / span) * 100)); // väljaspool tulu ja tulemi vahemikku ei joonista
    return {
      bar: (tr, a, b, color, soft) => {
        const cell = td(tr, '', 'wfb');
        const t = document.createElement('div');
        t.className = 'wft';
        const f = document.createElement('div');
        f.className = 'wff';
        f.style.left = pct(Math.min(a, b)) + '%';
        f.style.width = Math.max(0.4, pct(Math.max(a, b)) - pct(Math.min(a, b))) + '%';
        f.style.background = color;
        if (soft) f.style.opacity = 0.55;
        {
          const R = 'var(--cds-radius)',
            l = Math.abs(Math.min(a, b)) < 1e-9 ? '0' : R,
            rr = Math.abs(Math.max(a, b)) < 1e-9 ? '0' : R;
          f.style.borderRadius = `${l} ${rr} ${rr} ${l}`;
        } // nulljoone poolne ots on sirge
        {
          const z = document.createElement('div');
          z.className = 'wz';
          z.style.left = pct(0) + '%';
          t.append(z);
        }
        t.append(f);
        cell.append(t);
      }
    };
  };
  const open = new Set();
  // päis on oma joonis: tbody joonis ei tohi kirjutada väljapoole oma elementi
  D('groups_head', (tr) => {
    tr.replaceChildren();
    const th = (t, cls) => {
      const e = document.createElement('th');
      e.textContent = t;
      if (cls) e.className = cls;
      tr.append(e);
    };
    th('Grupp');
    for (const p of visiblePeriods()) th(periodLabel(p), 'num');
    th('', 'wfh');
  });
  D('groups_table', (tb) => {
    const g = dash.data('groups'),
      c = dash.data('categories'),
      kk = dash.data('month_average');
    tb.replaceChildren();
    if (g.status !== 'ok' || c.status !== 'ok') return;
    const inc = kk.status === 'ok' ? kk.data.find((r) => r.metric === 'income') : null;
    // „Üle jääb“ = kuu tulem (aktsiate müük seda ei suurenda), kuu_keskmine rida net_regular
    const nr = kk.status === 'ok' ? kk.data.find((r) => r.metric === 'net_regular') : null;
    const val = (v, p) => (HID() ? (inc ? share(v, +inc[p]) : F.MASK) : F.eur(v));
    const vis = visiblePeriods();
    const active = (x) => vis.some((p) => Math.abs(+x[p]) >= 0.5);
    const P = vis[vis.length - 1];
    const gs = g.data.filter(active);
    const income = inc ? +inc[P] : 0;
    const restP = nr ? +nr[P] : income - d3.sum(gs, (r) => +r[P]);
    const B = wfBars(income, restP);
    if (inc) {
      const tr = document.createElement('tr');
      tr.className = 'okrow';
      td(tr, LABELS.income);
      for (const p of vis) td(tr, HID() ? '100%' : F.eur(+inc[p]), 'num');
      B.bar(tr, 0, income, dash.colors[2]);
      tb.append(tr);
    }
    let run = income;
    for (const r of gs) {
      const tr = document.createElement('tr');
      tr.className = 'g' + (open.has(r.grp) ? ' open' : '');
      td(tr, groupName(r.grp));
      for (const p of vis) td(tr, val(+r[p], p), 'num');
      const top = run,
        col = r.grp.startsWith(LABELS.loans)
          ? dash.colors[1]
          : r.grp === LABELS.investments
            ? dash.colors[4]
            : dash.colors[0];
      B.bar(tr, run - +r[P], run, col);
      run -= +r[P];
      tb.append(tr);
      const kids = c.data.filter((k) => k.grp === r.grp && active(k)).sort((a, b) => +b[P] - +a[P]);
      let kRun = top;
      const rows = kids.map((k) => {
        const kr = document.createElement('tr');
        kr.className = 'c';
        kr.hidden = !open.has(r.grp);
        td(kr, catName(k.category));
        for (const p of vis) td(kr, Math.round(+k[p]) ? val(+k[p], p) : '', 'num');
        B.bar(kr, kRun - +k[P], kRun, col, true);
        kRun -= +k[P];
        tb.append(kr);
        return kr;
      });
      tr.addEventListener('click', () => {
        if (open.has(r.grp)) open.delete(r.grp);
        else open.add(r.grp);
        tr.classList.toggle('open', open.has(r.grp));
        for (const kr of rows) kr.hidden = !open.has(r.grp);
      });
    }
    if (inc) {
      const tr = document.createElement('tr');
      tr.className = 'tot' + (restP >= 0 ? ' okrow' : ' badrow');
      td(tr, 'Üle jääb');
      for (const p of vis) {
        const rv = nr ? +nr[p] : +inc[p] - d3.sum(gs, (r) => +r[p]);
        td(
          tr,
          HID() ? shareS(rv, +inc[p]) : F.signed(rv),
          'num' + (Math.round(rv) < 0 ? ' bad' : Math.round(rv) > 0 ? ' ok' : '')
        );
      }
      B.bar(
        tr,
        Math.min(0, restP),
        Math.max(0, restP),
        restP >= 0 ? dash.colors[2] : 'var(--cds-chart-status-critical)'
      );
      tb.append(tr);
    }
  });

  D('group_multiples', (el) => {
    const got = state(el, 'group_months', 'months', 'month_groups');
    if (!got) return;
    const [rows, monthRows, jg] = got;
    el.replaceChildren();
    const groups = [...new Set(rows.map((r) => r.grp))];
    const allM = [...new Set(rows.map((r) => r.month))];
    const months = allM.filter((mo) => yearOn(mo));
    const lab = Object.fromEntries(rows.map((r) => [r.month, r.label]));
    const J = CURRENT(),
      FC = Object.fromEntries(jg.map((r) => [r.grp, +r.forecast]));
    if (yearOn(J) && J > allM[allM.length - 1]) {
      months.push(J);
      lab[J] = monthLabel(J);
    }
    const gmax = d3.max(
      rows.filter((r) => yearOn(r.month)),
      (r) => +r.amount
    );
    const tip = tipFor(el);
    const incBy = Object.fromEntries(monthRows.map((r) => [r.month, +r.income]));
    const items = [
      {name: LABELS.income, key: LABELS.income, inc: true, full: allM.map((mo) => ({month: mo, v: incBy[mo] || 0}))},
      ...groups.map((g) => ({
        name: groupName(g),
        key: g,
        inc: false,
        full: allM.map((mo) => {
          const r = rows.find((x) => x.month === mo && x.grp === g);
          return {month: mo, v: r ? +r.amount : 0};
        })
      }))
    ];
    for (const it of items) {
      it.full.forEach((d, i) => {
        d.avg = i >= 2 ? d3.mean(it.full.slice(i - 2, i + 1), (w) => w.v) : null;
      });
      it.fc = months.includes(J) && FC[it.key] !== undefined ? {month: J, v: FC[it.key], fc: true} : null;
    }
    const vmax = (it) =>
      Math.max(
        d3.max(
          it.full.filter((d) => yearOn(d.month)),
          (d) => Math.max(d.v, d.avg ?? 0)
        ) || 0,
        it.fc ? it.fc.v : 0
      ) || 1;
    const emax =
      d3.max(
        items.filter((it) => !it.inc),
        vmax
      ) || gmax;
    // suuremad ees: järjestus kastis näidatud summa (viimaste täiskuude kuu keskmine) järgi
    const WINR = window.FA.PI.window,
      WIN_PREV = window.FA.PI.window_prev,
      inWin = (d) => d.month >= WINR[0] && d.month <= WINR[1],
      inWinPrev = (d) => d.month >= WIN_PREV[0] && d.month <= WIN_PREV[1];
    for (const it of items) it.now = d3.mean(it.full.filter(inWin), (d) => d.v) || 0;
    items.sort((a, b) => b.now - a.now);
    for (const it of items) {
      const isInv = it.name === LABELS.investments,
        good = it.inc || isInv;
      const g = it.name,
        full = it.full,
        col = it.inc ? dash.colors[2] : isInv ? dash.colors[4] : dash.colors[0];
      const ymax = it.inc ? vmax(it) : emax;
      full.forEach((d, i) => {
        d.avg = i >= 2 ? d3.mean(full.slice(i - 2, i + 1), (w) => w.v) : null;
      });
      const rs = full.filter((d) => yearOn(d.month));
      if (!rs.some((d) => Math.abs(d.v) >= 0.5)) continue;
      const prevYear = d3.mean(full.filter(inWinPrev), (d) => d.v); // samad kuud aasta varem
      const now = d3.mean(full.filter(inWin), (d) => d.v);
      const ch = prevYear ? (now - prevYear) / Math.abs(prevYear) : 0;
      const box = document.createElement('div');
      box.className = 'mini';
      const h = document.createElement('div');
      h.className = 'mh';
      const n = document.createElement('span');
      n.className = 'mn';
      n.textContent = g;
      const v = document.createElement('span');
      v.className = 'mv';
      v.textContent = HID() ? F.MASK : F.eur(now);
      const c = document.createElement('span');
      c.className = 'mc ' + (Math.abs(ch) < 0.1 ? '' : ch > 0 !== good ? 'up' : 'down');
      c.textContent =
        prevYear === undefined
          ? ''
          : (Math.abs(ch) < 0.1 ? '≈ ' : ch > 0 ? '▲ ' : '▼ ') +
            (HID() ? F.pctsigned(ch) : F.signed(now - prevYear)) +
            ' vs aasta varem';
      h.append(n, ...(HID() ? [] : [v]), c);
      box.append(h);
      const W = 360,
        H = 130,
        m = {t: 8, r: 24, b: 22, l: 44};
      const x = d3.scaleBand(months, [m.l, W - m.r]).padding(0.2);
      const ymin = Math.min(
        0,
        d3.min(rs, (d) => Math.min(d.v, d.avg ?? 0)),
        it.fc ? it.fc.v : 0
      );
      const y = d3.scaleLinear([ymin, ymax], [H - m.b, m.t]).nice();
      const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
      const step = y.domain()[1] > 6000 ? 2000 : 1000;
      const tv = y.domain()[1] >= 1000 ? d3.range(step, y.domain()[1] + 1, step) : y.ticks(3).filter((t) => t > 0);
      svg
        .append('g')
        .selectAll('line')
        .data(tv)
        .join('line')
        .attr('x1', m.l)
        .attr('x2', W - m.r)
        .attr('y1', y)
        .attr('y2', y)
        .attr('stroke', 'var(--cds-chart-grid)');
      svg
        .append('g')
        .attr('transform', `translate(${m.l},0)`)
        .call(
          d3
            .axisLeft(y)
            .tickValues(tv)
            .tickFormat((t) => (HID() ? '' : d3.format(',')(t).replace(/,/g, ' ')))
            .tickSize(0)
        )
        .call(muteAxis)
        .call((a) => a.select('.domain').remove());
      svg
        .append('g')
        .attr('transform', `translate(0,${H - m.b})`)
        .call(
          d3
            .axisBottom(x)
            .tickSize(0)
            .tickPadding(5)
            .tickValues(halfYears(months.map((mo) => ({month: mo}))))
            .tickFormat((k) => lab[k])
        )
        .call(muteAxis);
      svg
        .append('g')
        .selectAll('rect')
        .data(rs)
        .join('rect')
        .attr('x', (d) => x(d.month))
        .attr('width', x.bandwidth())
        .attr('y', (d) => y(Math.max(0, d.v)))
        .attr('height', (d) => Math.abs(y(d.v) - y(0)))
        .attr('rx', 1)
        .attr('fill', col)
        .attr('opacity', 0.35);
      if (it.fc) fcBar(svg, it.fc, x, y, col);
      svg
        .append('path')
        .datum(rs.filter((d) => d.avg !== null))
        .attr(
          'd',
          d3
            .line()
            .x((d) => x(d.month) + x.bandwidth() / 2)
            .y((d) => y(d.avg))
        )
        .attr('fill', 'none')
        .attr('stroke', col)
        .attr('stroke-width', 2)
        .attr('stroke-linecap', 'round')
        .attr('stroke-linejoin', 'round');
      svg
        .append('g')
        .selectAll('rect')
        .data(it.fc ? [...rs, it.fc] : rs)
        .join('rect')
        .attr('x', (d) => x(d.month))
        .attr('width', x.bandwidth())
        .attr('y', m.t)
        .attr('height', H - m.t - m.b)
        .attr('fill', 'transparent')
        .on('mousemove', (ev, d) =>
          showTip(
            el,
            tip,
            ev,
            g + ' · ' + lab[d.month] + (d.fc ? ' (prognoos)' : ''),
            HID()
              ? [[null, 'Võrreldes aasta varasemaga', shareS(d.v - prevYear, prevYear)]]
              : d.fc
                ? [[col, 'Kuu lõpu prognoos', F.eur(d.v)]]
                : [[null, 'Kuu', F.eur(d.v)], ...(d.avg !== null ? [[col, '3 kuu keskmine', F.eur(d.avg)]] : [])]
          )
        )
        .on('mouseleave', () => {
          tip.hidden = true;
        });
      el.append(box);
    }
  });

  D('loanshare', (el) => {
    const d = dash.data('trend_total');
    el.replaceChildren();
    if (d.status !== 'ok') return;
    for (const p of visiblePeriods()) {
      const r = d.data.find((x) => x.metric === 'loan_share_' + p);
      if (!r) continue;
      const box = document.createElement('div'),
        l = document.createElement('div'),
        b = document.createElement('div');
      l.className = 'lbl';
      l.textContent = periodLabel(p);
      b.className = 'big';
      b.textContent = F.pct(+r.value);
      box.append(l, b);
      el.append(box);
    }
  });
  const openL = new Set();
  D('activeloans', (tb) => {
    const d = dash.data('loans'),
      loanCost = dash.data('loan_cost'),
      kk = dash.data('loan_cost_total'),
      lp = dash.data('loan_contracts');
    tb.replaceChildren();
    if (d.status !== 'ok') return;
    const act = d.data.filter((x) => window.FA.isActive(x.status));
    const COST =
      loanCost.status === 'ok' ? Object.fromEntries(loanCost.data.map((r) => [r.loan, +r.cost_month || 0])) : {};
    const CONTRACTS = lp.status === 'ok' ? d3.group(lp.data, (r) => r.loan) : new Map();
    const tm = d3.sum(act, (x) => +x.monthly),
      tbal = d3.sum(act, (x) => +x.balance || 0);
    const nn = (v) => v === null || v === undefined || v === '';
    const pc = (v, n = 1) => (+v).toLocaleString('et-EE', {minimumFractionDigits: 1, maximumFractionDigits: n}) + '%';
    // summad tekstis peidetakse koos teiste summadega
    const masked = (c, v) => {
      if (HID()) {
        for (const part of String(v).split(/([0-9][0-9 ]*(?:,[0-9]+)?\s?€)/g)) {
          if (!part) continue;
          if (/€$/.test(part)) {
            const sp = document.createElement('span');
            sp.className = 'amtm';
            sp.textContent = F.MASK;
            c.append(sp);
          } else c.append(part);
        }
      } else c.textContent = String(v);
    };
    for (const r of act) {
      const tr = document.createElement('tr');
      tr.className = 'lr' + (openL.has(r.loan) ? ' open' : '');
      tr.tabIndex = 0;
      td(tr, r.loan);
      td(tr, +r.monthly ? (HID() ? share(+r.monthly, tm) : F.eur(+r.monthly)) : '', 'num');
      const ap = r.apr ?? r.rate;
      const rc = td(tr, nn(ap) ? '' : pc(ap), 'num');
      if (!nn(r.rate)) rc.title = 'Lepingu intress ' + pc(r.rate, 3) + (r.rate_note ? ': ' + r.rate_note : '');
      td(tr, COST[r.loan] ? F.eur(COST[r.loan]) : '', 'num');
      const b = td(
        tr,
        r.balance === null ? 'puudub' : HID() ? share(+r.balance, tbal) : F.eur(+r.balance),
        'num' + (r.balance === null ? ' muted' : '')
      );
      if (r.balance_note) b.title = r.balance_note;
      td(tr, dt(r.end), 'ctr');
      const dr = document.createElement('tr');
      dr.className = 'det';
      dr.hidden = !openL.has(r.loan);
      const c = td(dr, '');
      c.colSpan = 6;
      const toggle = () => {
        if (openL.has(r.loan)) openL.delete(r.loan);
        else openL.add(r.loan);
        tr.classList.toggle('open', openL.has(r.loan));
        dr.hidden = !openL.has(r.loan);
      };
      tr.addEventListener('click', toggle);
      tr.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          toggle();
        }
      });
      tb.append(tr);
      if (r.note) {
        const p = document.createElement('p');
        p.className = 'lnote';
        masked(p, r.note);
        c.append(p);
      }
      const t = document.createElement('table'),
        b2 = document.createElement('tbody');
      const kv = (k, v) => {
        const x = document.createElement('tr');
        td(x, k).style.color = 'var(--color-fg-muted)';
        masked(td(x, ''), v);
        b2.append(x);
      };
      const contract = [...(CONTRACTS.get(r.loan) || [])].sort((x, y) => +x.n - +y.n);
      if (contract.length) for (const x of contract) kv(x.key, x.value);
      else {
        if (!nn(r.amount)) kv(r.kind === 'Krediitkaart' ? 'Limiit' : 'Laenusumma', F.eur(+r.amount));
        if (r.start) kv('Algus', dt(r.start));
        if (!nn(r.rate)) kv('Intress lepingus', pc(r.rate, 3) + (r.rate_note ? ' (' + r.rate_note + ')' : ''));
      }
      const paid = ysum(r, 'paid');
      if (paid > 0.5) kv('Makstud valitud aastatel', F.eur(paid));
      t.append(b2);
      c.append(t);
      tb.append(dr);
    }
    const g = (n) => (kk.status === 'ok' ? +((kk.data.find((x) => x.metric === n) || {}).value || 0) : 0);
    const tr = document.createElement('tr');
    tr.style.fontWeight = 'var(--cds-font-weight-medium)';
    td(tr, 'Kokku');
    td(tr, HID() ? '100%' : F.eur(tm), 'num');
    td(tr, '');
    td(tr, g('cost_month') ? F.eur(g('cost_month')) : '', 'num');
    td(tr, HID() ? '100%' : F.eur(tbal), 'num');
    td(tr, '');
    tb.append(tr);
  });

  const futKeys = (rows) => [...new Set(rows.map((r) => r.loan))];
  D('future_legend', (el) => {
    const d = dash.data('future_loans');
    el.replaceChildren();
    if (d.status !== 'ok') return;
    futKeys(d.data).forEach((name, i) => {
      const s = document.createElement('span');
      const sw = document.createElement('span');
      sw.className = 'sw';
      sw.style.background = dash.colors[i % 8];
      s.append(sw, name);
      el.append(s);
    });
    const s = document.createElement('span');
    const sw = document.createElement('span');
    sw.className = 'sw';
    sw.style.background = 'var(--color-fg)';
    sw.style.height = '2px';
    sw.style.borderRadius = '1px';
    s.append(sw, 'Laenujääk (parem telg)');
    el.append(s);
  });
  D('future_chart', (el) => {
    const got = state(el, 'future_loans', 'future_balance');
    if (!got) return;
    const [rows, bal] = got;
    el.replaceChildren();
    const keys = futKeys(rows);
    const months = [...new Set(rows.map((r) => r.month))];
    const lab = Object.fromEntries(rows.map((r) => [r.month, r.label]));
    const balOf = Object.fromEntries(bal.map((r) => [r.month, +r.balance]));
    // iga laen kahes osas: põhiosa (tume) ja intress koos tasudega (hele)
    const at = (mo, k) => rows.find((r) => r.month === mo && r.loan === k) || {};
    const wide = months.map((mo) =>
      Object.assign(
        {month: mo, _bal: balOf[mo] ?? null},
        ...keys.map((k) => ({
          [k]: +(at(mo, k).amount || 0),
          [k + ' ·p']: +(at(mo, k).principal ?? at(mo, k).amount ?? 0),
          [k + ' ·i']: +(at(mo, k).interest || 0)
        }))
      )
    );
    const series = d3.stack().keys(keys.flatMap((k) => [k + ' ·p', k + ' ·i']))(wide);
    const W = el.clientWidth || 700,
      H = 260,
      m = {t: 12, r: 60, b: 30, l: 56};
    const x = d3.scaleBand(months, [m.l, W - m.r]).padding(0.15);
    const y = d3.scaleLinear([0, d3.max(series[series.length - 1], (d) => d[1]) * 1.08], [H - m.b, m.t]).nice();
    const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
    grid(svg, y, m, W);
    yAxis(svg, y, m);
    const jan = months.filter((mo) => mo.endsWith('-01'));
    svg
      .append('g')
      .attr('transform', `translate(0,${H - m.b})`)
      .call(
        d3
          .axisBottom(x)
          .tickSize(0)
          .tickPadding(8)
          .tickValues(jan)
          .tickFormat((k) => k.slice(0, 4))
      )
      .call(muteAxis);
    series.forEach((s, i) => {
      svg
        .append('g')
        .selectAll('rect')
        .data(s)
        .join('rect')
        .attr('x', (d) => x(d.data.month))
        .attr('width', x.bandwidth())
        .attr('y', (d) => y(d[1]))
        .attr('height', (d) => Math.max(0, y(d[0]) - y(d[1])))
        .attr('fill', dash.colors[Math.floor(i / 2) % 8])
        .attr('opacity', i % 2 ? 0.4 : 1);
    });
    const y2 = d3.scaleLinear([0, d3.max(bal, (r) => +r.balance) * 1.08], [H - m.b, m.t]).nice();
    svg
      .append('g')
      .attr('transform', `translate(${W - m.r},0)`)
      .call(
        d3
          .axisRight(y2)
          .ticks(5)
          .tickFormat((v) => (HID() ? '' : v / 1000 + ' tuh'))
          .tickSize(0)
          .tickPadding(6)
      )
      .call(muteAxis)
      .call((g) => g.select('.domain').remove());
    const bl = wide.filter((d) => d._bal !== null);
    svg
      .append('path')
      .datum(bl)
      .attr(
        'd',
        d3
          .line()
          .x((d) => x(d.month) + x.bandwidth() / 2)
          .y((d) => y2(d._bal))
      )
      .attr('fill', 'none')
      .attr('stroke', 'var(--color-fg)')
      .attr('stroke-width', 2)
      .attr('stroke-linecap', 'round')
      .attr('stroke-linejoin', 'round');
    const tip = tipFor(el);
    svg
      .append('g')
      .selectAll('rect')
      .data(wide)
      .join('rect')
      .attr('x', (d) => x(d.month))
      .attr('width', x.bandwidth())
      .attr('y', m.t)
      .attr('height', H - m.t - m.b)
      .attr('fill', 'transparent')
      .on('mousemove', (ev, d) => {
        const s = d3.sum(keys, (k) => d[k]),
          si = d3.sum(keys, (k) => d[k + ' ·i']);
        showTip(el, tip, ev, lab[d.month], [
          ...keys
            .map((k, i) => [dash.colors[i % 8], k, d[k], d[k + ' ·i']])
            .filter((l) => l[2] > 0)
            .map((l) => [
              l[0],
              l[1],
              HID() ? share(l[2], s) : F.eur(l[2]) + (l[3] ? ' (intress ' + F.eur(l[3]) + ')' : '')
            ]),
          [null, 'Kuumakse kokku', HID() ? '100%' : F.eur(s)],
          ...(!HID() && si ? [[null, 'sh intress ja tasud', F.eur(si)]] : []),
          ...(d._bal !== null && !HID() ? [['var(--color-fg)', 'Laenujääk kuu lõpus', F.eur(d._bal)]] : [])
        ]);
      })
      .on('mouseleave', () => {
        tip.hidden = true;
      });
  });

  const sideTable = (side) => (tb) => {
    const d = dash.data('assets');
    tb.replaceChildren();
    if (d.status !== 'ok') return;
    let rs = d.data.filter((x) => x.side === side);
    const tot = d3.sum(rs, (x) => +x.value || 0);
    if (side === 'debt') {
      const isCard = (x) => /krediitkaart/i.test(x.item),
        ln = rs.filter((x) => !isCard(x));
      if (ln.length > 1)
        rs = [
          {
            item: LABELS.loan_section,
            value: d3.sum(ln, (x) => +x.value || 0),
            note: ln.map((x) => x.item).join(', ') + '. Laenude kaupa vahelehel Laenud.'
          },
          ...rs.filter(isCard)
        ];
    }
    for (const r of rs) {
      const tr = document.createElement('tr');
      const a = td(tr, r.item);
      a.title = r.note;
      td(
        tr,
        r.value === null ? 'puudub' : HID() ? share(+r.value, tot) : F.eur(+r.value),
        'num' + (r.value === null ? ' muted' : '')
      );
      tb.append(tr);
    }
  };
  D('assets_table', sideTable('asset'));
  D('debts_table', sideTable('debt'));

  D('investchart', (el) => {
    const got = state(el, 'investment_months', 'portfolio_change', 'month_summary');
    if (!got) return;
    const rows = got[0].filter(inY);
    const months = [...new Set([...got[0], ...got[1]].map((d) => d.month))].sort().filter((mo) => yearOn(mo));
    el.replaceChildren();
    const W = el.clientWidth || 700,
      H = 260,
      m = {t: 12, r: 8, b: 30, l: 56};
    const x = d3.scaleBand(months, [m.l, W - m.r]).padding(0.25);
    const po = (d) => +d.pension_out || 0;
    let cs = 0;
    const cumBy = Object.fromEntries(got[0].map((d) => [d.month, (cs += +d.stocks_net + +d.pension3 + po(d))]));
    const J = CURRENT(),
      ie = got[2].find((r) => r.metric === 'invest_end'),
      last = got[0][got[0].length - 1];
    const fc =
      ie && months.includes(J) && last && J > last.month
        ? {month: J, label: monthLabel(J), v: +ie.value, cum: cumBy[last.month] + +ie.value}
        : null;
    const lo = Math.min(
        d3.min(rows, (d) => Math.min(0, +d.stocks_net) + po(d)),
        fc ? Math.min(0, fc.v) : 0
      ),
      hi = Math.max(
        d3.max(rows, (d) => Math.max(cumBy[d.month], Math.max(0, +d.stocks_net) + +d.pension3)),
        fc ? Math.max(fc.cum, fc.v) : 0
      );
    const y = d3.scaleLinear([lo * 1.05, hi * 1.08], [H - m.b, m.t]).nice();
    const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
    grid(svg, y, m, W);
    yAxis(svg, y, m);
    const step = W < 520 ? 3 : W < 900 ? 2 : 1;
    svg
      .append('g')
      .attr('transform', `translate(0,${H - m.b})`)
      .call(
        d3
          .axisBottom(x)
          .tickSize(0)
          .tickPadding(8)
          .tickValues(halfYears(rows))
          .tickFormat((k) => rows.find((r) => r.month === k).label)
      )
      .call(muteAxis);
    svg
      .append('line')
      .attr('x1', m.l)
      .attr('x2', W - m.r)
      .attr('y1', y(0))
      .attr('y2', y(0))
      .attr('stroke', 'var(--cds-chart-reference)');
    const bw = x.bandwidth(),
      off = 0;
    svg
      .append('g')
      .selectAll('rect')
      .data(rows)
      .join('rect')
      .attr('x', (d) => x(d.month) + off)
      .attr('width', bw)
      .attr('y', (d) => y(Math.max(0, +d.stocks_net)))
      .attr('height', (d) => Math.abs(y(+d.stocks_net) - y(0)))
      .attr('fill', dash.colors[0]);
    svg
      .append('g')
      .selectAll('rect')
      .data(rows)
      .join('rect')
      .attr('x', (d) => x(d.month) + off)
      .attr('width', bw)
      .attr('y', (d) => y(Math.max(0, +d.stocks_net) + +d.pension3))
      .attr('height', (d) => y(Math.max(0, +d.stocks_net)) - y(Math.max(0, +d.stocks_net) + +d.pension3))
      .attr('fill', dash.colors[2]);
    svg
      .append('g')
      .selectAll('rect')
      .data(rows.filter((d) => po(d) < 0))
      .join('rect')
      .attr('x', (d) => x(d.month) + off)
      .attr('width', bw)
      .attr('y', (d) => y(Math.min(0, +d.stocks_net)))
      .attr('height', (d) => y(Math.min(0, +d.stocks_net) + po(d)) - y(Math.min(0, +d.stocks_net)))
      .attr('fill', dash.colors[3]);
    svg
      .append('path')
      .datum(rows)
      .attr(
        'd',
        d3
          .line()
          .x((d) => x(d.month) + x.bandwidth() / 2)
          .y((d) => y(cumBy[d.month]))
      )
      .attr('fill', 'none')
      .attr('stroke', dash.colors[4])
      .attr('stroke-width', 2)
      .attr('stroke-linecap', 'round')
      .attr('stroke-linejoin', 'round');
    if (fc) {
      fcBar(svg, fc, x, y, 'var(--color-fg-muted)', bw, off);
      if (rows.length && rows[rows.length - 1].month === last.month)
        svg
          .append('line')
          .attr('x1', x(last.month) + x.bandwidth() / 2)
          .attr('x2', x(J) + x.bandwidth() / 2)
          .attr('y1', y(cumBy[last.month]))
          .attr('y2', y(fc.cum))
          .attr('stroke', dash.colors[4])
          .attr('stroke-width', 2)
          .attr('stroke-dasharray', '4 3')
          .attr('stroke-linecap', 'round');
    }
    const tip = tipFor(el);
    svg
      .append('g')
      .selectAll('rect')
      .data(fc ? [...rows, fc] : rows)
      .join('rect')
      .attr('x', (d) => x(d.month))
      .attr('width', x.bandwidth())
      .attr('y', m.t)
      .attr('height', H - m.t - m.b)
      .attr('fill', 'transparent')
      .on('mousemove', (ev, d) =>
        d === fc
          ? showTip(el, tip, ev, d.label + ' (prognoos)', [
              [null, 'Kuu lõpu prognoos', F.signed(d.v)],
              [dash.colors[4], 'Investeeritud alates ' + YEARS[0], F.eur(d.cum)]
            ])
          : showTip(el, tip, ev, d.label, [
              [dash.colors[0], 'Aktsiad', F.signed(+d.stocks_net)],
              [dash.colors[2], 'Pension', F.signed(+d.pension3)],
              ...(po(d) ? [[dash.colors[3], 'Väljavõtted', F.signed(po(d))]] : []),
              [null, 'Kokku', F.signed(+d.stocks_net + +d.pension3 + po(d))],
              [dash.colors[4], 'Investeeritud alates ' + YEARS[0], F.eur(cumBy[d.month])]
            ])
      )
      .on('mouseleave', () => {
        tip.hidden = true;
      });
  });

  // tootluste juures ainult miinusmärk, pluss jääb ära
  const noPlus = (s) => String(s).replace(/\+/g, '');
  const PARTS = [
    ['price', 'Kapitali kasv', 0],
    ['fx', 'Valuuta mõju', 3],
    ['dividends', 'Tulud', 2],
    ['fees', 'Kulud', 1]
  ];
  const PM = PARTS;
  // instrumentide tabel nagu Portfellow: kapitali kasv, valuuta mõju, tulud, kulud
  const TPARTS = [
    ['price', 'Kapitali kasv', 0],
    ['fx', 'Valuuta mõju', 3],
    ['dividends', 'Tulud', 2],
    ['fees', 'Kulud', 1]
  ];
  const PART_KEYS = TPARTS.map((p) => p[0]);
  const showTable = (box, tip, ev, title, rows, total, foot) => {
    tip.replaceChildren();
    const h = document.createElement('div');
    h.className = 't';
    h.textContent = title;
    tip.append(h);
    tip.append(
      tipRows([
        ...rows.map((r) => [r[0], r[1], r[2], '']),
        [null, total[0], total[1], 'tot'],
        ...(foot || []).map(([l, v]) => [null, l, v, 'ft'])
      ])
    );
    tip.hidden = false;
    const r = box.getBoundingClientRect();
    let x = ev.clientX - r.left + 12;
    if (x + tip.offsetWidth > r.width) x = ev.clientX - r.left - tip.offsetWidth - 12;
    tip.style.left = Math.max(0, x) + 'px';
    tip.style.top = ev.clientY - r.top + 12 + 'px';
  };
  const totM = (d) => d3.sum(PM, ([k]) => +d[k] || 0);
  const stackSigned = (d, parts = PARTS) => {
    let up = 0,
      dn = 0;
    return parts.map(([k, , ci]) => {
      const v = +d[k] || 0;
      const a = v >= 0 ? up : dn;
      const b = a + v;
      if (v >= 0) up = b;
      else dn = b;
      return {k, ci, a: Math.min(a, b), b: Math.max(a, b), v};
    });
  };

  D('portfolio_change_chart', (el) => {
    const got = state(el, 'portfolio_change');
    if (!got) return;
    const all = got[0],
      rows = all.filter(inY);
    el.replaceChildren();
    const W = el.clientWidth || 700,
      H = 280,
      m = {t: 12, r: 8, b: 30, l: 56};
    const x = d3
      .scaleBand(
        rows.map((d) => d.month),
        [m.l, W - m.r]
      )
      .padding(0.25);
    const st = rows.map((d) => ({d, s: stackSigned(d, PM)}));
    const lo = d3.min(st, (o) => d3.min(o.s, (p) => p.a)),
      hi = d3.max(st, (o) => d3.max(o.s, (p) => p.b));
    const y = d3.scaleLinear([Math.min(0, lo) * 1.1, hi * 1.1], [H - m.b, m.t]).nice();
    const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
    grid(svg, y, m, W);
    yAxis(svg, y, m);
    svg
      .append('g')
      .attr('transform', `translate(0,${H - m.b})`)
      .call(
        d3
          .axisBottom(x)
          .tickSize(0)
          .tickPadding(8)
          .tickValues(halfYears(rows))
          .tickFormat((k) => rows.find((r) => r.month === k).label)
      )
      .call(muteAxis);
    const bw = x.bandwidth(),
      off = 0;
    for (const o of st)
      for (const p of o.s)
        if (Math.abs(p.v) > 0.00005)
          svg
            .append('rect')
            .attr('x', x(o.d.month) + off)
            .attr('width', bw)
            .attr('y', y(p.b))
            .attr('height', Math.max(1, y(p.a) - y(p.b)))
            .attr('fill', dash.colors[p.ci]);
    svg
      .append('line')
      .attr('x1', m.l)
      .attr('x2', W - m.r)
      .attr('y1', y(0))
      .attr('y2', y(0))
      .attr('stroke', 'var(--cds-chart-reference)');
    svg
      .append('g')
      .selectAll('circle')
      .data(rows)
      .join('circle')
      .attr('cx', (d) => x(d.month) + x.bandwidth() / 2)
      .attr('cy', (d) => y(totM(d)))
      .attr('r', 3)
      .attr('fill', 'var(--color-fg)');
    const tip = tipFor(el);
    svg
      .append('g')
      .selectAll('rect')
      .data(rows)
      .join('rect')
      .attr('x', (d) => x(d.month))
      .attr('width', x.bandwidth())
      .attr('y', m.t)
      .attr('height', H - m.t - m.b)
      .attr('fill', 'transparent')
      .on('mousemove', (ev, d) => {
        const i = all.indexOf(d),
          base = i > 0 ? +all[i - 1].value + Math.max(0, +d.flow) : Math.max(0, +d.flow);
        const f = (v) => noPlus(HID() ? (base ? F.pctS1(v / base) : '') : F.signed(v));
        showTable(
          el,
          tip,
          ev,
          d.label,
          PM.map(([k, lab, ci]) => [dash.colors[ci], lab, f(+d[k] || 0)]),
          ['Kokku', f(totM(d))],
          HID()
            ? []
            : [
                ['Sisse/välja makstud neto', F.signed(+d.flow)],
                ['Väärtus kuu lõpus', F.eur(+d.value)]
              ]
        );
      })
      .on('mouseleave', () => {
        tip.hidden = true;
      });
  });

  document.querySelectorAll('th[data-tsort]').forEach((th) =>
    th.addEventListener('click', () => {
      const k = th.dataset.tsort,
        p = dash.params(),
        cur = p.tsort || 'total',
        dir = p.tdir || 'desc';
      dash.setParams({tsort: k, tdir: k === cur ? (dir === 'desc' ? 'asc' : 'desc') : k === 'name' ? 'asc' : 'desc'});
    })
  );
  dash.onData(() => {
    const p = dash.params(),
      cur = p.tsort || 'total',
      dir = p.tdir || 'desc';
    document
      .querySelectorAll('th[data-tsort]')
      .forEach((th) =>
        th.setAttribute('aria-sort', th.dataset.tsort === cur ? (dir === 'asc' ? 'ascending' : 'descending') : 'none')
      );
  });
  D('returns_table', (tb) => {
    const d = dash.data('returns');
    tb.replaceChildren();
    if (d.status !== 'ok') return;
    const lg = dash.data('logos');
    const LOGO = lg.status === 'ok' ? Object.fromEntries(lg.data.map((x) => [x.symbol, x.img])) : {};
    const ys = selectedYears(),
      both = ALL_YEARS();
    const rows = d.data
      .map((r) => {
        const o = {...r};
        for (const k of PART_KEYS) o[k] = d3.sum(ys, (yy) => +r[k + '_' + yy] || 0);
        o.total = o.price + o.fx + o.dividends + o.fees;
        o.cost = both ? +r.cost : +r['base_' + ys[0]] || 0;
        // %-vaates perioodi tootlus XIRR-i järgi (nagu Portfellow); osad jagatakse summa suhtes. XIRR-i puudumisel tootlus / keskmine investeeritud summa.
        // üks aasta: selle aasta XIRR; kõik aastad: kogu perioodi XIRR; muu valik: aastate tootlused korrutatult
        const xv = both
          ? r.xr_all
          : ys.length === 1
            ? r['xr_' + ys[0]]
            : ys.every((yy) => r['xr_' + yy] === null || r['xr_' + yy] === undefined || r['xr_' + yy] === '')
              ? null
              : ys.reduce((a, yy) => a * (1 + (+r['xr_' + yy] || 0)), 1) - 1;
        if (HID()) {
          if (xv !== null && xv !== undefined && xv !== '' && Math.abs(o.total) > 1e-9) {
            const k_ = +xv / o.total;
            for (const k of PART_KEYS) o[k] *= k_;
            o.total = +xv;
          } else {
            const ab = +(both ? r.avgb_all : r['avgb_' + ys[0]]) || 0,
              bse = ab > 0.5 ? ab : o.cost;
            for (const k of [...PART_KEYS, 'total']) o[k] = bse ? o[k] / bse : 0;
          }
        }
        return o;
      })
      .filter((o) => Math.abs(o.total) > 0.00005 || o.cost > 0);
    const TS = {
      name: (a, b) => String(a.name).localeCompare(String(b.name), 'et'),
      qty: (a, b) => (+a.qty || 0) - (+b.qty || 0),
      value: (a, b) => (+a.value || 0) - (+b.value || 0),
      total: (a, b) => a.total - b.total,
      price: (a, b) => a.price - b.price,
      fx: (a, b) => a.fx - b.fx,
      dividends: (a, b) => a.dividends - b.dividends,
      fees: (a, b) => a.fees - b.fees
    };
    const sortKey = TS[dash.params().tsort] ? dash.params().tsort : 'total',
      tdir = (dash.params().tdir || 'desc') === 'asc' ? 1 : -1;
    rows.sort((a, b) => tdir * TS[sortKey](a, b) || b.total - a.total);
    // nullist alates: kapitali kasv, rahavoog, valuutakurss
    const st = rows.map((o) => ({d: o, s: stackSigned(o, TPARTS)}));
    const lo = Math.min(0, d3.min(st, (o) => d3.min(o.s, (p) => p.a)) ?? 0),
      hi = Math.max(0, d3.max(st, (o) => d3.max(o.s, (p) => p.b)) ?? 0);
    const span = hi - lo || 1,
      pc = (v) => ((v - lo) / span) * 100;
    const eps = HID() ? 0.0005 : 0.5,
      f = (v) => noPlus(HID() ? F.pctS1(v) : F.signed(v));
    let negSeen = null;
    for (const o of st) {
      const r = o.d,
        held = r.held === true || r.held === 'true',
        isP = r.kind === 'pension',
        tot = +r.total;
      const tr = document.createElement('tr');
      if (!held) tr.className = 'done';
      const pop = document.createElement('div');
      pop.className = 'tpop';
      const ph = document.createElement('div');
      ph.className = 't plogo';
      if (LOGO[r.symbol]) {
        const pim = document.createElement('img');
        pim.src = LOGO[r.symbol];
        pim.alt = r.name;
        ph.append(pim);
      } else ph.textContent = r.name;
      pop.append(ph);
      pop.append(
        tipRows([...TPARTS.map(([k, lab, ci]) => [dash.colors[ci], lab, f(+r[k]), '']), [null, 'Kokku', f(tot), 'tot']])
      );
      const nc = td(tr, '', 'tname' + (isP ? ' fund' : '') + (r.kind === 'deposit' ? ' dep' : ''));
      const lw = document.createElement('span');
      lw.className = 'tlogo';
      if (LOGO[r.symbol]) {
        const im = document.createElement('img');
        im.src = LOGO[r.symbol];
        im.alt = '';
        lw.append(im);
      }
      const nm = document.createElement('span');
      nm.textContent = r.name;
      const tn = document.createElement('div');
      tn.className = 'tn';
      tn.append(lw, nm);
      nc.append(tn);
      const q = +r.qty || 0;
      td(tr, !q ? '' : HID() ? '••••' : Math.round(q).toLocaleString('et-EE'), 'num' + (q && HID() ? ' amtm' : ''));
      td(tr, !+r.value ? '' : F.eur(+r.value), 'num');
      for (const k of PART_KEYS) {
        const v = +r[k] || 0;
        td(tr, Math.abs(v) < eps ? '' : f(v), 'num ' + (v > 0 ? 'ok' : 'bad'));
      }
      td(tr, f(tot), 'num ' + (Math.abs(tot) < eps ? 'muted' : tot > 0 ? 'ok' : 'bad'));
      const cell = td(tr, '', 'wfb');
      const t = document.createElement('div');
      t.className = 'wft';
      const z = document.createElement('div');
      z.className = 'wz';
      z.style.left = pc(0) + '%';
      t.append(z);
      // tootluse järgi sorteerides punane eraldusjoon + ja − ridade vahel (ainult esimese negatiivse rea kohal)
      const isNeg = tot < -eps;
      if (sortKey === 'total' && negSeen !== null && isNeg !== negSeen) tr.classList.add('negfirst');
      negSeen = isNeg;
      const segs = o.s.filter((p) => Math.abs(p.v) > 0.00005);
      // üks ümarate otstega tulp, värvid selle sees
      if (segs.length) {
        const q0 = pc(d3.min(segs, (p) => p.a)),
          q1 = pc(d3.max(segs, (p) => p.b)),
          qw = Math.max(0.4, q1 - q0);
        const w = document.createElement('div');
        w.className = 'wff';
        w.style.left = q0 + '%';
        w.style.width = qw + '%';
        w.style.overflow = 'hidden';
        if (!held) w.style.opacity = 0.5;
        {
          const a0 = d3.min(segs, (p) => p.a),
            b0 = d3.max(segs, (p) => p.b),
            R = 'var(--cds-radius)',
            l = Math.abs(a0) > 1e-9 ? R : '0',
            rr = Math.abs(b0) > 1e-9 ? R : '0';
          w.style.borderRadius = `${l} ${rr} ${rr} ${l}`;
        } // nulljoone poolne ots on sirge
        for (const p of segs) {
          const b = document.createElement('div');
          b.style.position = 'absolute';
          b.style.top = '0';
          b.style.bottom = '0';
          b.style.left = ((pc(p.a) - q0) / qw) * 100 + '%';
          b.style.width = ((pc(p.b) - pc(p.a)) / qw) * 100 + '%';
          b.style.background = dash.colors[p.ci];
          w.append(b);
        }
        t.append(w);
      }
      cell.append(t, pop);
      fixPop(tr, pop, cell);
      tb.append(tr);
    }
  });

  // pealkirja juures valitud perioodi kogutootlus: summa ja % (alus nagu tabelis: mõlemad aastad = soetus, üks aasta = aasta alguse väärtus + ostud)
  D('returns_total', (el) => {
    const d = dash.data('returns'),
      vm = dash.data('portfolio_change');
    el.textContent = '';
    el.className = 'htot';
    if (d.status !== 'ok' || vm.status !== 'ok') return;
    const ys = selectedYears(),
      both = ALL_YEARS();
    let tot = 0;
    for (const r of d.data)
      for (const yy of ys)
        tot +=
          (+r['price_' + yy] || 0) + (+r['fx_' + yy] || 0) + (+r['dividends_' + yy] || 0) + (+r['fees_' + yy] || 0);
    const all = vm.data,
      rows = all.filter((r) => ys.includes(String(r.month).slice(0, 4)));
    const i0 = all.indexOf(rows[0]),
      start = i0 > 0 ? +all[i0 - 1].value : 0;
    const mrf = d.data.find((r) => r.kind === 'deposit');
    // % = perioodi tootlus XIRR-i järgi (nagu Portfellow): rahavood kuu keskel (sissemaksed −, dividendid/intress +), algväärtus −, lõppväärtus +;
    // deposit: average balance in at the start of the period, out with interest at the end
    const t0 = new Date(rows[0].month + '-01'),
      lst = rows[rows.length - 1],
      t1 =
        lst.month >= window.FA.PI.price_date.slice(0, 7)
          ? new Date(window.FA.PI.price_date)
          : new Date(+lst.month.slice(0, 4), +lst.month.slice(5, 7), 0);
    const cf = [];
    if (start > 0.5) cf.push([t0, -start]);
    for (const r of rows) {
      const tm = new Date(r.month + '-15');
      if (+r.flow) cf.push([tm, -r.flow]);
      const dv = (r.dividends_base !== undefined ? +r.dividends_base : +r.dividends) || 0;
      if (dv) cf.push([tm, dv]);
    }
    cf.push([t1, +lst.value]);
    const mb2 = mrf ? +(both ? mrf.avgb_all : mrf['avgb_' + ys[0]]) || 0 : 0;
    if (mb2 > 0.5) {
      cf.push([t0, -mb2]);
      cf.push([t1, mb2 + d3.sum(ys, (yy) => +mrf['dividends_' + yy] || 0)]);
    }
    const tA = d3.min(cf, (c) => c[0]),
      yrs = (t) => (t - tA) / (365 * 864e5);
    const npv = (r) => d3.sum(cf, ([t, a]) => a / Math.pow(1 + r, yrs(t)));
    let lo = -0.9999,
      hi = 100;
    for (let it = 0; it < 200; it++) {
      const mid = (lo + hi) / 2;
      if (npv(mid) > 0 === npv(lo) > 0) lo = mid;
      else hi = mid;
    }
    const prr = Math.pow(1 + lo, yrs(t1)) - 1;
    const base = Math.abs(prr) > 1e-9 ? tot / prr : 0;
    const p = base ? F.pctS1(tot / base) : '';
    el.textContent = noPlus(HID() ? p : F.signed(tot) + (p ? ' · ' + p : ''));
    el.classList.add(tot >= 0 ? 'ok' : 'bad');
  });

  // icons before sector and country names: rules.json settings.icons {name: emoji}
  const ICON = window.FA.ICONS;
  const barsBy = (key) => (tb) => {
    const d = dash.data('portfolio');
    tb.replaceChildren();
    if (d.status !== 'ok') return;
    const rows = d.data;
    const total = d3.sum(rows, (r) => +r.value);
    const groups = d3
      .rollups(
        rows,
        (v) => d3.sum(v, (r) => +r.value),
        (r) => r[key]
      )
      .sort((a, b) => b[1] - a[1]);
    const max = groups[0][1];
    groups.forEach(([name, v], i) => {
      const tr = document.createElement('tr');
      const pre = ICON[name];
      const nc = td(tr, '');
      const tn = document.createElement('div');
      tn.className = 'tn';
      const ic = document.createElement('span');
      ic.className = 'ticon';
      ic.textContent = pre || '';
      const nm = document.createElement('span');
      nm.className = 'tnm';
      nm.textContent = name;
      tn.append(ic, nm);
      nc.append(tn);
      td(tr, F.eur(v), 'num');
      td(tr, F.pct(v / total), 'num muted');
      const cell = td(tr, '', 'wfb');
      const t = document.createElement('div');
      t.className = 'wft';
      const f = document.createElement('div');
      f.className = 'wff';
      f.style.left = '0';
      f.style.width = (v / max) * 100 + '%';
      f.style.background = key === 'sector' ? dash.colors[i % dash.colors.length] : 'var(--color-fg-muted)';
      t.append(f);
      cell.append(t);
      tb.append(tr);
    });
  };
  D('byregion', barsBy('country'));
  D('bysector', barsBy('sector'));
  D('maxpos', (el) => {
    const d = dash.data('portfolio');
    if (d.status !== 'ok') {
      el.textContent = '';
      return;
    }
    const top = [...d.data].sort((a, b) => b.value - a.value)[0];
    el.textContent =
      top.name +
      ' (' +
      (HID() ? F.pct(top.value / d3.sum(d.data, (r) => +r.value)) + ' portfellist' : F.eur(+top.value)) +
      ')';
  });

  D('timeline', (el) => {
    const got = state(el, 'events');
    if (!got) return;
    const rows = got[0].filter(inY).sort((a, b) => String(b.date).localeCompare(String(a.date)));
    el.replaceChildren();
    for (const r of rows) {
      const ev = document.createElement('div');
      ev.className = 'ev';
      const cal = document.createElement('div');
      cal.className = 'cal';
      const cm = document.createElement('span');
      cm.className = 'cm';
      cm.textContent = MONTHS[+r.date.slice(5, 7) - 1];
      const cy = document.createElement('span');
      cy.className = 'cy';
      cy.textContent = r.date.slice(0, 4);
      cal.append(cy, cm);
      const body = document.createElement('div');
      const h = document.createElement('div');
      h.className = 'h';
      h.textContent = r.title;
      const x = document.createElement('div');
      x.className = 'x';
      x.textContent = HID() ? String(r.text).replace(/[+−-]?\d[\d\s .,]*\s?€/g, F.MASK) : r.text;
      if (HID()) {
        x.replaceChildren();
        x.textContent = '';
        for (const part of String(r.text).split(/([+−-]?[0-9][0-9 ., ]*\s?€)/g)) {
          if (!part) continue;
          if (/€$/.test(part) && /[0-9]/.test(part)) {
            const s = document.createElement('span');
            s.className = 'amtm';
            s.textContent = F.MASK;
            x.append(s);
          } else x.append(part);
        }
      }
      body.append(h, x);
      ev.append(cal, body);
      el.append(ev);
    }
  });

  const fill = (tb, id, cols, opts = {}) => {
    const d = dash.data(id);
    tb.replaceChildren();
    if (d.status !== 'ok') return;
    const base = opts.filter ? d.data.filter(opts.filter) : d.data;
    const rows = opts.sort ? [...base].sort(opts.sort) : base;
    for (const r of rows) {
      const tr = document.createElement('tr');
      if (opts.key) tr.dataset.key = r[opts.key];
      if (opts.rowClass) {
        const c = opts.rowClass(r);
        if (c) tr.className = c;
      }
      for (const [k, f, cls] of cols) {
        const v = r[k];
        const c = td(
          tr,
          f ? (Number(v) || f === dt ? f(f === dt ? v : Number(v), r) : '') : (v ?? ''),
          f && f !== dt ? 'num' : f === dt ? 'ctr' : ''
        );
        if (cls) {
          const x = cls(r);
          if (x) c.classList.add(...String(x).split(/\s+/).filter(Boolean));
        }
      }
      tb.append(tr);
    }
  };
  const ysum = (r, k) => d3.sum(selectedYears(), (yy) => +r[k + '_' + yy] || 0);
  const openR = new Set();
  D('trips_table', (tb) => {
    const d = dash.data('trips'),
      kd = dash.data('trip_transactions');
    tb.replaceChildren();
    if (d.status !== 'ok' || kd.status !== 'ok') return;
    // aasta järgi reisi lõpu kuupäev, et ettemaks eelmisel aastal ei viiks reisi valele aastale
    const rs = d.data.filter((r) => yearOn(r.end));
    const TX = d3.group(kd.data, (x) => x.trip + x.start);
    for (const r of rs) {
      const k = r.trip + r.date;
      const tr = document.createElement('tr');
      tr.className = 'g' + (openR.has(k) ? ' open' : '') + (+r.cost < 0 ? ' okrow' : '');
      td(tr, r.trip);
      td(tr, dt(r.trip_start || r.date), 'ctr');
      td(tr, dt(r.end), 'ctr');
      td(tr, F.signed(-r.cost), 'num' + (+r.cost < 0 ? ' ok' : ''));
      tb.append(tr);
      // kanded nagu reisid: uuemad ees
      const kids = [...(TX.get(k) || [])]
        .sort((a, b) => (b.date + (b.time || '')).localeCompare(a.date + (a.time || '')))
        .map((x) => {
          const kr = document.createElement('tr');
          kr.className = 'c' + (+x.amount > 0 ? ' okrow' : '');
          kr.hidden = !openR.has(k);
          const c = td(kr, x.payee);
          if (x.desc) {
            const sp = document.createElement('span');
            sp.className = 'muted';
            sp.textContent = ' · ' + x.desc;
            c.append(sp);
          }
          td(kr, dt(x.date) + (x.time ? ' ' + x.time : ''), 'ctr');
          td(kr, '');
          td(kr, s2b(+x.amount), 'num' + (+x.amount > 0 ? ' ok' : ''));
          tb.append(kr);
          return kr;
        });
      tr.addEventListener('click', () => {
        if (openR.has(k)) openR.delete(k);
        else openR.add(k);
        tr.classList.toggle('open', openR.has(k));
        for (const kr of kids) kr.hidden = !openR.has(k);
      });
    }
    const tot = d3.sum(rs, (r) => +r.cost);
    const tr = document.createElement('tr');
    tr.className = 'tot';
    td(tr, 'Kokku');
    td(tr, '');
    td(tr, '');
    td(tr, F.signed(-tot), 'num');
    tb.append(tr);
  });
  D('oneoff_table', (tb) =>
    fill(tb, 'oneoffs', [['date', dt], ['what'], ['type'], ['amount', F.signed, (r) => (+r.amount >= 0 ? 'ok' : '')]], {
      key: 'id',
      filter: inY,
      sort: (a, b) => String(b.date).localeCompare(String(a.date)) || +b.id - +a.id,
      rowClass: (r) => (+r.amount > 0 ? 'okrow' : '')
    })
  );
  // ---- Püsikulud: laenud lepingu järgi, muu korduvate maksete järgi; muutuv kulu = viimaste täiskuude kulud kokku miinus püsikulud ----
  const openF = new Set();
  // sections of fixed costs come from rules.json recurring_kinds: [{kind, section, subscription?, latest_price?}]
  const KIND = Object.fromEntries(window.FA.KINDS.map((k) => [k.kind, k]));
  const FIXORDER = [LABELS.loan_section, ...new Set(window.FA.KINDS.map((k) => k.section))];
  const SUBSCRIPTION_SECTIONS = new Set(window.FA.KINDS.filter((k) => k.subscription).map((k) => k.section));
  const fixItems = (pk, ln) => {
    const items = [];
    for (const r of ln) {
      if (!window.FA.isActive(r.status) || !(+r.monthly > 0)) continue;
      items.push({
        sec: LABELS.loan_section,
        name: r.loan,
        v: +r.monthly,
        fut: (r.start || '') > window.FA.PI.last_full + '-31',
        info: ''
      });
    }
    for (const r of pk) {
      const kind = KIND[r.kind];
      if (!kind) continue;
      const yr = r.yearly === true || r.yearly === 'true';
      if (r.ended === true || r.ended === 'true' || (!yr && r.last < monthAdd(window.FA.PI.last_full, -1))) continue;
      // latest_price: the last payment, so that a price rise shows; otherwise the latest year's median
      const median = +(
        [...YEARS]
          .reverse()
          .map((yy) => r['med_' + yy])
          .find((v) => +v) || 0
      );
      const med = (kind.latest_price && +r.last_amt) || median;
      if (!med) continue;
      items.push({
        sec: kind.section,
        subscription: !!kind.subscription,
        sub: r.sub,
        name: r.name,
        v: yr ? med / 12 : med,
        yr,
        year: yr ? med : med * 12,
        info: yr ? (HID() ? 'aastatasu' : F.eur(med) + ' aastas') : ''
      });
    }
    return items;
  };
  D('subscriptions_table', (tb) => {
    const pk = dash.data('recurring'),
      ln = dash.data('loans');
    tb.replaceChildren();
    if (pk.status !== 'ok' || ln.status !== 'ok') return;
    const rs = fixItems(pk.data, ln.data)
      .filter((i) => i.subscription)
      .sort((a, b) => b.v - a.v);
    const subOf = (i) => i.sub || LABELS.other;
    // groups in the order of rules.json subscription_groups, then any others
    const subs = [...new Set([...window.FA.SUBSCRIPTION_GROUPS, ...rs.map(subOf)])];
    for (const sub of subs) {
      const ss = rs.filter((i) => subOf(i) === sub);
      if (!ss.length) continue;
      const hr = document.createElement('tr');
      hr.className = 'g' + (openF.has('T' + sub) ? ' open' : '');
      td(hr, sub);
      td(hr, F.eur(d3.sum(ss, (i) => i.v)), 'num');
      td(hr, F.eur(d3.sum(ss, (i) => i.year)), 'num');
      tb.append(hr);
      const kids = ss.map((i) => {
        const tr = document.createElement('tr');
        tr.className = 'c';
        tr.hidden = !openF.has('T' + sub);
        const c = td(tr, i.name);
        if (i.yr) {
          const sp = document.createElement('span');
          sp.className = 'muted';
          sp.textContent = ' · aastatasu';
          c.append(sp);
        }
        td(tr, F.eur(i.v), 'num');
        td(tr, F.eur(i.year), 'num');
        tb.append(tr);
        return tr;
      });
      hr.addEventListener('click', () => {
        const k = 'T' + sub;
        if (openF.has(k)) openF.delete(k);
        else openF.add(k);
        hr.classList.toggle('open', openF.has(k));
        for (const t of kids) t.hidden = !openF.has(k);
      });
    }
    const tr = document.createElement('tr');
    tr.className = 'tot';
    td(tr, 'Kokku');
    td(tr, F.eur(d3.sum(rs, (i) => i.v)), 'num');
    td(tr, F.eur(d3.sum(rs, (i) => i.year)), 'num');
    tb.append(tr);
  });
  D('fixed_table', (tb) => {
    const pk = dash.data('recurring'),
      ln = dash.data('loans'),
      kk = dash.data('month_average');
    tb.replaceChildren();
    if (pk.status !== 'ok' || ln.status !== 'ok' || kk.status !== 'ok') return;
    const K = (m) => +((kk.data.find((r) => r.metric === m) || {}).window || 0);
    const income = K('income'),
      outAll = K('expenses') + K('loans') + K('invest');
    const items = fixItems(pk.data, ln.data);
    const fixed = d3.sum(items, (i) => i.v);
    const pc = (v) => (income ? F.pct(v / income) : '');
    const row = (lab, v, cls) => {
      const tr = document.createElement('tr');
      tr.className = cls;
      td(tr, lab);
      td(tr, F.eur(v), 'num');
      td(tr, pc(v), 'num');
      tb.append(tr);
    };
    row(LABELS.income, income, 'okrow');
    for (const s of FIXORDER) {
      const rs = items.filter((i) => i.sec === s).sort((a, b) => b.v - a.v);
      if (!rs.length) continue;
      if (SUBSCRIPTION_SECTIONS.has(s)) {
        const tr = document.createElement('tr');
        const c = td(tr, s);
        const sp = document.createElement('span');
        sp.className = 'muted';
        sp.textContent = ' · vt tabelit Tellimused';
        c.append(sp);
        td(tr, F.eur(d3.sum(rs, (i) => i.v)), 'num');
        td(tr, pc(d3.sum(rs, (i) => i.v)), 'num muted');
        tb.append(tr);
        continue;
      }
      const tr = document.createElement('tr');
      tr.className = 'g' + (openF.has(s) ? ' open' : '');
      td(tr, s);
      td(tr, F.eur(d3.sum(rs, (i) => i.v)), 'num');
      td(tr, pc(d3.sum(rs, (i) => i.v)), 'num muted');
      tb.append(tr);
      const kids = rs.map((i) => {
        const kr = document.createElement('tr');
        kr.className = 'c';
        kr.hidden = !openF.has(s);
        const c = td(kr, i.name);
        if (i.info) {
          const sp = document.createElement('span');
          sp.className = 'muted';
          sp.textContent = ' · ' + i.info;
          c.append(sp);
        }
        td(kr, F.eur(i.v), 'num');
        td(kr, pc(i.v), 'num');
        tb.append(kr);
        return kr;
      });
      tr.addEventListener('click', () => {
        if (openF.has(s)) openF.delete(s);
        else openF.add(s);
        tr.classList.toggle('open', openF.has(s));
        for (const k of kids) k.hidden = !openF.has(s);
      });
    }
    row('Püsikulud kokku', fixed, 'tot');
    row(
      'Muutuv kulu',
      outAll -
        (fixed -
          d3.sum(
            items.filter((i) => i.fut),
            (i) => i.v
          )),
      'tot'
    );
  });

  // ---- Eesmärgid ----
  const gv = (k) => {
    const d = dash.data('goals');
    const r = d.status === 'ok' ? d.data.find((x) => x.metric === k) : null;
    return r && r.value !== null ? +r.value : null;
  };
  D('goal_progress', (el) => {
    el.replaceChildren();
    const now = gv(el.dataset.now),
      t = gv(el.dataset.target);
    if (now === null || !t) return;
    // alguspunktiga eesmärk (nt netovara): edenemine alguspunktist sihini
    const b0 = el.dataset.base ? gv(el.dataset.base) : null;
    if (b0 !== null) {
      const r = t !== b0 ? (now - b0) / (t - b0) : 0;
      const tr0 = document.createElement('div');
      tr0.className = 'gtrack';
      const f0 = document.createElement('div');
      f0.className = 'gfill';
      f0.style.width = Math.max(0, Math.min(1, r)) * 100 + '%';
      f0.style.background = r >= 1 ? dash.colors[2] : dash.colors[0];
      tr0.append(f0);
      const p0 = document.createElement('div');
      p0.className = 'gpct';
      p0.textContent = F.pct(Math.max(0, Math.min(r, 9.99))) + ' teest';
      el.append(tr0, p0);
      return;
    }
    const tr = document.createElement('div');
    tr.className = 'gtrack';
    const f = document.createElement('div');
    f.className = 'gfill';
    f.style.width = Math.max(0, Math.min(1, now / t)) * 100 + '%';
    const bud = 'budget' in el.dataset;
    f.style.background = bud
      ? now > t
        ? 'var(--cds-chart-status-critical)'
        : dash.colors[0]
      : now >= t
        ? dash.colors[2]
        : dash.colors[0];
    tr.append(f);
    const p = document.createElement('div');
    p.className = 'gpct';
    p.textContent = now < 0 ? 'miinuses' : F.pct(Math.min(now / t, 9.99)) + (bud ? ' eelarvest' : ' sihist');
    if (bud && now > t) p.classList.add('bad');
    el.append(tr, p);
  });
  D('goal_int', (el) => {
    const v = gv(el.dataset.metric);
    el.textContent = v === null ? '' : String(v);
  });
  D('goalchart', (el) => {
    const got = state(el, 'trend', 'goals', 'month_summary', 'cashflow');
    if (!got) return;
    const rows = got[0].filter(inY),
      T = gv('net_target') || 500;
    const J = CURRENT(),
      fe = got[2].find((r) => r.metric === 'forecast_end');
    const fc =
      fe && yearOn(J) && !got[0].some((r) => r.month >= J)
        ? {month: J, label: monthLabel(J), net: +fe.value, v: +fe.value}
        : null;
    // prognoos: järgmised kuud rahavoo prognoosist (jooksev kuu on fc); ainult siis, kui jooksev aasta on valitud
    const fut = yearOn(J) ? got[3].filter((r) => r.month > J).map((r) => ({...r, net: +r.net, fut: true})) : [];
    const all = [...(fc ? [...rows, fc] : rows), ...fut];
    el.replaceChildren();
    const W = el.clientWidth || 700,
      H = 240,
      m = {t: 14, r: 8, b: 30, l: 56};
    const x = d3
      .scaleBand(
        all.map((d) => d.month),
        [m.l, W - m.r]
      )
      .padding(0.25);
    const ext = d3.extent([...all.map((d) => d.net), 0, T]);
    const y = d3.scaleLinear([ext[0] * 1.05, ext[1] * 1.15], [H - m.b, m.t]).nice();
    const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
    grid(svg, y, m, W);
    yAxis(svg, y, m);
    svg
      .append('g')
      .attr('transform', `translate(0,${H - m.b})`)
      .call(
        d3
          .axisBottom(x)
          .tickSize(0)
          .tickPadding(8)
          .tickValues([...halfYears(rows), ...fut.map((d) => d.month).filter((mo) => /-(01|07)$/.test(mo))])
          .tickFormat((k) => all.find((r) => r.month === k).label)
      )
      .call(muteAxis);
    svg
      .append('line')
      .attr('x1', m.l)
      .attr('x2', W - m.r)
      .attr('y1', y(0))
      .attr('y2', y(0))
      .attr('stroke', 'var(--cds-chart-reference)');
    const bw = Math.min(26, x.bandwidth()),
      off = (x.bandwidth() - bw) / 2;
    const col = (v) =>
      v >= T ? dash.colors[2] : v >= 0 ? 'var(--color-fg-muted)' : 'var(--cds-chart-status-critical)';
    svg
      .append('g')
      .selectAll('rect')
      .data(rows)
      .join('rect')
      .attr('x', (d) => x(d.month) + off)
      .attr('width', bw)
      .attr('y', (d) => y(Math.max(0, d.net)))
      .attr('height', (d) => Math.abs(y(d.net) - y(0)))
      .attr('rx', 2)
      .attr('fill', (d) => col(d.net))
      .attr('opacity', (d) => (d.net >= 0 && d.net < T ? 0.6 : 1));
    if (fc) fcBar(svg, fc, x, y, col(fc.net), bw, off);
    svg
      .append('g')
      .selectAll('rect')
      .data(fut)
      .join('rect')
      .attr('x', (d) => x(d.month) + off)
      .attr('width', bw)
      .attr('y', (d) => y(Math.max(0, d.net)))
      .attr('height', (d) => Math.abs(y(d.net) - y(0)))
      .attr('rx', 2)
      .attr('fill', (d) => col(d.net))
      .attr('opacity', 0.4);
    if (fut.length) {
      const fx = x(fut[0].month) - (x.step() * x.paddingInner()) / 2;
      svg
        .append('line')
        .attr('x1', fx)
        .attr('x2', fx)
        .attr('y1', m.t)
        .attr('y2', H - m.b)
        .attr('stroke', 'var(--cds-chart-reference)')
        .attr('stroke-dasharray', '2 3');
      svg
        .append('text')
        .attr('x', fx + 6)
        .attr('y', m.t + 10)
        .attr('fill', 'var(--color-fg-muted)')
        .style('font-size', 'var(--cds-font-size-caption)')
        .text('prognoos');
    }
    svg
      .append('line')
      .attr('x1', m.l)
      .attr('x2', W - m.r)
      .attr('y1', y(T))
      .attr('y2', y(T))
      .attr('stroke', dash.colors[2])
      .attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '5 4');
    svg
      .append('path')
      .datum(rows.filter((d) => d.rolling !== null))
      .attr(
        'd',
        d3
          .line()
          .x((d) => x(d.month) + x.bandwidth() / 2)
          .y((d) => y(d.rolling))
      )
      .attr('fill', 'none')
      .attr('stroke', dash.colors[0])
      .attr('stroke-width', 2)
      .attr('stroke-linecap', 'round')
      .attr('stroke-linejoin', 'round');
    svg
      .append('text')
      .attr('x', W - m.r)
      .attr('y', y(T) - 5)
      .attr('text-anchor', 'end')
      .attr('fill', dash.colors[2])
      .style('font-size', 'var(--cds-font-size-caption)')
      .text('Siht ' + (HID() ? '' : F.signed(T)));
    const tip = tipFor(el);
    svg
      .append('g')
      .selectAll('rect')
      .data(all)
      .join('rect')
      .attr('x', (d) => x(d.month))
      .attr('width', x.bandwidth())
      .attr('y', m.t)
      .attr('height', H - m.t - m.b)
      .attr('fill', 'transparent')
      .on('mousemove', (ev, d) =>
        d.fut
          ? showTip(el, tip, ev, d.label + ' (prognoos)', [
              [null, 'Tulu', F.eur(+d.income)],
              [null, 'Püsikulud', F.eur(-d.fixed)],
              [null, 'Laenud', F.eur(-d.loans)],
              [null, 'Muutuv kulu', F.eur(-d.variable)],
              ...(+d.travel ? [[null, 'Reisid', F.eur(-d.travel)]] : []),
              [null, 'III sammas', F.eur(-d.invest)],
              ...(+d.refund ? [[null, 'Tulumaksutagastus', F.eur(+d.refund)]] : []),
              [col(d.net), 'Tulem', F.signed(d.net)]
            ])
          : d === fc
            ? showTip(el, tip, ev, d.label + ' (prognoos)', [
                [col(d.net), 'Kuu tulemi prognoos', F.signed(d.net)],
                [null, 'Sihist', F.signed(d.net - T)]
              ])
            : showTip(el, tip, ev, d.label, [
                [col(d.net), 'Kuu tulem', F.signed(d.net)],
                [null, 'Sihist', F.signed(d.net - T)],
                ...(d.rolling !== null ? [[dash.colors[0], '12 kuu keskmine', F.signed(d.rolling)]] : [])
              ])
      )
      .on('mouseleave', () => {
        tip.hidden = true;
      });
  });
  // ---- Netovara: rahalised varad üles, võlad alla, joon = netovara ----
  D('net_chart', (el) => {
    const got = state(el, 'net_worth');
    if (!got) return;
    const rows = got[0].filter(inY);
    el.replaceChildren();
    const W = el.clientWidth || 700,
      H = Math.max(280, el.clientHeight || 0),
      m = {t: 12, r: 8, b: 30, l: 64};
    const x = d3
      .scaleBand(
        rows.map((d) => d.month),
        [m.l, W - m.r]
      )
      .padding(0.25);
    const lo = d3.min(rows, (d) => -d.debts),
      hi = d3.max(rows, (d) => d.assets);
    const y = d3.scaleLinear([lo * 1.05, Math.max(hi * 1.1, 1000)], [H - m.b, m.t]).nice();
    const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
    grid(svg, y, m, W);
    yAxis(svg, y, m);
    svg
      .append('g')
      .attr('transform', `translate(0,${H - m.b})`)
      .call(
        d3
          .axisBottom(x)
          .tickSize(0)
          .tickPadding(8)
          .tickValues(halfYears(rows))
          .tickFormat((k) => rows.find((r) => r.month === k).label)
      )
      .call(muteAxis);
    const bw = x.bandwidth();
    svg
      .append('g')
      .selectAll('rect')
      .data(rows)
      .join('rect')
      .attr('x', (d) => x(d.month))
      .attr('width', bw)
      .attr('y', (d) => y(d.assets))
      .attr('height', (d) => y(0) - y(d.assets))
      .attr('fill', dash.colors[2]);
    // võlad: täpsed jäägid tumedamalt, hinnanguline osa (vanad laenud) heledamalt
    svg
      .append('g')
      .selectAll('rect')
      .data(rows)
      .join('rect')
      .attr('x', (d) => x(d.month))
      .attr('width', bw)
      .attr('y', y(0))
      .attr('height', (d) => y(-(d.debts - d.loans_est)) - y(0))
      .attr('fill', dash.colors[1]);
    svg
      .append('g')
      .selectAll('rect')
      .data(rows.filter((d) => d.loans_est > 0))
      .join('rect')
      .attr('x', (d) => x(d.month))
      .attr('width', bw)
      .attr('y', (d) => y(-(d.debts - d.loans_est)))
      .attr('height', (d) => y(-d.debts) - y(-(d.debts - d.loans_est)))
      .attr('fill', dash.colors[1])
      .attr('opacity', 0.45);
    svg
      .append('line')
      .attr('x1', m.l)
      .attr('x2', W - m.r)
      .attr('y1', y(0))
      .attr('y2', y(0))
      .attr('stroke', 'var(--cds-chart-reference)');
    svg
      .append('path')
      .datum(rows)
      .attr(
        'd',
        d3
          .line()
          .x((d) => x(d.month) + bw / 2)
          .y((d) => y(d.net))
      )
      .attr('fill', 'none')
      .attr('stroke', 'var(--color-fg)')
      .attr('stroke-width', 2)
      .attr('stroke-linejoin', 'round');
    svg
      .append('g')
      .selectAll('circle')
      .data(rows)
      .join('circle')
      .attr('cx', (d) => x(d.month) + bw / 2)
      .attr('cy', (d) => y(d.net))
      .attr('r', 3)
      .attr('fill', 'var(--color-fg)');
    const tip = tipFor(el);
    svg
      .append('g')
      .selectAll('rect')
      .data(rows)
      .join('rect')
      .attr('x', (d) => x(d.month))
      .attr('width', bw)
      .attr('y', m.t)
      .attr('height', H - m.t - m.b)
      .attr('fill', 'transparent')
      .on('mousemove', (ev, d) =>
        showTable(
          el,
          tip,
          ev,
          d.label,
          [
            ...(d.car ? [[dash.colors[2], d.car_name || 'Auto', F.eur(d.car)]] : []),
            [dash.colors[2], 'Investeeringud', F.eur(d.investments)],
            ...(d.pension2 ? [[dash.colors[2], 'II sammas', F.eur(d.pension2)]] : []),
            [dash.colors[2], 'Kontod', F.eur(d.cash)],
            ...(d.deposit > 0.5 ? [[dash.colors[2], 'Hoius', F.eur(d.deposit)]] : []),
            [
              dash.colors[1],
              'Laenud' + (d.loans_est > 0.5 ? ' (sh hinnang ' + (HID() ? '' : F.eur(d.loans_est)) + ')' : ''),
              F.signed(-d.loans)
            ],
            [dash.colors[1], 'Krediitkaart', F.signed(-d.card)]
          ],
          ['Netovara', F.signed(d.net)]
        )
      )
      .on('mouseleave', () => {
        tip.hidden = true;
      });
  });
  D('net_total', (el) => {
    const d = dash.data('net_worth');
    el.textContent = '';
    el.className = 'htot';
    if (d.status !== 'ok' || !d.data.length) return;
    const a = d.data[d.data.length - 1],
      ys = selectedYears();
    const b = d.data.filter((r) => ys.includes(r.month.slice(0, 4)))[0];
    const i0 = d.data.indexOf(b),
      base = i0 > 0 ? d.data[i0 - 1] : b;
    if (HID()) {
      el.textContent = '';
      return;
    }
    el.textContent = F.signed(a.net) + ' · muutus ' + F.signed(a.net - base.net);
  });

  // ---- Tulevik: rahavoog, laenamise hind, pension ----
  D('goal_num', (el) => {
    const d = dash.data(el.dataset.source);
    const r = d.status === 'ok' ? d.data.find((x) => x.metric === el.dataset.where.split('=')[1]) : null;
    if (!r || r.value === null) {
      el.textContent = '';
      return;
    }
    const v = +r.value;
    el.textContent = el.dataset.pct
      ? Math.round(v * 100) + '%'
      : v.toLocaleString('et-EE', {
          minimumFractionDigits: +(el.dataset.dec || 0),
          maximumFractionDigits: +(el.dataset.dec || 0)
        });
  });
  D('cost_head', (hr) => {
    hr.replaceChildren();
    for (const [t, cls] of [['Laen', ''], ...selectedYears().map((yy) => [yy, 'num'])]) {
      const e = document.createElement('th');
      e.textContent = t;
      if (cls) e.className = cls;
      hr.append(e);
    }
  });
  D('cost_table', (tb) => {
    const d = dash.data('loan_cost');
    tb.replaceChildren();
    if (d.status !== 'ok') return;
    const yr = (v) => (+v ? F.eur(+v) : '');
    for (const r of d.data) {
      if (!selectedYears().some((yy) => +r['paid_' + yy])) continue;
      const tr = document.createElement('tr');
      const c = td(tr, r.loan);
      c.title = r.note || '';
      for (const yy of selectedYears()) td(tr, yr(r['paid_' + yy]), 'num');
      tb.append(tr);
    }
    const k = dash.data('loan_cost_total');
    if (k.status !== 'ok') return;
    const g = (n) => +((k.data.find((x) => x.metric === n) || {}).value || 0);
    const tr = document.createElement('tr');
    tr.style.fontWeight = 'var(--cds-font-weight-medium)';
    td(tr, 'Kokku');
    for (const yy of selectedYears()) td(tr, F.eur(g('paid_' + yy)), 'num');
    tb.append(tr);
  });
  D('pension_table', (tb) => {
    const d = dash.data('pension_view');
    tb.replaceChildren();
    if (d.status !== 'ok') return;
    const g = (n) => +((d.data.find((x) => x.metric === n) || {}).value || 0);
    const rows = [
      ['III sammas praegu', F.eur(g('p3_value'))],
      ['Muud fondid praegu', F.eur(g('funds_value'))],
      ['Neto sisse makstud', F.eur(g('paid_p3') + g('paid_funds'))],
      ['Tulu', F.signed(g('gain'))],
      ['Sissemakse', F.eur(g('contrib_month')) + ' kuus, ' + F.eur(g('contrib_year')) + ' aastas'],
      ['Tulumaksutagastus', F.eur(g('refund_year')) + ' aastas'],
      ['Vanus praegu / pensioniiga', g('age_now') + ' / ' + g('pension_age')],
      ['Aega pensionieani', g('years_left').toLocaleString('et-EE', {maximumFractionDigits: 1}) + ' aastat'],
      ['Prognoos pensionieaks', F.eur(g('fv'))],
      ['Sama ilma tootluseta', F.eur(g('fv_paid'))],
      ['Prognoos kuus 20 aasta peale', F.eur(g('fv_month'))],
      ['II sambast välja võetud', F.eur(g('ii_withdrawn'))],
      ['II sambaga saab uuesti liituda', String(g('ii_rejoin_year'))]
    ];
    for (const [a, b] of rows) {
      const tr = document.createElement('tr');
      td(tr, a);
      td(tr, b, 'num');
      tb.append(tr);
    }
  });
  // ---- Säästumäär (jooksev aasta): investeeringud + laenu põhiosa / tulu ----
  D('savings', (el) => {
    const d = dash.data('savings_rate');
    el.replaceChildren();
    if (d.status !== 'ok') return;
    const p = (a, b) => d.data.filter((r) => r.month >= a && r.month <= b);
    const rate = (rs) => d3.sum(rs, (r) => r.invest + r.principal) / d3.sum(rs, (r) => r.income);
    // viimased täiskuud vs eelmised sama palju kuid (säästumäär arvutatakse ainult jooksva aasta kohta)
    const WINR = window.FA.PI.window,
      nA = (+WINR[1].slice(0, 4) - +WINR[0].slice(0, 4)) * 12 + (+WINR[1].slice(5) - +WINR[0].slice(5)) + 1;
    const p4 = p(...WINR),
      p3 = p(monthAdd(WINR[0], -nA), monthAdd(WINR[0], -1));
    const big = document.createElement('div');
    big.className = 'big';
    big.textContent = F.pct(rate(p4));
    const s1 = document.createElement('div');
    s1.className = 'sub';
    s1.append('Viimased ' + nA + ' kuud, kuus ');
    const inv = document.createElement('span');
    inv.textContent = F.eur(d3.mean(p4, (r) => r.invest));
    if (inv.textContent === F.MASK) inv.className = 'amtm';
    const pr = document.createElement('span');
    pr.textContent = F.eur(d3.mean(p4, (r) => r.principal));
    if (pr.textContent === F.MASK) pr.className = 'amtm';
    s1.append(inv, ' investeeringuid ja ', pr, ' laenu põhiosa');
    const ch = rate(p4) - rate(p3);
    const s2 = document.createElement('div');
    s2.className = 'sub chg ' + (Math.abs(ch) < 0.01 ? '' : ch > 0 ? 'ok' : 'bad');
    s2.textContent =
      (Math.abs(ch) < 0.01 ? '≈ ' : ch > 0 ? '▲ ' : '▼ ') +
      (ch > 0 ? '+' : ch < 0 ? '−' : '') +
      Math.abs(Math.round(ch * 1000) / 10).toLocaleString('et-EE') +
      ' pp vs eelmised ' +
      nA +
      ' kuud';
    el.append(big, s1, s2);
  });

  // ---- Võrdlus indeksitega ----
  D('comparison_table', (tb) => {
    const d = dash.data('comparison');
    tb.replaceChildren();
    if (d.status !== 'ok') return;
    const ys = selectedYears(),
      P = ys.length === 1 ? ys[0] : 'all';
    const rs = d.data.filter((r) => r.period === P && r.ret !== null);
    const pf = rs.find((r) => r.kind === 'portfolio');
    rs.sort((a, b) => (b.kind === 'portfolio') - (a.kind === 'portfolio') || b.ret - a.ret);
    const lo = Math.min(
        0,
        d3.min(rs, (r) => r.ret)
      ),
      hi = Math.max(
        0,
        d3.max(rs, (r) => r.ret)
      ),
      sp = hi - lo || 1,
      pc = (v) => ((v - lo) / sp) * 100;
    for (const r of rs) {
      const tr = document.createElement('tr');
      if (r.kind === 'portfolio') tr.style.fontWeight = 'var(--cds-font-weight-medium)';
      const c = td(tr, r.name);
      c.title = r.src;
      td(tr, noPlus(F.pctS1(r.ret)), 'num ' + (r.ret >= 0 ? 'ok' : 'bad'));
      const dv = pf ? pf.ret - r.ret : 0;
      td(
        tr,
        r.kind === 'portfolio' || !pf
          ? ''
          : (dv < 0 ? '−' : '') +
              Math.abs(Math.round(dv * 1000) / 10).toLocaleString('et-EE', {
                minimumFractionDigits: 1,
                maximumFractionDigits: 1
              }) +
              ' pp',
        'num ' + (r.kind === 'portfolio' ? '' : dv >= 0 ? 'ok' : 'bad')
      );
      const cell = td(tr, '', 'wfb');
      const t = document.createElement('div');
      t.className = 'wft';
      const z = document.createElement('div');
      z.className = 'wz';
      z.style.left = pc(0) + '%';
      t.append(z);
      const f = document.createElement('div');
      f.className = 'wff';
      f.style.left = pc(Math.min(0, r.ret)) + '%';
      f.style.width = Math.max(0.4, pc(Math.max(0, r.ret)) - pc(Math.min(0, r.ret))) + '%';
      f.style.background = r.kind === 'portfolio' ? dash.colors[0] : 'var(--color-fg-muted)';
      f.style.borderRadius =
        r.ret >= 0 ? '0 var(--cds-radius) var(--cds-radius) 0' : 'var(--cds-radius) 0 0 var(--cds-radius)';
      t.append(f);
      cell.append(t);
      tb.append(tr);
    }
  });

  // ---- Oodatavad dividendid järgmise 12 kuu jooksul ----
  D('div_chart', (el) => {
    const got = state(el, 'expected_dividends');
    if (!got) return;
    const rows = got[0];
    el.replaceChildren();
    const M = [],
      J = window.FA.PI.current;
    for (let i = 0; i < 12; i++) {
      const dd2 = new Date(+J.slice(0, 4), +J.slice(5, 7) - 1 + i, 1);
      M.push(dd2.getFullYear() + '-' + String(dd2.getMonth() + 1).padStart(2, '0'));
    }
    const by = d3.group(rows, (r) => r.month),
      tot = (mo) => d3.sum(by.get(mo) || [], (r) => +r.amount);
    const W = el.clientWidth || 600,
      H = 220,
      m = {t: 12, r: 8, b: 30, l: 44};
    const x = d3.scaleBand(M, [m.l, W - m.r]).padding(0.25);
    const y = d3.scaleLinear([0, (d3.max(M, tot) || 1) * 1.1], [H - m.b, m.t]).nice();
    const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
    grid(svg, y, m, W);
    yAxis(svg, y, m);
    svg
      .append('g')
      .attr('transform', `translate(0,${H - m.b})`)
      .call(
        d3
          .axisBottom(x)
          .tickSize(0)
          .tickPadding(8)
          .tickFormat((k) =>
            x.step() < 40 ? MONTHS[+k.slice(5) - 1].charAt(0).toUpperCase() : MONTHS[+k.slice(5) - 1]
          )
      )
      .call(muteAxis);
    // kinnitatud (börsil välja kuulutatud) all täisvärviga, hinnang peal heledamalt
    const isC = (r) => r.confirmed === true || r.confirmed === 'true';
    const conf = (mo) => d3.sum((by.get(mo) || []).filter(isC), (r) => +r.amount);
    svg
      .append('g')
      .selectAll('rect')
      .data(M)
      .join('rect')
      .attr('x', (k) => x(k))
      .attr('width', x.bandwidth())
      .attr('y', (k) => y(tot(k)))
      .attr('height', (k) => y(conf(k)) - y(tot(k)))
      .attr('fill', dash.colors[2])
      .attr('opacity', 0.4);
    svg
      .append('g')
      .selectAll('rect')
      .data(M.filter((k) => conf(k) > 0))
      .join('rect')
      .attr('x', (k) => x(k))
      .attr('width', x.bandwidth())
      .attr('y', (k) => y(conf(k)))
      .attr('height', (k) => y(0) - y(conf(k)))
      .attr('fill', dash.colors[2]);
    const tip = tipFor(el);
    svg
      .append('g')
      .selectAll('rect')
      .data(M)
      .join('rect')
      .attr('x', (k) => x(k))
      .attr('width', x.bandwidth())
      .attr('y', m.t)
      .attr('height', H - m.t - m.b)
      .attr('fill', 'transparent')
      .on('mousemove', (ev, k) => {
        const rs = [...(by.get(k) || [])].sort((a, b) => isC(b) - isC(a) || b.amount - a.amount);
        showTable(
          el,
          tip,
          ev,
          MONTHS[+k.slice(5) - 1] + ' ' + k.slice(0, 4),
          rs.map((r) => [
            dash.colors[2],
            r.name + (isC(r) ? ' · kinnitatud ' + dt(r.date).slice(0, 6) : ' · hinnang'),
            F.eur2(+r.amount)
          ]),
          ['Kokku', F.eur2(tot(k))]
        );
      })
      .on('mouseleave', () => {
        tip.hidden = true;
      });
  });
  D('div_total', (el) => {
    const d = dash.data('expected_dividends');
    el.className = 'htot';
    el.textContent = '';
    if (d.status !== 'ok') return;
    const c = d3.sum(
      d.data.filter((r) => r.confirmed === true || r.confirmed === 'true'),
      (r) => +r.amount
    );
    el.textContent = HID() ? '' : F.eur(d3.sum(d.data, (r) => +r.amount)) + (c ? ' · kinnitatud ' + F.eur2(c) : '');
  });

  // Kokkupandavad kaardid (.fold) on vaikimisi kinni, pealkiri avab ja sulgeb
  // (avamine käib peidetud märkeruuduga, vt index.html .cardt)
  // puuteekraanil: ? avab ja sulgeb selgituse koputusega, koputus mujal sulgeb
  document.addEventListener('click', (e) => {
    const b = e.target.closest('.help');
    if (!b && e.target.closest('.help + .note')) return;
    document.querySelectorAll('.fa .help.open').forEach((x) => {
      if (x !== b) x.classList.remove('open');
    });
    if (b) {
      b.classList.toggle('open');
      if (!b.classList.contains('open')) b.blur();
    }
  });
  // tabeli viimasel nähtaval real pole alumist joont. Klass lastv pannakse siin, mitte CSS-i :has(~ …) abil,
  // sest see tegi suurte tabelite (Kanded) puhul Safari iga muudatuse peale väga aeglaseks.
  const lastVis = (tb) => {
    let l = null;
    for (const tr of tb.rows) {
      if (tr.classList.contains('lastv')) tr.classList.remove('lastv');
      if (!tr.hidden) l = tr;
    }
    if (l) l.classList.add('lastv');
  };
  const tbq = new Set();
  let tbf = 0;
  new MutationObserver((ms) => {
    for (const m of ms) {
      const tb =
        (m.target.closest && m.target.closest('tbody')) || (m.target.querySelector && m.target.querySelector('tbody'));
      if (tb) tbq.add(tb);
      if (m.type === 'childList' && m.target.querySelectorAll)
        m.target.querySelectorAll('tbody').forEach((t) => tbq.add(t));
    }
    if (!tbf)
      tbf = requestAnimationFrame(() => {
        tbf = 0;
        tbq.forEach(lastVis);
        tbq.clear();
      });
  }).observe(document.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['hidden']});
  document.querySelectorAll('tbody').forEach(lastVis);
  // vahelehe vahetusel joonista uuesti: peidetud vahelehe graafikud joonistati vaikelaiusega ja olid telefonis liiga madalad
  document.querySelectorAll('.fa > input.tabr').forEach((i) =>
    i.addEventListener('change', () => {
      if (i.checked && dash.refresh) requestAnimationFrame(() => dash.refresh());
    })
  );
  // telefoni pööramisel joonista graafikud uue laiusega
  let rw = window.innerWidth,
    rt = null;
  window.addEventListener('resize', () => {
    if (Math.abs(window.innerWidth - rw) < 40) return;
    rw = window.innerWidth;
    clearTimeout(rt);
    rt = setTimeout(() => {
      if (dash.refresh) dash.refresh();
    }, 250);
  });
})();
