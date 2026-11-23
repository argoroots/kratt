(() => {
  const eur0 = new Intl.NumberFormat('et-EE', {maximumFractionDigits: 0});
  const eur2 = new Intl.NumberFormat('et-EE', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const one = new Intl.NumberFormat('et-EE', {maximumFractionDigits: 1});
  const one1 = new Intl.NumberFormat('et-EE', {minimumFractionDigits: 1, maximumFractionDigits: 1});
  const prm = () => {
    try {
      return dash.params() || {};
    } catch (e) {
      return {};
    }
  };
  const isHidden = () => prm().amt === 'off';
  // periods and years: config.js (written by build.py on every update)
  const PI = window.RAHAPADA.periods;
  const YEARS = PI.years;
  // by default only the last year is selected; the choice is in the address as y<year> = on/off
  const CUR_YEAR = YEARS[YEARS.length - 1];
  const yearOn = (y) => {
    const k = String(y).slice(0, 4),
      v = prm()['y' + k];
    return v ? v !== 'off' : k === CUR_YEAR;
  };
  const MASK = '     ';
  const F = {
    eur: (v) => (isHidden() ? F.MASK : eur0.format(Math.round(v) + 0) + ' €'), // + 0: −0 -> 0
    eur2: (v) => (isHidden() ? F.MASK : eur2.format(Math.round(v * 100) / 100 + 0) + ' €'),
    signed: (v) =>
      isHidden()
        ? F.MASK
        : (Math.round(v) > 0 ? '+' : Math.round(v) < 0 ? '−' : '') + eur0.format(Math.abs(Math.round(v))) + ' €',
    pct: (v) => eur0.format(Math.round(v * 100)) + '%',
    pct1: (v) => one.format(v * 100) + '%',
    pctsigned: (v) => (v > 0 ? '+' : v < 0 ? '−' : '') + one.format(Math.abs(v * 100)) + '%',
    pctS1: (v) => {
      const r = Math.round(v * 1000) / 10;
      return (r > 0 ? '+' : r < 0 ? '−' : '') + one1.format(Math.abs(r)) + '%';
    }
  };
  // sections whose datasets are empty (no investments, loans, ...) are hidden; their drawings and calcs are skipped
  const EMPTY = new Set(window.RAHAPADA.empty || []);
  const off = (el) => {
    for (let e = el.closest('[data-feature]'); e; e = e.parentElement && e.parentElement.closest('[data-feature]')) {
      if (e.dataset.feature.split(' ').some((d) => EMPTY.has(d))) return true;
    }
    return false;
  };
  const draw = (name, fn) => dash.draw(name, (el, ...a) => (off(el) ? el.replaceChildren() : fn(el, ...a)));
  const NEEDS = {
    invest_total: ['investment_months'],
    invest_compare: ['investment_months', 'portfolio_change'],
    invest_summary: ['portfolio_change'],
    portfolio_total: ['portfolio'],
    loans_total: ['loans'],
    assets_total: ['assets']
  };
  const calc = (name, def) =>
    dash.calc(name, (NEEDS[name] || []).some((d) => EMPTY.has(d)) ? {...def, fn: () => []} : def);
  dash.draw('features', (el) => {
    el.textContent = [...EMPTY].map((d) => `[data-feature~="${d}"]{display:none!important}`).join('\n');
  });
  F.MASK = '•••• €'; // a hidden amount is shown as four blurred middle dots
  // loan status in the loan files: active/ended (or the Estonian Aktiivne/Lõppenud)
  const isActive = (s) => s === 'active' || s === 'Aktiivne';
  // names from the user's rules (rules.json settings.labels, recurring_kinds, subscription_groups, icons)
  const LABELS = window.RAHAPADA.labels || {};
  const KINDS = window.RAHAPADA.recurring_kinds || [];
  const SUBSCRIPTION_GROUPS = window.RAHAPADA.subscription_groups || [];
  const ICONS = window.RAHAPADA.icons || {};
  window.FA = {F, draw, isHidden, yearOn, PI, PERIODS: PI.periods, isActive, LABELS, KINDS, SUBSCRIPTION_GROUPS, ICONS};

  // Controls: year buttons and the € button live in the HTML; scripts only listen and set class / aria-*.
  // the year buttons are made from the list of years
  const sync = () => {
    document.querySelectorAll('.fa').forEach((r) => {
      r.classList.toggle('hide-amt', isHidden());
    });
    document
      .querySelectorAll('.ybtn[data-year]')
      .forEach((b) => b.setAttribute('aria-pressed', String(yearOn(b.dataset.year))));
    document.querySelectorAll('.ybtn[data-amt]').forEach((b) => b.setAttribute('aria-pressed', String(!isHidden())));
  };
  // the year buttons are a drawing (data-draw="years") made from the list of years
  const onYear = (y) => {
    // at least one year stays selected
    const sel = YEARS.filter((a) => (a === y) !== yearOn(a));
    if (!sel.length) return;
    dash.setParams(Object.fromEntries(YEARS.map((a) => ['y' + a, sel.includes(a) ? 'on' : 'off'])));
    sync();
  };
  dash.draw('years', (g) => {
    g.replaceChildren(
      ...YEARS.map((y) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'ybtn';
        b.dataset.year = y;
        b.textContent = y;
        b.setAttribute('aria-pressed', String(yearOn(y)));
        b.addEventListener('click', () => onYear(y));
        return b;
      })
    );
  });
  document.querySelectorAll('.ybtn[data-amt]').forEach((b) =>
    b.addEventListener('click', () => {
      dash.setParams({amt: isHidden() ? null : 'off'});
      sync();
    })
  );
  dash.onData(sync);

  // P4 = current level (last full months, rolling), AE = the same months a year earlier
  const PERIODS = PI.periods,
    LAST_FULL = PI.last_full,
    WIN = PI.window,
    WIN_PREV = PI.window_prev;
  // investment taken off the month's result: pillar III and net stock purchases; selling stocks does not add to the result (investment_months.invest_out)
  const outOf = (ik) => {
    const I = Object.fromEntries(
      ik.map((r) => [r.month, r.invest_out !== undefined ? +r.invest_out : Math.max(0, +r.stocks_net) + +r.pension3])
    );
    return (r) => I[r.month] || 0;
  };
  const inWindow = (w) => (r) => r.month >= w[0] && r.month <= w[1];

  calc('month_average', {
    title: 'Kuu keskmine perioodide kaupa',
    description:
      'Tulude, kulude, laenumaksete, ühekordsete maksete, säästude ja vahe kuu keskmine poolaastate ja kvartalite kaupa ning viimastel täiskuudel (aken).',
    inputs: ['months', 'investment_months'],
    fn: (monthRows, ik) => {
      const I = Object.fromEntries(ik.map((r) => [r.month, +r.stocks_net + +r.pension3]));
      const inv = (r) => I[r.month] || 0,
        io = outOf(ik);
      const rows = [
        ['income', LABELS.income, (r) => +r.income],
        ['expenses', 'Igapäevakulud', (r) => +r.expenses],
        ['loans', LABELS.loan_section, (r) => +r.loans],
        ['invest', LABELS.investments, inv],
        ['net_regular', 'Korraline vahe', (r) => +r.income - +r.expenses - +r.loans - io(r)],
        ['oneoff', 'Ühekordsed maksed', (r) => +r.oneoff],
        ['out', 'Kulud ja laenumaksed kokku', (r) => +r.expenses + +r.loans + +r.oneoff],
        ['saved', 'Säästud (III sammas + aktsiad)', (r) => +r.pension3 + +r.to_aktsiad]
      ];
      return rows.map(([metric, label, g]) => {
        const o = {metric, label};
        for (const [k, [a, b]] of Object.entries({...PERIODS, aken: WIN}))
          o[k] = d3.mean(
            monthRows.filter((r) => r.month >= a && r.month <= b),
            g
          );
        return o;
      });
    }
  });

  calc('trend', {
    title: 'Korraline vahe ja 12 kuu keskmine',
    description: 'Iga täiskuu korraline vahe ja selle 12 kuu libisev keskmine.',
    inputs: ['months', 'investment_months'],
    fn: (monthRows, ik) => {
      const io = outOf(ik);
      const nt = (r) => +r.income - +r.expenses - +r.loans - io(r);
      const k = monthRows.filter((r) => r.month <= LAST_FULL);
      return k.map((r, i) => {
        const net = nt(r);
        const win = k.slice(Math.max(0, i - 11), i + 1);
        return {month: r.month, label: r.label, net, rolling: i >= 11 ? d3.mean(win, nt) : null};
      });
    }
  });

  calc('header', {
    title: 'Päise numbrid',
    description:
      'Kuu tulem pärast kulusid, laenumakseid ja investeeringuid (aktsiate müük tulemit ei suurenda) ning kulud kokku (kulud ja laenumaksed): viimaste täiskuude kuu keskmine ja muutus samade kuudega aasta varem võrreldes.',
    inputs: ['months', 'investment_months'],
    fn: (monthRows, ik) => {
      const io = outOf(ik);
      const out = (r) => +r.expenses + +r.loans,
        net = (r) => +r.income - out(r) - io(r);
      const p4 = monthRows.filter((r) => r.month >= WIN[0] && r.month <= WIN[1]),
        prevYear = monthRows.filter(inWindow(WIN_PREV));
      return [
        // comparison with a year earlier only when those months are in the data
        {metric: 'net', value: d3.mean(p4, net)},
        {metric: 'net_diff', value: prevYear.length ? d3.mean(p4, net) - d3.mean(prevYear, net) : null},
        {metric: 'out', value: d3.mean(p4, out)},
        {metric: 'out_diff', value: prevYear.length ? d3.mean(p4, out) - d3.mean(prevYear, out) : null}
      ];
    }
  });

  calc('lead_group', {
    title: 'Suurim kulugrupp',
    description: 'Viimaste täiskuude (aken) suurim kulugrupp (investeeringud välja arvatud) ja selle osa tulust.',
    inputs: ['group_months', 'months'],
    fn: (gm, monthRows) => {
      const w = (r) => r.month >= WIN[0] && r.month <= WIN[1];
      const n = monthRows.filter(w).length || 1;
      const by = d3
        .rollups(
          gm.filter((r) => w(r) && r.grp !== LABELS.investments),
          (v) => d3.sum(v, (r) => +r.amount) / n,
          (r) => r.grp
        )
        .sort((a, b) => b[1] - a[1]);
      const inc = d3.mean(monthRows.filter(w), (r) => +r.income);
      return by.length
        ? [{metric: 'group', value: by[0][0], amount: by[0][1], share: inc ? by[0][1] / inc : null}]
        : [];
    }
  });

  calc('trend_total', {
    title: 'Laenukoorem perioodide kaupa',
    description: 'Korraliste laenu- ja liisingumaksete osa tuludest neljal perioodil.',
    inputs: ['months'],
    fn: (monthRows) =>
      Object.entries({...PERIODS, aken: WIN}).map(([k, [a, b]]) => {
        const r = monthRows.filter((x) => x.month >= a && x.month <= b);
        return {metric: 'loan_share_' + k, value: d3.sum(r, (x) => +x.loans) / d3.sum(r, (x) => +x.income)};
      })
  });

  calc('invest_total', {
    title: 'Investeeringud kokku',
    description:
      'Neto sisse makstud aktsiatesse, viimaste täiskuude kuine investeering ja määr tulust, III samba maksed ja viimase 12 kuu dividendid.',
    inputs: ['investment_months'],
    fn: (invest_kuud) => {
      const p4 = invest_kuud.filter((r) => r.month >= WIN[0] && r.month <= WIN[1]);
      const last12 = invest_kuud.slice(-12);
      const monthly = d3.mean(p4, (r) => +r.stocks_net + +r.pension3);
      return [
        {metric: 'invested', value: +invest_kuud[invest_kuud.length - 1].stocks_cum},
        {metric: 'monthly_p4', value: monthly},
        {metric: 'rate_p4', value: monthly / d3.mean(p4, (r) => +r.income)},
        {metric: 'pension_p4', value: d3.mean(p4, (r) => +r.pension3)},
        {metric: 'pension_total', value: d3.sum(invest_kuud, (r) => +r.pension3)},
        {metric: 'div12', value: d3.sum(last12, (r) => +r.dividends)}
      ];
    }
  });

  calc('invest_compare', {
    title: 'Investeeringud võrreldes eelmise aastaga',
    description:
      'Kõik investeeringud koos (aktsiad ja pensionifondid): igakuine investeering (viimased täiskuud vs samad kuud aasta varem), neto sisse makstud (jooksev aasta vs eelmine aasta), väärtus (praegu vs eelmise aasta lõpus) ja dividendid (jooksva aasta algusest viimase täiskuuni vs sama aeg eelmisel aastal).',
    inputs: ['investment_months', 'portfolio_change'],
    fn: (k, v) => {
      const y = (yy, mx = '12') => k.filter((r) => r.month.slice(0, 4) === yy && r.month.slice(5) <= mx);
      const p4 = k.filter((r) => r.month >= WIN[0] && r.month <= WIN[1]);
      const CUR_Y = LAST_FULL.slice(0, 4),
        PREV_YEAR = String(+CUR_Y - 1); // the year of the last full month and the year before
      const endPrev = v.find((r) => r.month === PREV_YEAR + '-12');
      const inv = (r) => +r.stocks_net + +r.pension3;
      const fl = (yy) =>
        d3.sum(
          v.filter((r) => r.month.slice(0, 4) === yy),
          (r) => +r.flow
        );
      return [
        {metric: 'monthly', now: d3.mean(p4, inv), prev: d3.mean(k.filter(inWindow(WIN_PREV)), inv)},
        {metric: 'stocks', now: fl(CUR_Y), prev: fl(PREV_YEAR)},
        {metric: 'value', now: +v[v.length - 1].value, prev: endPrev ? +endPrev.value : null},
        {
          metric: 'div',
          now: d3.sum(y(CUR_Y, LAST_FULL.slice(5)), (r) => +r.dividends),
          prev: d3.sum(y(PREV_YEAR, LAST_FULL.slice(5)), (r) => +r.dividends)
        }
      ];
    }
  });

  calc('invest_summary', {
    title: 'Kõik investeeringud kokku',
    description:
      'Aktsiad ja pensionifondid koos: neto sisse makstud andmete algusest (väljavõtted maha arvatud), väärtus praegu ning kasum (väärtus miinus neto sisse makstud, dividendid ei ole sees).',
    inputs: ['portfolio_change'],
    fn: (v) => {
      const inv = d3.sum(v, (r) => +r.flow),
        val = +v[v.length - 1].value;
      return [
        {metric: 'invested', value: inv},
        {metric: 'value', value: val},
        {metric: 'profit', value: val - inv},
        {metric: 'profit_pct', value: inv ? (val - inv) / inv : 0}
      ];
    }
  });

  calc('portfolio_total', {
    title: 'Portfell kokku',
    description: 'Positsioonide väärtus, kasum, kasum protsendina soetusmaksumusest ja keskmine positsioon.',
    inputs: ['portfolio'],
    fn: (portfolioRows) => {
      const value = d3.sum(portfolioRows, (r) => +r.value),
        pl = d3.sum(portfolioRows, (r) => +r.pl),
        cost = d3.sum(portfolioRows, (r) => +r.cost);
      return [
        {metric: 'value', value},
        {metric: 'pl', value: pl},
        {metric: 'pl_pct', value: pl / cost},
        {metric: 'avg', value: value / portfolioRows.length}
      ];
    }
  });

  calc('loans_total', {
    title: 'Laenujääk ja intressikulu',
    description:
      'Aktiivsete laenude jääk kokku, intress ja tasud kuus (järgmise makse intress maksegraafikutest pluss igakuised tasud), keskmine kulu jäägi suhtes ja liisingu jääkväärtus.',
    inputs: ['loans', 'loan_cost_total'],
    fn: (loanRows, loanCost) => {
      const act = loanRows.filter((r) => isActive(r.status) && r.balance !== null);
      const balance = d3.sum(act, (r) => +r.balance);
      const interest = +((loanCost.find((r) => r.metric === 'cost_month') || {}).value || 0);
      return [
        {metric: 'balance', value: balance},
        {metric: 'interest', value: interest},
        {metric: 'avg_rate', value: (interest * 12) / balance},
        {metric: 'balloon', value: d3.sum(act, (r) => +r.balloon || 0)}
      ];
    }
  });

  calc('assets_total', {
    title: 'Varad ja võlad kokku',
    description: 'Varade ja võlgade summa viimase uuenduse seisuga.',
    inputs: ['assets'],
    fn: (assetRows) => [
      {
        metric: 'assets',
        value: d3.sum(
          assetRows.filter((r) => r.side === 'asset' && r.value !== null),
          (r) => +r.value
        )
      },
      {
        metric: 'debts',
        value: d3.sum(
          assetRows.filter((r) => r.side === 'debt' && r.value !== null),
          (r) => +r.value
        )
      }
    ]
  });

  calc('goals', {
    title: 'Eesmärgid',
    description:
      'Eesmärgid reeglitest (goals): kuu tulemuse siht, puhver (esimene samm, siis üks kuu palk), netovara siht, krediitkaardi jääk, kallite laenude jääk ja reiside aasta eelarve.',
    inputs: ['months', 'investment_months', 'assets', 'loans', 'month_summary', 'transactions', 'trips', 'net_worth'],
    fn: (monthRows, ik, assetRows, loanRows, jk, tx, tripRows, nv) => {
      // goals come from rules.json (goals) via config.js
      const G = window.RAHAPADA.goals || {},
        GN = G.net_worth || {},
        GB = G.buffer || {};
      const nwNow = nv.length ? +nv[nv.length - 1].net : null,
        nwBase = +((nv.find((r) => r.month === GN.base_month) || {}).net ?? nwNow),
        NW_TARGET = GN.target ?? null;
      const card = +((assetRows.find((r) => r.item === G.card_item) || {}).value || 0);
      const Y = String(d3.max(tx, (r) => r.date)).slice(0, 4),
        TRAVEL_BUDGET = G.travel_budget ?? 0;
      // by the trip's year (trip end date), as in the trips table: a prepayment in the previous year goes to the trip's year
      const travel = (yy) =>
        d3.sum(
          tripRows.filter((r) => String(r.end).slice(0, 4) === yy),
          (r) => +r.cost
        );
      const tNow = travel(Y),
        tPrev = travel(String(+Y - 1));
      const io = outOf(ik);
      const net = (r) => +r.income - +r.expenses - +r.loans - io(r);
      const p4 = monthRows.filter((r) => r.month >= WIN[0] && r.month <= WIN[1]);
      const inc = d3.mean(p4, (r) => +r.income);
      const bufT = Math.round(inc / 10) * 10;
      const buf = +((assetRows.find((r) => r.item === GB.item) || {}).value || 0);
      const netNow = d3.mean(p4, net),
        T = G.month_net ?? 0;
      const fc = jk.find((r) => r.metric === 'forecast_end');
      const L = (n) => +((loanRows.find((r) => r.loan === n) || {}).balance || 0);
      const gap = Math.max(0, bufT - buf);
      return [
        {metric: 'net_target', value: T},
        {metric: 'net_now', value: netNow},
        {metric: 'net_gap', value: Math.max(0, T - netNow)},
        {metric: 'net_month', value: fc ? +fc.value : null},
        {metric: 'buf_target', value: bufT},
        {metric: 'buf_now', value: buf},
        {metric: 'buf_gap', value: gap},
        {metric: 'buf_months', value: Math.ceil(gap / T)},
        {metric: 'costly', value: d3.sum(G.costly_loans || [], L)},
        {metric: 'buf_step', value: GB.first_step ?? 0},
        {metric: 'buf_step_gap', value: Math.max(0, (GB.first_step ?? 0) - buf)},
        {metric: 'nw_now', value: nwNow},
        {metric: 'nw_target', value: NW_TARGET},
        {metric: 'nw_base', value: nwBase},
        {metric: 'nw_gap', value: nwNow === null || NW_TARGET === null ? null : Math.max(0, NW_TARGET - nwNow)},
        {metric: 'card_now', value: card},
        {metric: 'travel_budget', value: TRAVEL_BUDGET},
        {metric: 'travel_now', value: tNow},
        {metric: 'travel_left', value: TRAVEL_BUDGET - tNow},
        {metric: 'travel_prev', value: tPrev},
        {metric: 'travel_year', value: +Y}
      ];
    }
  });

  const cell = (el) => {
    const where = el.dataset.where.split('=');
    const d = dash.data(el.dataset.source);
    if (d.status !== 'ok') return {status: d.status};
    const row = d.data.find((r) => String(r[where[0]]) === where[1]);
    return {status: row ? 'ok' : 'missing', v: row ? Number(row[el.dataset.field]) : null};
  };
  for (const [name, fmt] of [
    ['metric', F.eur],
    ['signed', F.signed],
    ['pct', F.pct],
    ['pct1', F.pct1],
    ['pctsigned', F.pctsigned]
  ]) {
    draw(name, (el) => {
      const c = cell(el);
      el.classList.toggle('dash-skeleton', c.status === 'loading');
      el.textContent = c.status === 'ok' ? fmt(c.v) : '';
      el.classList.toggle('amtm', el.textContent === F.MASK);
      el.classList.toggle('neg', c.status === 'ok' && c.v < 0 && /\d/.test(el.textContent));
    });
  }
  // change vs previous year: arrow, change and comparison label
  draw('chg', (el) => {
    const d = dash.data(el.dataset.source);
    const r = d.status === 'ok' ? d.data.find((x) => x.metric === el.dataset.where.split('=')[1]) : null;
    if (!r || r.prev === null || r.prev === undefined) {
      el.textContent = '';
      return;
    }
    const now = +r.now,
      prev = +r.prev,
      df = now - prev,
      ch = prev ? df / Math.abs(prev) : 0;
    const same = Math.abs(ch) < 0.1,
      arr = same ? '≈ ' : df > 0 ? '▲ ' : '▼ ';
    const amt = isHidden() ? F.pctsigned(ch) : F.signed(df);
    el.textContent = arr + amt + ' ' + (el.dataset.vs || 'vs eelmine aasta');
    el.classList.toggle('ok', !same && df > 0);
    el.classList.toggle('bad', !same && df < 0);
  });
  for (const i of [0, 1, 2, 3, 4])
    dash.draw('sw' + i, (el) => {
      el.style.background = dash.colors[i];
    });
})();
