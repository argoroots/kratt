# Gruppide ja kategooriate ettepanek

Reeglid tehakse kasutaja enda kannetest. Mall (`templates/rules.json`) on tühi: ühtegi gruppi, kategooriat ega saajat seal pole.

## Kuidas

1. `python3 scripts/payees.py rahapada` → `rahapada/payees.json`. Iga saaja kohta: kandeid, välja, sisse, mitmel kuul, kas kuine, kontod, mõni kirjeldus.
2. Vaata saajaid suurimast alates ja lisa nii palju, et kategooriata jääks alla 5 % kulust. Väikesed ühekordsed saajad võivad jääda `Muu` alla.
3. Tee esialgne jaotus ise, ära küsi iga saaja kohta eraldi. Kasuta saaja nime, kirjeldust, summat ja sagedust. Kui saaja on ebaselge (inimese nimi, „Revolut**…“, üks suur makse), pane ta oma parima arvamuse järgi ja märgi ebaselgeks.
4. Kirjuta `rules.json`-i: `groups`, `group_order`, `payees` (või `keywords`, kui ühine sõna katab mitu saajat), `roles`, `settings.salary_categories`, `settings.trip_categories`, `settings.bank_fees`, `recurring`, `recurring_kinds`, `subscription_groups`, `loan_rules`, `internal`.
5. Arvuta (`build.py`) ja näita kasutajale **ühes tabelis**: grupp → kategooriad → suurimad saajad ja keskmine kuus. Eraldi lühike loetelu: ebaselged saajad (sinu arvamusega), mida pidasid oma kontode vaheliseks, mida laenuks, mida palgaks, mis on püsimaksed.
6. Küsi, mida muuta. Võimalda vabateksti (nt „Mari on mu tütar, pane tema ülekanded Pere alla“, „liida Toit ja Väljas söömine kokku“). Muuda, arvuta uuesti, näita muutunud osa. Korda, kuni kasutaja on rahul.

## Lihtsuse reeglid

- **Gruppe 6–9** (lisaks tuludele ja `Muu`-le). Nimi on igapäevane sõna, mida kasutaja ise kasutaks: Kodu, Toit, Transport, Ostlemine, Vaba aeg, Tervis, Lapsed, Tellimused, Laenud. Pane ainult grupid, mille kanded kasutajal on.
- **Kategooriaid grupis 1–4.** Kategooria nimi on „Grupp: alam“ (nt „Toit: toidupood“), siis läheb see grupi alla `prefixes` kaudu. Kui grupis on üks kategooria, on kategooria nimi sama mis grupp.
- Iga kanne peab ühe pilguga sobima ühte gruppi. Kui kaks gruppi kattuvad (nt „Ostlemine“ ja „Kodu: sisustus“), ütle reegel välja ja hoia seda.
- Ära tee kategooriat alla ~1 % kuludest, kui kasutaja seda ei palu: pane see grupi teise kategooriasse.
- Kategooriate nimed kasutaja keeles, ilma lühenditeta.
- Ühekordsed suured maksed (auto, remont, laenu ennetähtaegne tagastus) jäävad oma kategooriasse, aga `oneoff` alla, et need kuu tulemit ei moonutaks. Küsi, kui pole kindel.

## Rollid

Rollid ütlevad arvutusele, mis kategooria on (`reference/rules.md`):

- `income`: palk, toetused, muu korduv tulu. Palga kategooria ka `settings.salary_categories`.
- `oneoff_income`: ühekordne tulu (müük, pärand).
- `loan`: laenu- ja liisingumaksed; saaja → laen `loan_rules` alla, kui laene on mitu.
- `investment`, `pension`: aktsiad, fondid, III sammas. Tee neile üks grupp `labels.investments` nimega.
- `recurring`: kategooriad, kus on püsimakseid (kommunaal, side, kindlustus, tellimused, laenud, palk).
- Oma kontode vahelised ülekanded (ka teise panka, nt Revolut) ei ole kulu: IBAN `own_ibans` alla või tingimus `internal` alla. Küsi, kui pole kindel.

## Püsimaksed ja tellimused

`payees.json`-is on `monthly: true` saajatel makseid enamikus kuudes. Paku neist `recurring` read ja `recurring_kinds` (nt Kodu, Side, Kindlustus, Auto, Tellimus, Aastatasu). Tellimustele (`"subscription": true`) paku alamgrupid `subscription_groups` (nt Meedia, Tarkvara).
