# Reeglid (rules.json)

Algversioon: `templates/rules.json`. Võtmed on inglise keeles, väärtused (kategooriad, grupid, saajad) kasutaja keeles. Kategooria nimi kujul „Grupp: alam“ (nt „Toit: toidupoed“) läheb grupi alla `prefixes` kaudu. Muuda faili Edit-tööriistaga ja kontrolli, et see jääb kehtivaks JSON-iks (`python3 -m json.tool rules.json`).

## settings

| Võti | Mis |
|---|---|
| `data_start` | varasemaid kandeid ei arvestata (`"2025-01-01"`) |
| `timezone` | kaardimaksete aja parandus (`"Europe/Tallinn"`); puudumisel UTC |
| `window_months` | mitme viimase täiskuu järgi on „tavaline kuu“ ja prognoos |
| `recurring_min_months` | püsimakse: sama saaja ja kategooria vähemalt nii mitmel aknakuul |
| `salary_categories` | palga kategooriad; palgapäev nihutab kuu prognoosi |
| `payday` | palgapäev (kuupäev); `null` = tavaline palga päev andmetest. Nädalavahetusel ja pühal eelmine tööpäev |
| `card_account` | krediitkaardi konto nimi (`accounts` all) |
| `pair_internal` | kontod, mille vahel ülekannetel pole vastaspoole IBAN-i (nt krediitkaart ja arveldus) |
| `trip_categories` | reiside kategooriad |
| `bank_fees` | `{payee, categories}` – panga tasud ühe saaja alla |
| `holidays` | riigipühad: `{"dates": ["01-01", "12-24"], "easter_days": [-2, 0, 49]}` (kuupäevad ja päevad lihavõttepühast); puudumisel ainult nädalavahetused |
| `labels` | kohustuslik: nimed, mida skriptid ja leht ise kasutavad (vt allpool) |
| `leasing_kinds` | laenufailide `kind` väärtused, mis on liising (säästumäärasse ei lähe) |
| `subscription_groups` | tellimuste tabeli alamgruppide järjekord (`recurring[].sub`) |
| `investment_rows` | aktsiakonto read kannete tabelis: `{stocks, dividends, funds, fund_description, fees}` kategooriad |
| `icons` | ikoonid sektori ja riigi nime ees: `{"Tehnoloogia": "💻", "Eesti": "🇪🇪"}` |

`labels` (kõik kohustuslikud):

| Võti | Mis | Näide |
|---|---|---|
| `income` | tulude grupp | `"Tulud"` |
| `expenses` | kulud kategooriate tabelis | `"Kulud"` |
| `loans` | laenude grupp | `"Laenud"` |
| `investments` | investeeringute grupp | `"Investeeringud"` |
| `other` | kategooriata kanded ja muu grupp | `"Muu"` |
| `internal` | oma kontode vaheline kategooria | `"Oma kontode vahel"` |
| `unassigned_trip` | reisi nime algus kandel, mis pole ühegi reisi all | `"Määramata"` |
| `loan_section` | laenude rida püsikulude ja varade tabelis | `"Laenud ja liising"` |

## accounts, own_ibans

`accounts`: `[{"name": "Arveldus", "iban": "EE…"}, {"name": "Hoius", "iban": "EE…", "track_only": true}]`. Ülekanded oma kontode vahel ei ole tulu ega kulu. `track_only`: konto ainult jäägi jaoks (nt hoius), kanded ei lähe tuludesse ega kuludesse. `own_ibans`: muud oma kontod (nt teises pangas, mida ei impordita).

## names

Saaja nime ilu: `strip_prefix` (regulaaravaldis, mis eemaldatakse algusest), `spelled` (`{"NOMME": "Nõmme"}`), `keep_upper` (lühendid, mis jäävad suurtähtedega). `rewrite`: kannete tabelis saaja nime asendused enne numbrite eemaldamist, `[{"match": "^(?i:BOLT\\.EU)[/_]?D[/_]?\\d.*$", "name": "Bolt Food"}]` (regulaaravaldis, `name` võib sisaldada `\\1`).

## Kategooria leidmine

Esimene sobiv võidab:

1. `internal` – lisaks oma kontodele sisekanded (tingimused), nt `{"description_starts": "Konverteerimine (", "note": "valuutavahetus oma rahaga"}`;
2. `exceptions` – üks kanne või kitsas juhtum: tingimused + `category`, `note`. Nt `{"id": "1234567890", "category": "Kingitused ja lilled", "note": "sünnipäevakink"}`;
3. `payee_rules` – saaja, kelle kanded jagunevad: `{"payee": "Maksu- ja Tolliamet", "category": "Riigilõivud ja maksud", "rules": [{"sign": "+", "category": "Toetused ja tagastused"}]}` – esimene sobiv reegel, muidu saaja `category`;
4. `payees` – `{"name", "match", "category"}`: `match` on regulaaravaldis saaja nimel SUURTÄHTEDES (või loend), `bank_names` täpsed nimed pangast;
5. `keywords` – `{"category", "words": [...]}` sõnad saaja nimes või kirjelduses;
6. muidu `labels.other` (kategooriata).

Siis:

- `lunch` (valikuline): `{"from_category": "Väljas söömine", "category": "Toit: lõuna", "from_hour": 11, "to_hour": 14, "places": ["TALLINN"]}` – väljas söömine tööpäeval lõuna ajal antud kohtades;
- `oneoff`: tingimused – ühekordsed, ei lähe kuu tulemisse ega prognoosi (näidatakse eraldi tabelis);
- `loans[].insurance`: laenumaksesse peidetud kindlustus eraldi kategooriasse (vt allpool).

## Tingimused

Kõik peavad kehtima; loend = ükskõik milline.

`id`, `payee`, `payee_not`, `account`, `counterparty_is` / `_contains` / `_starts` / `_account`, `description_is` / `_contains` / `_not_contains` / `_starts`, `text_contains` / `_contains_all` / `_not_contains` / `_nospace_contains`, `amount`, `amount_min`, `amount_max`, `sign` (`"+"`/`"-"`), `date` (päev või kuu), `date_from`, `date_before`, `day`, `description_day_max`, `description_day_over`, `category_is`, `category_starts`, `category_not`, `sub_is`, `sub_not`.

Reegel, mis ei tohi muuta möödunud kuid: lisa `date_from`.

## groups, group_order, roles

`groups`: `[{"name": "Toit", "prefixes": ["Toit"], "categories": ["Väljas söömine"]}]` – kategooria läheb esimesse gruppi, mille `categories` seda sisaldab või `prefixes`'iga algab; muidu „Muu“. `group_order`: gruppide järjekord.

`roles` – kuidas kategooria arvesse läheb (`{"categories": [...], "prefixes": [...]}`): `income`, `oneoff_income`, `internal`, `loan`, `investment`, `pension`, `recurring`.

## recurring, not_recurring

`recurring`: püsikulude tabeli read `{"name", "kind", "transactions": [tingimused], "yearly": true?, "ended": true?, "sub"?}`, nt `{"name": "Netflix", "kind": "Tellimus", "sub": "Meedia", "transactions": [{"payee": "Netflix"}]}`.

`recurring_kinds`: mis `kind` läheb püsikulude tabelis millisesse ossa, järjekorras: `[{"kind": "Kodu", "section": "Kodu"}, {"kind": "Tellimus", "section": "Tellimused", "subscription": true, "latest_price": true}]`. `subscription`: rida on ka tellimuste tabelis (alamgrupp `sub`). `latest_price`: summa on viimane makse (hinnatõus näha), muidu viimase aasta mediaan. Loendis puuduva `kind`-iga read püsikulude tabelisse ei lähe. `not_recurring`: kanded, mis pole püsimaksed, kuigi kategooria on `recurring` rollis.

## loan_rules, loans

`loan_rules`: millised kanded millise laenu alla – `{"category_is": "Laen: kodulaen", "loan": "Kodulaen"}`. Laenude andmed ja graafikud: hoidla `loans/<nimi>.json` (`reference/store.md`).

`loans` (reeglites): laenumaksesse peidetud kindlustus –
`{"name": "Autoliising", "category": "Auto: liising", "schedule": [{"month": "2026-06", "payment": 450.0, "insurance": 40.0}], "insurance": {"category": "Auto: kindlustus", "suffix": " (kasko)", "schedule_from": "2026-06"}}`.

## worth – vara ja võlad

```json
{"items": [
  {"name": "Aktsiad", "side": "asset", "source": "portfolio"},
  {"name": "III sammas", "side": "asset", "source": "funds", "funds": ["FOND1"]},
  {"name": "Hoius", "side": "asset", "source": "deposit"},
  {"name": "Kontodel", "side": "asset", "source": "accounts"},
  {"name": "Kodulaen", "side": "debt", "source": "loan", "loan": "Kodulaen"},
  {"name": "Krediitkaart", "side": "debt", "source": "card"},
  {"name": "Maja", "side": "asset", "source": "manual", "value": 150000}],
 "cash_accounts": ["Arveldus"], "deposit_account": "Hoius", "cash_item": "Kontodel", "card_item": "Krediitkaart",
 "cars": [{"name": "Auto", "from": "2024-01", "value": 15000}]}
```

`side`: `asset` või `debt`. `source`: `portfolio`, `funds`, `deposit`, `accounts`, `loan`, `card`, `manual` (`value`).

## forecast – 24 kuu rahavoog

```json
{"months": 24, "invest_per_month": 200, "trips_per_year": 2000, "trips_split": {"06": 0.5, "07": 0.5},
 "tax_rate": 0.22, "refund_month": 4,
 "leasing": {"loan": "Autoliising", "margin": 2.0, "euribor_now": 2.2, "euribor_new": 2.5, "change_from": "2027-06"},
 "pension": {"born": "1985-01", "pension_age": 65, "return": 0.05, "contribution_month": 100,
             "pillar3_items": ["III sammas"], "fund_items": [], "pillar3_funds": ["FOND1"], "other_funds": []}}
```

`invest_per_month: null` = aknakuude keskmine. `trips_split`: mis kuudel reisiraha kulub. `tax_rate` ja `refund_month`: tulumaksu tagastus III sambast. `leasing`: Euriboriga laenu intressi muutus.

## trips

`[{"name": "Rooma", "from": "2026-05-10", "to": "2026-05-15"}]` – kanded reisikategooriates nende kuupäevade vahel lähevad selle reisi alla. `transactions` (tingimused) piirab kandeid, `start` on reisi algus, kui ettemaks oli varem.

## goals – eesmärgid

```json
{"month_net": 300, "buffer": {"item": "Hoius", "first_step": 1000}, "net_worth": {"target": 0, "base_month": "2026-11"},
 "card_item": "Krediitkaart", "costly_loans": ["Väikelaen"], "travel_budget": 2000}
```

Puhver: esimene samm, siis üks kuu palk. Eesmärk, mida pole, on lehel peidus. Eesmärgid ütleb kasutaja – ära pane neid ise.
