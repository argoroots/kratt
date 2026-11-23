# Hoidla, failid ja andmestikud

## Kaks artefakti

- **Töölaud** – Claude'i artefakt tüübist **Data**. Andmestikud (`datasets/<id>`, fail `out/datasets/<id>.json` assetina) ja lehe failid (`files/index.html`, `files/calc.js`, `files/draw.js`, `files/config.js`).
- **Hoidla** – tavaline artefakt (mitte tüübist), pealkiri „Rahapada hoidla“. Kogu ajalugu, mida pangast uuesti ei saa või mida on mõttekas mitte uuesti küsida: reeglid, kanded, investeeringud, laenud. Leht `index.html` on lihtne selgitus (`templates/store_index.html`).

Hoidla faile ei loeta konteksti. Allalaadimine: `read_file(slug, paths=[…])` (kuni 32 faili korraga) salvestab need kettale; vastuse kokkuvõttes on failid samas järjekorras – kopeeri iga salvestatud fail töökausta oma teele (`cp`). Üleslaadimine: `publish_files` (patch, `base_version` = viimane versioon), `as` = tee hoidlas, `path` = fail töökaustas. Kõik hoidla andmefailid on JSON.

Töökaust: `rahapada` oma töökaustas (`pwd`), **mitte** `/tmp` all (sealt ei saa üles laadida). Töökaust on hoidla koopia + `out/`.

## Hoidla failid

```
index.html                 selgitus
rules.json                 reeglid (reference/rules.md, algversioon templates/rules.json)
card_times.json            kaardimaksete broneeringu ajad (build.py kirjutab out/card_times.json)
state.json                 andmestike räsid (build.py kirjutab out/state.json)
tx/<YYYY-MM>.json          kanded kuu kaupa, kõik kontod (kuu = kirjendamise kuu)
balances.json              kontode jäägid kuu alguses ja lõpus (valikuline)
prices.json                hinnad kuu lõpus (valikuline)
invest/trades.json         aktsiatehingud (valikuline)
invest/account.json        investeerimiskonto rahaliikumised (valikuline)
invest/portfolio.json      praegused positsioonid (valikuline)
invest/instruments.json    instrumentide andmed, indeksid, dividendid (valikuline)
invest/funds.json          pensionifondid (valikuline)
invest/deposit.json        hoius (valikuline)
loans/<nimi>.json          laenu või liisingu andmed ja graafik (valikuline)
events.json                suured sündmused (valikuline)
logos.json                 instrumentide logod (valikuline)
```

## Kanne (tx/*.json)

JSON-massiiv. Sama `id` mitmes failis on üks kanne (viimane jääb).

| Väli | Mis |
|---|---|
| `id` | panga viide (unikaalne; broneeringul broneeringu viide) |
| `account` | konto nimi nagu `rules.json` `accounts` all |
| `booked` | kirjendamise päev `YYYY-MM-DD` (ootel kandel tühi) |
| `date` | ostu päev, kui see erineb (`import_statement.py` paneb); muidu ära pane |
| `amount` | summa märgiga (välja −, sisse +) |
| `currency` | `EUR` |
| `counterparty` | saaja või maksja nimi; kaardimaksel võib olla tühi |
| `counterparty_account` | saaja/maksja IBAN või `""` |
| `description` | selgitus |
| `card` | kaardimakse (`true`/`false`) |
| `pending` | ootel kaardimakse (broneering) |
| `reserved_at` | broneeringu aeg ISO kujul (`2026-11-21T11:36:02Z`), kui pank annab |

LHV ühendusest teeb read `scripts/lhv_statement.py` (`get_account_statement` tulemuse failist): `bankReference` → `id` (sama viitega teine rida saab lõpu `:2`); `settlementDtime` → `booked`; `paymentData` vastaspool (väljaminekul `creditor`, sissetulekul `debtor`) → `counterparty`, `counterparty_account`; selgitus → `description` muutmata (kaardimaksel `(..1234) 2026-11-21 13:36 KAUPMEES\…`, skript võtab sealt ostu päeva ja kaupmehe); `card: true` kaardimaksel. Broneeringud (`reservations`): `id` broneeringu viide, `pending: true`, `reserved_at` = `reservationDtime`.

Ootel kanne jäetakse välja, kui sama konto, summa ja kirjelduse algusega kirjendatud kanne on olemas. Broneeringu aeg jääb `card_times.json`-i, sest kirjendatud kaardimaksel on aeg vahel makseteenuse ajavööndis.

## Investeeringud (valikuline)

- `invest/trades.json`: `[{executedAt, symbol, instrumentName, currency, actionType: BUY|SELL, quantity, price}]` (LHV `get_account_executions`).
- `invest/account.json`: `[{time, description, amount, currency, counterparty, kind?, symbol?}]` (investeerimiskonto väljavõte). `kind`: buy, sell, fee, dividend, tax, interest, account_interest, paid_interest, conversion, fund, other; puudumisel loetakse LHV selgitustest.
- `invest/portfolio.json`: `[{symbol, qty, value, pl, cost}]` eurodes (LHV `get_account_instrument_balances`).
- `invest/instruments.json`: `{instruments: {SYMBOL: {name, country, sector, region, aliases}}, trade_fx: {YYYY-MM: kurss}, indices: [{name, source}], dividends_declared: [{symbol, date, per_share}]}`. Riik ja valdkond küsi kasutajalt või võta avalikust allikast; ära arva.
- `invest/funds.json`: `{funds: [{code, name, isin, start_units}], tx: [{fund, date, units, price}], account_fund_payee}`. `start_units` = osakud enne esimest `tx` rida; `tx` = osakute ostud fondi väljavõttest (Pensionikeskus, fondi koduleht). Kui väljavõtet pole, on osakud makse summa / NAV makse päeval – ütle kasutajale, et see on hinnang. `isin` on hinna päringuks; `account_fund_payee` = investeerimiskonto saaja nime algus, kui fondi makse läheb sealt.
- `invest/deposit.json`: `{name, symbol, rows: [{time, description, amount}]}`.
- `prices.json`: `[{month, source, symbol, price, date}]`, `source`: `stocks`, `funds` (code), `indices` (indeksi nimi), `fx` (`EURUSD`). Iga kuu kohta viimane teadaolev hind; jooksva kuu rida asendatakse igal uuendusel, möödunud kuude read jäävad. Eesti pensionifondi osaku hind: `https://onboarding-service.tuleva.ee/v1/funds/<ISIN>/nav` (viimane kirje).

## Laenud (valikuline)

`loans/<nimi>.json`, üks laen faili kohta (`ended.json` võib sisaldada `{"loans": [...]}` lõppenud laenudega):

`name, family, kind, monthly, status (active/ended), note, balance, rate, apr, end, balloon, amount, start, n, interest_total, fees, total, fee_month, oneoff_fees [{year, amount}], contract [{name, value}], schedule [{month, balance, payment?, interest?, insurance?}]`.

Maksegraafik (`schedule`) tuleb pangast või lepingust – ära arvuta seda ise. Euriboriga laenul uuenda graafikut, kui pank selle muudab; prognoosi intressimuutus on `rules.json` `forecast.leasing` all. Millised kanded on laenumaksed: `rules.json` `loan_rules`.

## Muu (valikuline)

- `balances.json`: `[{month, account, currency, start, end}]` – konto jääk kuu alguses ja lõpus (LHV `get_balances` või väljavõte). Vajalik netovarale.
- `events.json`: `[{id, date: YYYY-MM, title, text, amount}]` – ainult kasutaja öeldud sündmused.
- `logos.json`: `[{symbol, img}]` – instrumentide logod (pildi URL) tootluse tabelis.

## Kategooria leidmine (esimene sobiv võidab)

1. oma kontode vaheline ülekanne (`accounts`, `own_ibans`, `internal`) – ei ole tulu ega kulu;
2. `exceptions`;
3. `payee_rules` (saaja kanded jagunevad tingimuste järgi);
4. `payees` (saaja nimi `match` järgi, kategooria);
5. `keywords`;
6. muidu „Muu“ ja kategooriata.

Siis: lõuna reegel (`lunch`), ühekordsed (`oneoff`), laenumaksesse peidetud kindlustus (`loans[].insurance`). Grupp tuleb `groups` alt, arvestus `roles` alt.

## Arvutus

`build.py` arvutab iga kord kõik kogu ajaloo pealt. Reegli muudatus kehtib kõigile kuudele; kui see ei tohi möödunud kuid muuta, lisa reeglile `date_from`.

- **Kuu prognoos:** viimase `window_months` täiskuu põhjal; muutuv kulu ülejäänud päevadeks samast kuu osast, palgapäevaga joondatud. Vahemik: aknakuude kaupa.
- **Püsimaksed:** `roles.recurring` kategooriad, mis on aknakuudest vähemalt `recurring_min_months` kuul.
- **Rahavoog:** tulud, püsikulud, muutuv kulu aknakuude keskmisest, laenugraafikud, reisid (`trips_per_year`, `trips_split`), investeeringud, III samba tulumaksu tagastus, Euribori muutus.

`out/config.js` (periodid, eesmärgid, tühjad andmestikud) läheb töölauale `files/config.js`. Tühja andmestikuga osad on lehel peidus.

## Andmestikud

Pealkirjad ja kirjeldused: `templates/datasets.json`. Kõik 34 andmestikku tehakse alati (tühi = `[]`). Kulud on andmestikes positiivsed, kannetes märgiga.
