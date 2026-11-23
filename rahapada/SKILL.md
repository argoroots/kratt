---
name: rahapada
description: Rahaasjade töölaud pangakannetest Claude'i Data töölaual – kuu prognoos, kategooriad, püsikulud, investeeringud ja pension, laenud, vara ja netovara, 24 kuu rahavoog, eesmärgid. Kasuta, kui kasutaja tahab teha oma rahaasjade või eelarve töölauda, seda uuendada („uuenda“), pangakandeid kategoriseerida või reegleid muuta.
---

# Rahapada

Teeb kasutaja pangakannetest rahaasjade töölaua (Claude'i artefakt, tüüp **Data**) ja hoiab seda ajakohasena. Kanded tulevad panga ühendusest (MCP), kui see on Claude'is olemas, või väljavõtte failist (camt.053 XML või CSV). Kogu ajalugu (reeglid, kanded, investeeringud, laenud) on teises privaatses artefaktis – **hoidlas** –, ja iga uuendus arvutab kõik selle pealt uuesti.

Vasta kasutaja keeles. **Ära eelda midagi:** kui miski pole selge (konto, kategooria, laen, kas kanne on ühekordne), küsi. Paku ise välja, aga ära otsusta kasutaja eest. Sa ei ole finantsnõustaja: näita numbreid ja arvutusi, ära anna investeerimis- ega laenusoovitusi.

Pangas tee ainult lugemist. Ühtegi makset, korraldust ega muud muudatust pangas ei tee.

## Failid

- `scripts/build.py` – kategoriseerib kanded ja arvutab kõik andmestikud, `config.js`, `report.json`.
- `scripts/import_statement.py` – väljavõte (camt.053/052 XML, CSV) → kanded JSON-is.
- `scripts/lhv_statement.py` – LHV ühenduse väljavõtted → kanded, investeerimiskonto, hoius ja jäägid.
- `scripts/merge_tx.py` – lisab kanded hoidla kuu failidesse.
- `scripts/dataset_docs.py` – teeb andmestike dokumendid (`db_write` ops) üles laaditud failide URL-idest.
- `scripts/chunks.py` – jagab suure lehe faili osadeks andmebaasi kirjutamiseks.
- `scripts/payees.py` – kasutaja saajad kokkuvõttena (summad, sagedus, kirjeldused) gruppide ja kategooriate ettepanekuks.
- `templates/rules.json` – reeglite tühi algversioon (seaded ja nimed, gruppe ega kategooriaid pole).
- `reference/categories.md` – kuidas pakkuda kasutaja andmete järgi lihtsad grupid ja kategooriad. **Loe enne reeglite tegemist.**
- `reference/rules.md` – reeglite kõik võtmed, tingimused ja näited.
- `templates/page/index.html`, `calc.js`, `draw.js` – töölaua leht.
- `templates/datasets.json` – andmestike pealkirjad ja kirjeldused.
- `templates/store_index.html` – hoidla leht.
- `reference/store.md` – hoidla ja failide kuju, kannete väljad, arvutus. **Loe enne esimest tööd.**

Skriptid vajavad ainult Pythonit (lisapakette pole). Kõik andmed on JSON. Töökaust: `rahapada` oma töökaustas (`pwd`), **mitte** `/tmp` all.

## Esimene kord

1. **Küsi** (AskUserQuestion, mitu korraga):
   - millised pangad ja kontod (arveldus, krediitkaart, hoius, investeerimiskonto); millistel on Claude'is panga ühendus (vaata oma tööriistu, nt LHV: `list_accounts`, `get_account_statement`, `get_balances`, `get_account_executions`, `get_account_instrument_balances`, `get_credit_contracts`). Teiste kohta palu väljavõte: camt.053 XML (soovitatav) või CSV;
   - **mis aastate kanded importida** – paku jooksvat ja eelmist aastat (nt 2025 ja 2026). Prognoosiks on vaja vähemalt 3 täiskuud. Töölaual saab aastaid nuppudega sisse ja välja lülitada;
   - mis osad: investeeringud ja pension, laenud ja liising, vara ja netovara, rahavoog, reisid, eesmärgid. Mida ei taheta, see jääb tühjaks ja lehel peitu.
2. **Reeglid:** kopeeri `templates/rules.json` → `rahapada/rules.json` (võtmed: `reference/rules.md`). Täida `accounts` (nimi, IBAN; hoius `"track_only": true`), `own_ibans`, `settings.data_start` (valitud esimese aasta 1. jaanuar), `settings.card_account`, `pair_internal`. Kui kasutaja ei tea mõnda väärtust, jäta tühjaks – ära pane oma numbreid. Gruppe, kategooriaid ega saajaid mallis pole: need tulevad sammus 6. Mall on Eesti jaoks (`timezone`, riigipühad `holidays`, nimed `labels`): kui kasutaja elab mujal, küsi ja muuda.
3. **Kanded:** iga kuu kohta fail `tx/<YYYY-MM>.json` (kirjendamise kuu, kõik kontod; väljad `reference/store.md`).
   - LHV ühendus: `get_account_statement` iga konto kohta terve aasta kaupa (`limit: 10000`, `includeBalances: true`; jooksval aastal ka `includeReservations: true`). Suur vastus ei tule vestlusesse: tööriist salvestab selle faili ja ütleb tee. Ära loe faili – anna see skriptile: `python3 scripts/lhv_statement.py rahapada --account NIMI FAIL… --balances` (arvelduskonto ja krediitkaart; investeerimiskonto `--as invest`; hoius `--as deposit --symbol SÜMBOL`). Väikese vastuse, mis tuleb vestlusesse, kirjuta faili (Write) muutmata kujul ja anna samuti skriptile.
   - Muu panga ühendus: kirjuta read väljadega nagu `reference/store.md` faili `new.json` ja `python3 scripts/merge_tx.py new.json rahapada/tx`.
   - Väljavõte: `python3 scripts/import_statement.py FAIL --account NIMI --tx rahapada/tx` (mitme kontoga failil `--iban`; CSV veergude puudumisel `--map`).
   Mõlemad jagavad read kuu failideks; sama `id` asendab vana rea.
4. **Valikulised failid** (ainult valitud osad, kuju `reference/store.md`): `balances.json`, investeeringud (`invest/*`, `prices.json`), laenud (`loans/<nimi>.json` – andmed ja maksegraafik pangast või lepingust; ära arvuta graafikut ise), `rules.json` `worth`, `forecast`, `trips`, `goals`. Küsi puuduvat; eesmärgid ja pensioniiga ütleb kasutaja.
5. **Saajad:** `python3 <skill>/scripts/payees.py rahapada` – kõik saajad suurimast alates (`rahapada/payees.json`).
6. **Grupid ja kategooriad** (`reference/categories.md`):
   - tee ise esialgne jaotus kasutaja saajate järgi: 6–9 lihtsat gruppi, igas 1–4 kategooriat; palk, oma kontode vahelised ülekanded, laenud, investeeringud, püsimaksed ja tellimused; kirjuta kõik `rules.json`-i;
   - arvuta: `python3 <skill>/scripts/build.py rahapada --today YYYY-MM-DD`;
   - näita kasutajale üht tabelit (grupp → kategooriad → suurimad saajad, keskmine kuus) ja eraldi ebaselged saajad koos oma arvamusega;
   - **küsi, mida muuta** (grupid, nimed, kuhu mõni saaja läheb, mis on ühekordne, mis on oma ülekanne). Muuda, arvuta uuesti, näita muutunut. Korda, kuni kasutaja on rahul;
   - järgmistel kordadel uued kategooriata saajad: paku igale kategooria olemasolevate seast ja küsi koos (AskUserQuestion, kuni 4 küsimust korraga). Lisa `payees` (saaja kõik kanded), `payee_rules` (saaja kanded jagunevad) või `exceptions` (üks kanne) alla.
7. **Hoidla:** `publish_files` ilma slug-ita, pealkiri „Rahapada hoidla“: `index.html` (`templates/store_index.html`), `rules.json`, `tx/*.json`, valikulised failid, `card_times.json` ja `state.json` `out/`-ist. Hoidla slug läheb töölaua `config.js`-i (`--store`).
8. **Töölaud:** `list_types` → tüüp **Data** → `create_from_type` (pealkiri nt „Rahaasjad“). Järgi tüübi juhist:
   - arvuta uuesti hoidla slug-iga: `build.py rahapada --today … --store <hoidla slug>` (slug läheb `config.js`-i);
   - lae üles mittetühjad `out/datasets/*.json` ja üks fail `empty.json` sisuga `[]` (`upload_asset`, kuni 10 korraga); kirjuta URL-id faili `urls.json` (`{"months.json": "/_blob/…", …}`) ja `python3 scripts/dataset_docs.py rahapada urls.json` annab kõigi `datasets/<id>` dokumentide `db_write` ops (pealkiri ja kirjeldus `templates/datasets.json`-ist, `fixed: true`, `updated`);
   - lehe failid `files/config.js` (= `out/config.js`), `files/calc.js`, `files/draw.js`, `files/index.html` = `templates/page/` muutmata. Ühe kirjutuse piir on umbes 64 KB. Suur fail (`draw.js`, `index.html`): `python3 scripts/chunks.py FAIL` → `db_write set files/<nimi> {text: "@@RAHAPADA_REST@@"}`, siis iga osa kohta `db_str_replace` (old_str = märk, new_str = osa + märk; viimasel osal ilma märgita). `db_str_replace` võtab teksti nii nagu on, JSON-escape'i pole vaja;
   - `dash/meta`: `{title, lang: "et"}`;
   - `files/index.html` kirjuta viimasena: see käivitab kontrolli;
   - loe tüübi `check` ja `runs` ning paranda vead.
9. **Ütle kasutajale:** mitu kuud on sees, kuu prognoos, mis jäi teadmata ja et mõlemad artefaktid on privaatsed (hoidlat ära jaga).

## Uuendamine („uuenda“)

1. **Hoidla töökausta:** hoidla slug on töölaua `files/config.js`-is (`db_get files/config.js` → `"store"`); `list_files` → `read_file(slug, paths=[…])` kõik failid (32 korraga) → kopeeri igaüks oma teele.
2. **Kanded:** jooksev kuu kõigilt kontodelt; kui eelmine kuu pole lõpuni sees, ka see (`lhv_statement.py` / `merge_tx.py` / `import_statement.py --tx`). Võta alati ka praegused broneeringud: skript eemaldab nende kontode vanad ootel read. Ühenduseta pankade kohta küsi uut väljavõtet või ütle, et need kontod jäävad seekord vanaks.
3. **Investeeringud:** tehingud, investeerimiskonto, positsioonid, jooksva kuu hinnad `prices.json`-i (fondide osaku hind fondivalitseja avalikust hinnaallikast, kui fondid on), jäägid `balances.json`-i.
4. **Arvuta** `build.py … --store <hoidla slug>`. Kategooriata kanded: paku olemasolevate kategooriate seast ja küsi (nagu esimese korra 6. sammu lõpus). Uut gruppi ära tee ilma kasutaja nõusolekuta.
5. **Avalda:**
   - hoidlasse muutunud failid (`publish_files`, patch, `base_version` = `list_files` versioon): uued/muutunud `tx/*.json`, `card_times.json`, `state.json`, muutunud reeglid ja muud failid;
   - töölauale `out/report.json` → `changed_datasets`: lae üles ja `dataset_docs.py rahapada urls.json --op update --only <id> …` (lisa igale op-ile `ifVersion` `db_list datasets` järgi); `files/config.js` iga kord (`update`).
6. **Kokkuvõte:** lühidalt uued kanded (ootel eraldi), investeeringute muutus ja kuu prognoos. Kui kasutaja on öelnud, millist kokkuvõtet ta tahab, tee see nii.

## Reeglite muutmine

Kui kasutaja ütleb, et kanne on mujal (nt „see poeost oli kink“), küsi vajadusel, kas see kehtib saaja kõigile kannetele (`payees`) või ainult sellele (`exceptions`). Kõik kuud arvutatakse uuesti, nii et muudatus mõjub ka möödunud kuudele: kui see võib muuta möödunud kuid, **küsi kasutajalt**, kas need muuta. Ei → lisa reeglile `"date_from": "<jooksev kuu>"`. Siis arvuta, avalda hoidlasse `rules.json` ja töölauale muutunud andmestikud.

## Leht

- Lehte ei muuda ilma kasutaja palveta. Plaani ja reeglite teksti (Vara ja eesmärgid) muudab kasutaja ise pliiatsiga või palub sind – siis muuda ainult seda teksti `files/index.html`-is.
- Pealkirja muutmiseks muuda ainult `<h1>`.
- Aastad, perioodid ja tühjad osad tulevad `config.js`-ist – uue aasta jaoks lehte muuta ei ole vaja.

## Reeglid

- Pangaandmed lähevad ainult kasutaja enda kahte artefakti. Ära pane neid kuhugi mujale.
- Numbrid tulevad skriptidest. Ära arvuta summasid peast ega kirjuta numbreid lehele käsitsi.
- Hoidla faile ära loe konteksti (`read_file` ilma `paths`-ita, `read_asset`) – ainult kettale.
