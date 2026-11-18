---
name: tikkimisfail
description: Vektorpildi (SVG) muutmine tikkimisfailiks valitud masinale (Brother PES, Janome JEF) mitmes suuruses, koos kontrolli, 1:1 PDF-spetsifikatsiooni, piltide ja soovi korral animatsiooniga.
---

# Tikkimisfaili loomine vektorpildist

Reeglid ja nende põhjused (kangas, tihedus, alustikk, suund, nurgad) on failis `TEADMISED.md`. Loe see enne digiteerimist läbi.

## Masinad

| Masin | Fail | Suurim tikkimisala |
|---|---|---|
| Brother Innov-is V3 | PES (v10 töötava faili päisega, nullpunkt ülal vasakul) | 300 × 180 mm |
| Janome Memory Craft 550E | JEF (+ BMP eelvaade, keskpunktiga) | 200 × 360 mm |

## 1. Küsi enne alustamist
- **Masin:** Brother Innov-is V3, Janome Memory Craft 550E või mõlemad. Küsi masina, mitte faili järgi: vorming tuleb masinast.
- **Suurused** (pikem külg mm). Iga suurus peab mahtuma valitud masina raami (`gen.py` hoiatab).
- **Kangas:** linane, puuvill, teksas, kanvas, trikoo, fliis, frotee, nahk, vinüül (`--fabric`, vt `TEADMISED.md` jaotis 8). Kui see pole teada, küsi; ära oleta.
- **Variandid** (nt ilma tekstita) on eraldi SVG-d. Küsi, kas variant peab olema samas mõõtkavas kui terve pilt (vt 2).
- Töötav fail samale masinale (sellega võrdled), failide ja niitide nimed. Neid ära tuleta ise.
- Näita pilti PNG-na ja oota kinnitust. Muuda ainult kasutaja nõusolekul. Kui valikul on hind (nt rohkem lõikeid), ütle see numbritega.

## 2. Pilt
- Parim on SVG; PNG/PDF tuleb enne vektoriks teha. Veebilehelt võta SVG brauseris JS-iga (`document.querySelector('header svg').outerHTML`).
- Hilisem element on peal. Taustavärvi (vaikimisi valge) kujundid lõikavad alla jääva välja ja neid ei tikita. Teise värvi kujund lõikab alumisest välja, jättes 0,3 mm ülekatet. Jooned (stroke) alla 0,8 mm tikitakse sirgpistena, laiemad kujundina.
- Eemalda nähtamatud elemendid, mida `display:none` ei peida.
- **Osa variandina:** võta SVG-st vastav rühm välja (nt `<g class="letters">`). Kui variant peab olema terve pildiga samas mõõtkavas, arvuta suurused nii: terve pildi suurus × (osa pikem külg / terve pildi pikem külg), mõlemad `design.load` kujundite järgi.

## 3. Digiteerimine

### 3.1 Töövoog
1. `swatch.py pilt.svg --list --size <suurus> …` näitab kujundite numbrid ja asukohad.
2. **Plaan:** otsusta iga kujundi kohta see, mida reeglid ise ei tea: tikkimisviis (kui piiripealne), tatami nurk (kõrvuti alad eri nurgaga, ühe kujundi osad sama nurgaga), alustikk, järjekord (taust enne, esiplaan viimasena). Kirjuta `plan.json`:
   `{"shapes": {"30": {"stitch": "tatami", "fill_angle": 10}, "5": {"underlay": "contour"}}, "order": [30, 31]}`
   Lubatud võtmed: `stitch` (satin / tatami), `underlay` (centre / contour / german / none) ja kõik `digitize.DEFAULTS` võtmed. Tundmatu võti annab vea.
3. **Automaatne proovimine:** `optimize.py` tikib iga kujundi kõigis variantides (satiin: nurgad, kiilu pikendus, täitetükk; `--angles` korral ka tatami nurk). Iga variandi juures mõõdab see katmata ala, üle serva minevat niiti, paksud kohad, lõiked ja pisted. Parim läheb plaani. Alustikku ja tihedust see ei vali, need tulevad reeglitest ja proovist.
4. `gen.py … --fabric … --plan plan.json`, siis kontroll (5), pildid (6), PDF (7) ja proovitikand (9).

### 3.2 Pistetüübid

| Element | Meetod | Parameetrid |
|---|---|---|
| Joon < 0,8 mm | 3× sirgpiste | piste kuni 2,0 mm, kurvil lühem (kõrvalekalle ≤ `run_tol` 0,1 mm) |
| Lai kujund (2·pindala/ümbermõõt > `satin_max` 2,8 mm suurimas suuruses) | servaalustikk + ristialustikk + tatami | serv 0,35 mm seest; ristialustikk risti, `fill_under_spacing` 0,9 mm; reavahe 0,30 mm (0,1 mm kordne); piste ≤ 4 mm |
| Kitsas kujund, tekst | satiin + alustikk laiuse järgi | tihedus 0,40 mm; satiin/tatami valitakse suurima suuruse järgi, et kõik suurused oleks ühtemoodi |
| Kompensatsioon `comp` 0,18 mm | piste suunas | tatami read mõlemast otsast pikemad, satiin kummaltki poolt laiem; kujundit ennast ei suurendata |
| Kinnitus | algus 2× edasi-tagasi ≤ 0,7 mm, lõpp tagasi mööda viimast pistet ≤ 0,5 mm | kujundi sees, ainult lõike juures |
| Niidilõige | järgmine algus > 2 mm või üleminek läheks üle valmis satiini | TRIM + JUMP |

### 3.3 Tatami
- 0,1 mm võrk: rea samm on 0,1 mm kordne ja rea otspunktid ümardatakse oma rea joonele (`snap()`). Muu samm teeb triipe.
- Kujundi osad tikitakse samas suunas ülevalt alla, ülemise serva järjekorras; osade vahel lõige ja hüpe.
- Iga rida algab eelmise lõpule lähemast otsast. Järgmise reani minnakse otse, kui see jääb kujundi sisse; pikk üleminek jagatakse ≤ 4 mm pisteteks. Osa pikendatakse ühe reaga ainult lõpus.
- Läbistused on ühisel võrgul: x = (j + faas) × max piste, faas nihkub igal real 1/`fill_staggers` (4) võrra. Reaotsale lähemal kui 0,4 mm läbistust ei tehta.
- Puhastus eemaldab ainult alla 0,15 mm pisted. Tsentreerimine käib täisarvulise nihkega (0,1 mm).

### 3.4 Satiin
1. Rasterda täht (0,02 mm/px), `skeletonize`, ehita pikslite graaf (diagonaal ainult siis, kui 4-naabri teed pole). Joone laius = 2·pindala/ümbermõõt.
2. Eemalda otsaga lõppevad harud < 1,8 × laius.
3. Ristumisel ühenda kaks vastassuunalist haru üheks läbivaks sambaks. Kahe joone kohtumisel läheb pikem läbi välisservani, teine lõpeb selle serval.
4. **Läbiv ots** läheb välisservast üle `comp` võrra (+ laienduse võrra, kui sammas on alla `satin_min`), sest risti olev sammas on samuti nii palju laiem (nt E püstkriips).
5. **Nurgad:** kuni `satin_mitre` (60°) pöörde korral jääb sammas tervikuks ja pisted pööravad ühe laiuse jooksul nurga poolitaja kaudu. Teravam nurk (täisnurk, A tipp) lõigatakse kaheks (mitte otsale lähemal kui 1,4 × laius) ja läheb edasi nagu punkt 3.
6. **Vaba ots:** skeleti saba lõigatakse ära ja sammas pikeneb sirgelt tipuni. Viimase laiuse jooksul pööravad pisted otsa serva suunaliseks (pikim sirge kontuurilõik tipu juures; üle 60° viltu jäävad pisted risti). Iga piste lõigatakse kontuuriga; alla 0,25 mm pisted tipus jäetakse ära. Lehvikut ei tehta.
7. **Laius:** ≤ min(1,12 × mediaan; 0,62 × laius), nurga pööramisel jagatud nurga koosinusega. Kontuurist väljas (läbiv ots) kantakse edasi viimane täislaiusega piste. Kompensatsioon `comp` + `satin_pull_pct` %, vabad otsad `satin_push` mm lühemaks. Alla `satin_min` (1,0 mm; froteel 1,5) sambad laiendatakse.
8. **Tihedus:** järgmine piste tuleb, kui enim liikunud külg (kurvi väliskülg) on eelmisest pistest risti mõõtes `satin_spacing`/2 kaugusel.
9. **Kurvi ja nurga sisekülg:** punkt, mis on samal küljel viimasest täispikast lähemal kui `satin_short` (0,25 mm), nihkub kordamööda 15% ja 30% laiusest sissepoole.
10. **Otsad kontuuril** (vaba ots, läbiv ots) lõpevad täispika pistega mõlemalt servalt. Teise samba sisse jääv ots jääb lahti (vähem kihte).
11. **Pikad pisted** üle `satin_split` (7 mm) saavad vahepunktid; nende koht nihkub pistest pisteni 1/4 võrra.
12. **Alustikk:** alla 2 mm keskjoon; 2–4 mm kontuur (servad 0,15 × laiuse kaugusel, min 0,2 mm); üle 4 mm kontuur + madal siksak.
13. **Katmata kohad:** jäägid ≥ 0,15 mm² ja ≥ `satin_gap` 0,3 mm saavad enne satiini väikese tatami 45°. Kitsam kiil (≥ 0,02 mm²) teise joone vastu lõppeva samba otsas (M keskel): see sammas pikeneb naaberjoone sisse, kuni ka mahajääv serv on 0,15 mm selle sees (max `satin_reach` 1,5 × laius).
14. **Järjekord:** proovitakse kõik sammaste järjekorrad ja suunad ning valitakse vähim lõigete arv. Üleminek käib mööda keskjoont ega lähe üle valmis satiini; satiin tuleb alati pärast alustikku. Iga tähekuju arvutatakse üks kord (sama täht = samad pisted).

## 4. Failid
- **PES:** nullpunkt vasakus ülanurgas, pistete min x ja y = 0. Nihe on `floor(min + 0,5)`, et ümardamine ei jätaks 0,1 mm nihet. `write_pes(p, fn, {'version': 6})`, siis v10 päis töötava faili järgi (`pes10.py`). Nimi masina ekraanil on max 8 märki. Masin kasutab lähimat PEC paleti värvi.
- **JEF:** keskpunktiga, lõiked lõikekäsuna (`{'trims': True}`), juurde `.bmp` eelvaade 400×400, taust (236,236,236).
- **Nimed:** failinimes täpitähti pole, kuju `Nimi 102` (pikem külg mm, 3 kohta tühikuga). PDF-is on nimi täpitähtedega. Niidi nimi tuleb `--color "#rrggbb=Nimi"` kaudu, muidu jääb PDF-i ainult värvikood.
- Mitu värvi: esmakordse ilmumise järjekorras, värvide vahel lõige ja värvivahetus.
- `outpos/<fail>.under.json` (alustiku punktid PDF-i jaoks), `out/meta.json` (parameetrid, failid, värvid, kasutatud pistetüübid `kinds`).

## 5. Kontroll
- Võrdle töötava failiga: versioon, päis, min-koordinaadid (0, 0), mõõdud, lõigete arv.
- `check.py`: pikim piste < 7 mm; ≤ ~13 läbistust/mm² (satiini ristumistes ≤ 16; 3× sirgpiste torkab samadesse aukudesse ja annab ise kõrge arvu); mõõdud vastavad nimele ja mahuvad raami.
- Täidises pole kolmnurki (kaks > 1,5 mm pistet vastassuunas ilma astmeta). Pisted on kuni 0,3 mm kujundi servast väljas (kompensatsioon). Read on ühtlased, sama kujundi osad sama suuna ja tihedusega.
- Vaata pisteid suurendusega koos kontuuriga: täidise servad, satiini otsad, läbivate joonte otsad (sama kaugel kui risti oleva samba serv), ristumised, kinnitused.
- `preview.py`: tihedusekaart (7 taset, vt 7). Oranžid ja punased kohad vaata üle ja ütle kasutajale numbritega.

## 6. Pildid
- **Tikandi pilt:** joonepilt niidi värvis helehallil taustal, 400×400 (sama stiil nagu tikandikogu eelvaadetel), suurimast suurusest: `preview.py <fail> --line` → `<fail>.joon.png`.
- **Iga faili pilt:** eeldatav välimus nagu PDF-is: `preview.py <fail> --long 1200` → `<fail>.niit.png` (niit 0,4 mm, ümarad otsad, kanga taust, pikem külg 1200 px).

## 7. PDF (`pdfcad.py` → `<Nimi> spec.pdf`)
- **Esileht (A4 püsti):** pealkiri; failide tabel (lehed, fail, mõõdud, pisted, lõiked); värvitabel (originaal, Brother, Janome värvinäidistega); „Kuidas on tehtud“ ainult kasutatud pistetüüpide ja vormingute kohta; „Kuidas testida“ + proovitabel; märkus alaservas (1 : 1, prindi 100 %, mõõtjoonlaud 50 mm). Mahub ühele lehele.
- **Joonised (A4 rõhtsalt), iga suuruse kohta 3 lehte, kõik 1:1, CAD-stiilis** (topeltraam, tsoonimärgid, pealkirjaplokk koos JOONIS-reaga, mõõtjooned, telgjooned, mõõtjoonlaud):
  1. *Eeldatav välimus:* kanga taustal niit 0,4 mm, ümarad otsad, tumedam serv ja hele läige, tikkimise järjekorras (kanga värv: keskkonnamuutuja `FABRIC`).
  2. *Pistete käik:* alustikk helesinine ja peenike; pealmised pisted järjekorras, igaüks valge äärisega, nii et pealmine jääb nähtavalt peale.
  3. *Niidi tihedus:* niiti mm/mm², silutud ~1 mm alale, 7 taset rohelisest punaseni (`preview.LEVELS`). Tavaline on 4–7; üle 8,5 kuhjuvad kihid.

## 8. Animatsioon (soovi korral)
1280×720, 60 fps, 3 kaadrit piste kohta. Helehall taust, ümar puitraam, kaamera paigal perspektiivis. Nõel on vertikaalne, hüpetel üleval, lõike juures tõuseb. Ülal failinimi ja „pisted N/M“. Enne täisrenderdust vaata proovikaadrid üle.

## 9. Proov
- Kui väärtus pole selge (tihedus, kompensatsioon, nurk), tee proovileht: `swatch.py --vary nimi=v1,v2,…` paneb sama kujundi mitu korda ühte faili, iga variandi alla number. Numbrid ja väärtused on failis `out/<Nimi>.txt`. Raskemad kujundid samas mõõtkavas: `--only 10,11,0 --size <terve mustri suurus>`. Küsi, milline number on parim.
- Masinas: kontrolli suurust, tee raami jälgimine, kasuta jäägitükki, sobivat tugimaterjali ja uut nõela 75/11. Pärast proovi küsi fail, kangas ja tugimaterjal.

| Proovil näed | Muuda |
|---|---|
| Täidis hõre | reavahe väiksemaks, ristialustikk tihedamaks |
| Pilu osade vahel | ülekate osa lõpus |
| Korrapärased heledad triibud | reavahe 0,1 mm võrgule |
| Osad erinevad | sama tikkimissuund, osade vahel lõige |
| Tähed narmendavad | satiin |
| Pikad niidid tähe peal | üleminekud mitte üle valmis satiini |
| Niidid tähtede vahel | lõige iga tähe järel (küsi) |
| Tähtede augud kinni | kompensatsioon väiksemaks |
| Kriipsu ots jääb lühemaks kui ristuv kriips | läbiv ots kompensatsiooni võrra üle serva (3.4 p 4) |
| Kangas kortsub | reavahe suuremaks, tugevam tugimaterjal |
| Niit katkeb ühes kohas | hõrenda tihedaimat kohta |
| Kinnitus harutub | kinnitus 3× edasi-tagasi |

Pärast iga parandust tee kõik suurused uuesti, käivita kontroll ning uuenda pildid, PDF ja animatsioon.

## Skriptid (`scripts/`)

`pip install --break-system-packages shapely svgelements pyembroidery scikit-image networkx reportlab pillow scipy`

| Fail | Mida teeb |
|---|---|
| `design.py` | SVG → elemendid (värv, kujund/joon), taustavärvi ja pealmiste värvide väljalõige |
| `digitize.py` | tatami, sirgpiste, `build()`, `DEFAULTS`, `FABRICS`, plaan |
| `satin.py` | satiin (skelett, sambad, nurgad, otsad, järjekord) |
| `gen.py` | kõik suurused → `out/` (PES, JEF, BMP, `meta.json`) |
| `pes10.py` | PES v6 → v10 töötava faili päisega |
| `check.py` | kontroll |
| `preview.py` | niidipilt `.niit.png` (`--long 1200`), joonepilt `.joon.png` (`--line`), tihedusekaart `.tihedus.png` |
| `swatch.py` | proovileht; `--list` kujundite numbrid |
| `optimize.py` | proovib kujundite variandid läbi → `plan.json` |
| `pdfcad.py` | `<Nimi> spec.pdf` `out/meta.json` põhjal |
| `anim3d2.py` | 3D-animatsioon: `python3 anim3d2.py "<fail>.pes" välja.mp4 60 3 [test]` |

Käivitus töökaustas (skriptid sinna kopeeritud):
```
python3 swatch.py pilt.svg --name x --size 150 --vary satin_spacing=0.4 --machines brother --list
python3 optimize.py pilt.svg --size 150 --ref-size 200 --fabric linane --angle 45 [--plan plan.json] --out plan.json
python3 gen.py pilt.svg --name "Nimi" --sizes 100,150,200 --machines brother,janome --working toimiv.pes \
    --color "#rrggbb=Niidi nimi" --fabric linane --plan plan.json [--angle 45] [--background "#ffffff"] [--set nimi=väärtus]
python3 check.py out/*.pes out/*.jef
python3 preview.py out/*.pes --long 1200
python3 pdfcad.py
```
Ilma `--working` failita jääb PES v6. Parameetrid: `--set nimi=väärtus` (vt `digitize.DEFAULTS`), nt `fill_spacing`, `fill_under_spacing`, `satin_spacing`, `satin_max`, `satin_min`, `satin_mitre`, `satin_split`, `satin_short`, `satin_reach`, `satin_gap`, `comp`, `run_tol`, `overlap`, `trim`.
