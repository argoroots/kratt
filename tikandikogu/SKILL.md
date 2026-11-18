---
name: tikandikogu
description: Tikandimustrite kausta korrastamine masinale sobivaks koguks (kategooriad, ühtsed failinimed suurusega mm-des, variandid A/B/C, eelvaated, raami mittemahtuvate eemaldamine) ja kataloogi PDF.
---

# Tikandimustrite kogu korrastamine

## Masinad
Kogu tehakse ühele neist masinatest; raami suurus tuleb masinast:

| Masin | `--machine` | Fail | Suurim tikkimisala |
|---|---|---|---|
| Brother Innov-is V3 | `brother` | PES (teisendamisel nullpunkt ülal vasakul) | 300 × 180 mm |
| Janome Memory Craft 550E | `janome` | JEF + JBF | 200 × 360 mm |

Väiksema raamiga töötamiseks anna `--hoop 200x200`.

## 1. Küsi enne alustamist
- Lähtekaust (originaalid) ja sihtkaust. **Lähtekausta ei muudeta kunagi**: kõik tehakse koopiatena sihtkausta.
- **Mis masinale:** Brother Innov-is V3 või Janome Memory Craft 550E – küsi masina järgi, mitte failivormingu järgi. Alles jäävad selle masina failid (tabel ülal) ja välja jäetakse mustrid, mis ei mahu selle masina raami (või kasutaja öeldud väiksemasse raami). Mõlemale masinale = kaks eraldi kogu.
- Kategooriate struktuur (nt Loomad / Lilled / Muu ja nende alamkaustad). Kui kasutajal pole, paku välja pärast mustrite vaatamist.
- Kas vajadusel teisendada teised vormingud (DST, EXP …) masina vormingusse või jätta need välja.
- Kustutamine ja failide liigutamine kasutaja arvutis: küsi luba; kui pole, anna kasutajale käsk ise käivitamiseks.

## 2. Töövoog
1. **Inventuur:** `python3 scan.py <lähtekaust> --machine janome --sheets lehed/` → `inventory.json` (mõõdud pistete järgi, pisted, värvid, kas mahub raami, kaasfailid) ja kontaktlehed eelvaadetega.
2. **Vaata kontaktlehti** ja tee `plan.json`: iga faili kohta kategooria, nimi ja vajadusel variant. Samad mustrid eri suurustes saavad sama nime. Näita kasutajale kategooriaid ja nimesid (tabelina) ning oota kinnitust.
3. **Proovisõit:** `python3 apply.py <lähtekaust> <sihtkaust> plan.json --machine janome` – näitab kõiki toiminguid ja probleeme (ei mahu raami, sama nimi, teisendused). Näita kokkuvõtet kasutajale.
4. **Tegemine:** sama käsk `--go`-ga.
5. **Kataloog:** `python3 catalog.py <sihtkaust> --ext jef --subtitle "Janome Memory Craft 550E – raam 200 x 360 mm" --names names.json` (Brotheri puhul `--ext pes`).
6. **Kontrolli:** failide arv lähte- ja sihtkaustas (miinus raami mittemahtuvad), eelvaated avanevad, kataloogis on kõik kategooriad.

## 3. Reeglid
- **Failinimi:** `Nimi [A] 102` – suurus = pikem külg täis-mm-des, 3 kohta tühikuga täidetud (sorteerub õigesti ja loeb hästi), ilma „mm“-ita. Ilma täpitähtedeta (õ→o, ä→a, ü→u, š→s), ka kaustanimedes.
- **Variandid:** kui sama nime all on mitu erinevat mustrit, saavad need tähed A, B, C … (numbrita variant on A). Üksik muster (ka mitmes suuruses) jääb ilma täheta.
- **Suurus** mõõdetakse pistete järgi (mitte `extents()`, mis sisaldab hüppeid).
- **Raam:** mustrid, mis ei mahu valitud masina raami (kumbki suund), jäetakse välja ja loetletakse kasutajale.
- **Ainult masinafailid:** masina vorming + kaasfailid (nt JEF + JBF) + eelvaade (BMP). Muud (PDF, JPG, DST …) mitte.
- **Sisu ei muudeta:** sama vormingu fail kopeeritakse baithaaval; teisendus ainult kasutaja loal ja märgitakse aruandes.
- **Eelvaade:** 400 × 400 BMP, helehall taust (236, 236, 236), niidi värvides joon, katkeb hüpete juures.
- **Kataloog (A4):** pealkiri, alapealkiri (masin, raam), üks kord märge „suurused mm-des“; kategooriad pealkirjadena; 4 mustrit reas: ümarate nurkadega eelvaade, nimi **täpitähtedega** (`names.json`), suurused kuni 5 reas, rea kõrgus vastavalt suuruste arvule; ühtlased servad.
- Kui nimes on keel peale eesti (inglise, vene), tõlgi nimi eesti keelde ja kontrolli kasutajaga.

## Skriptid (`scripts/`)
`pip install --break-system-packages pyembroidery pillow reportlab`

| Fail | Mida teeb |
|---|---|
| `scan.py` | inventuur ja kontaktlehed (ainult loeb) |
| `apply.py` | plaani järgi sihtkausta: nimed, variandid, raami filter, kaasfailid, eelvaated; ilma `--go`-ta proovisõit |
| `catalog.py` | kataloogi PDF |
| `common.py` | ühised funktsioonid (nimed, mõõdud, eelvaade) |
