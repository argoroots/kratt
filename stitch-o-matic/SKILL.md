---
name: stitch-o-matic
description: Vektorpildi (SVG) muutmine tikkimisfailiks valitud masinale (Brother PES, Janome JEF) mitmes suuruses, koos kontrolli, 1:1 projekti-PDF-i ja soovi korral animatsiooniga.
---

# Tikkimisfaili loomine vektorpildist

Reeglid ja nende põhjused (kangas, tihedus, alustikk, suund, nurgad) on failis `KNOWLEDGE.md`. Loe see enne digiteerimist läbi.

## Masinad

| Masin | Fail | Suurim tikkimisala |
|---|---|---|
| Brother Innov-is V3 | PES (v10 töötava faili päisega, nullpunkt ülal vasakul) | 300 × 180 mm |
| Janome Memory Craft 550E | JEF (+ BMP eelvaade, keskpunktiga) | 200 × 360 mm |

PES sobib Brotheri (ja Baby Locki) masinatele, JEF Janome masinatele. Teise mudeli või väiksema raami puhul anna raam ette: `--hoop 130x180` (tikkimisala mm). Levinud raamid:

| Raam | Tikkimisala (mm) | Kus |
|---|---|---|
| 4 × 4" | 100 × 100 | Brotheri ja Janome väikesed masinad (nt Brother M370) |
| 5 × 7" | 130 × 180 | Brother (nt F540E); Janome RE20 on 140 × 200 |
| SQ14 / SQ20 | 140 × 140 / 200 × 200 | Janome |
| 6 × 10" | 160 × 260 | Brother keskklass |
| 7 × 12" | 180 × 300 | Brother, nt Innov-is V3 |
| RE36 | 200 × 360 | Janome 550E |
| 9½ × 14" | 240 × 360 | Brother XE2, XJ2 |

Raami kasutatav ala on masina juhendis; kui kasutaja ei tea, küsi masina mudelit ja vaata järele.

## 1. Küsi enne alustamist
- **Masin ja raam:** küsi masina mudelit, mitte faili vormingut (vorming tuleb masinast: Brother → PES, Janome → JEF). Kui see pole Innov-is V3 ega 550E või kasutatakse väiksemat raami, küsi raami tikkimisala ja anna `--hoop`.
- **Suurused** (pikem külg mm). Iga suurus peab mahtuma raami (`gen.py` hoiatab). Küsi, kas suurus on tikandi tegelik mõõt (siis `--exact`: skaala kohendatakse, kuni pistete pikem külg on täpselt see, 0,05 mm piires) või pildi mõõt (vaikimisi; pisted tulevad kompensatsiooni võrra suuremad). Kasutajad mõtlevad tavaliselt tegelikku mõõtu.
- **Niit:** tavaline 40 wt või peen 60 wt (`--thread 60`). Alla ~5 mm kirja korral soovita 60 wt (nõel 65/9): pisted tihedamad ja kitsamad, tähtede augud jäävad lahti. 60 wt fail ei sobi 40 wt niidiga.
- **Kangas:** linane, puuvill, teksas, kanvas, trikoo, fliis, frotee, nahk, vinüül (`--fabric linen / cotton / denim / canvas / jersey / fleece / terry / leather / vinyl`, vt `KNOWLEDGE.md` jaotis 8). Kui see pole teada, küsi; ära oleta.
- **Tugimaterjal:** mis on all ja kas midagi on peal (`--stabilizer cutaway|mesh|tearaway|washaway-film|washaway-fiber|fusible|sticky`, liita `+`-ga, nt `cutaway+fusible`; `--topping washaway-film`). Kui kasutaja ei tea, soovita kanga järgi (`KNOWLEDGE.md`, Tugimaterjal) ja küsi kinnitust. Trikool vees lahustuv all: ütle, et pärast pesu see ei toeta (PDF hoiatab ka).
- **Variandid** (nt ilma tekstita) on eraldi SVG-d. Küsi, kas variant peab olema samas mõõtkavas kui terve pilt (vt 2). Kui jah, tee kõigepealt terve pilt; `gen.py` trükib iga faili skaala (`scale … mm/unit`, ka `out/meta.json`), ja variant tehakse samade skaaladega: `--scales 0.568,0.856,1.143` (SVG-d peavad olema samas koordinaadistikus).
- Töötav fail samale masinale (sellega võrdled), failide ja niitide nimed. Neid ära tuleta ise.
- Näita pilti PNG-na ja oota kinnitust. Muuda ainult kasutaja nõusolekul. Kui valikul on hind (nt rohkem lõikeid), ütle see numbritega.

## 2. Pilt
- Parim on SVG; PNG/PDF tuleb enne vektoriks teha. Veebilehelt võta SVG brauseris JS-iga (`document.querySelector('header svg').outerHTML`).
- Hilisem element on peal. Taustavärvi (vaikimisi valge) kujundid lõikavad alla jääva välja ja neid ei tikita. Teise värvi kujund lõikab alumisest välja, jättes 0,3 mm ülekatet. Jooned (stroke) alla 0,8 mm tikitakse sirgpistena, laiemad kujundina.
- Eemalda nähtamatud elemendid, mida `display:none` ei peida.
- **Osa variandina:** võta SVG-st vastav rühm välja (nt `<g class="letters">`). Kui variant peab olema terve pildiga samas mõõtkavas, arvuta suurused nii: terve pildi suurus × (osa pikem külg / terve pildi pikem külg), mõlemad `design.load` kujundite järgi.

## 3. Digiteerimine

### 3.1 Töövoog
1. `swatch.py pilt.svg --list --size <suurim suurus>` näitab kujundite numbrid, asukohad, reeglite valiku (`rule:`) ja mõõdetud ettepanekud (`suggest:` ümar → kontuuritäide, suur ala → aplikatsioon, ruudustikul → ristpiste, lai täidis → ääris; põhjus juures).
2. **Paku tehnika välja (kohustuslik):** näita kasutajale iga `suggest:` rida koos põhjuse ja hinnaga (pisted, peatused, värvid) ning küsi. Lisa ka see, mida mõõt ei näe, aga pildist on näha (folkmuster, kangatükk, 3D-efekt; vt KNOWLEDGE.md 6 ja 10, TODO.md). Ära vali ise: ilma vastuseta jääb reegli valik. Kinnitatud valik läheb plaani.
3. **Plaan:** otsusta iga kujundi kohta see, mida reeglid ise ei tea: tikkimisviis (kui piiripealne), tatami nurk (kõrvuti alad eri nurgaga, ühe kujundi osad sama nurgaga), alustikk, järjekord (taust enne, esiplaan viimasena). Kirjuta `plan.json`:
   `{"shapes": {"30": {"stitch": "tatami", "fill_angle": 10}, "5": {"underlay": "contour"}}, "order": [30, 31]}`
   Lubatud võtmed: `stitch` (satin / tatami / contour / applique / cross, vt 3.3), `underlay` (centre / contour / german / none) ja kõik `digitize.DEFAULTS` võtmed. Tundmatu võti annab vea.
4. **Automaatne proovimine:** `optimize.py` tikib iga kujundi kõigis variantides (satiin: nurgad, kiilu pikendus, täitetükk; `--angles` korral ka tatami nurk). Iga variandi juures mõõdab see katmata ala, üle serva minevat niiti, paksud kohad, lõiked ja pisted. Parim läheb plaani. Alustikku ja tihedust see ei vali, need tulevad reeglitest ja proovist.
5. `gen.py … --fabric … --plan plan.json`, siis kontroll (5, koos kontrollpiltidega 6), PDF (7) ja proovitikand (9).

### 3.2 Pistetüübid

| Element | Meetod | Parameetrid |
|---|---|---|
| Joon < 0,8 mm | 3× sirgpiste | piste kuni 2,0 mm, kurvil lühem (kõrvalekalle ≤ `run_tol` 0,1 mm) |
| Lai kujund (2·pindala/ümbermõõt > `satin_max` 2,8 mm suurimas suuruses) | servaalustikk + ristialustikk + tatami | serv 0,35 mm seest; ristialustikk risti, `fill_under_spacing` 0,9 mm; reavahe 0,30 mm (0,1 mm kordne); piste ≤ 4 mm |
| Kitsas kujund, tekst | satiin + alustikk laiuse järgi | tihedus 0,40 mm; satiin ainult joonetaolisele osale: suurim siseringjoon ≤ `satin_blob` (1,9) × keskmine laius ja ≤ 1,5 × `satin_max` (muidu ring, täpp, kammi lai riba → tatami); satiin/tatami valitakse suurima suuruse järgi, et kõik suurused oleks ühtemoodi; plaan ei saa sundida satiini üle `satin_force_max` 10 mm |
| Kompensatsioon `comp` 0,18 mm | piste suunas | tatami read mõlemast otsast pikemad, satiin kummaltki poolt laiem; kujundit ennast ei suurendata |
| Kinnitus | algus 2× edasi-tagasi ≤ 0,7 mm, lõpp tagasi mööda viimast pistet ≤ 0,5 mm | kujundi sees, ainult lõike juures |
| Niidilõige | järgmine algus > 2 mm või üleminek läheks üle valmis satiini | TRIM + JUMP |

### 3.3 Muud täidised (ainult plaani kaudu)
Reeglid neid ise ei vali: `swatch.py --list` pakub mõõtmise järgi (3.1 p 1–2), kasutaja kinnitab. Põhjused: KNOWLEDGE.md 10.

| Plaanis | Tehnika | Seaded |
|---|---|---|
| `fill_border` > 0 (tatami või contour juures) | satiinääris täidise serval | laius mm (2–4) |
| `fill_outline` 1 või 3 (tatami või contour juures) | pärast täidist sirgpiste mööda serva | kordade arv |
| `"stitch": "contour"` | kontuuritäide | `fill_spacing`, `fill_border` |
| `"stitch": "applique"` | aplikatsioon, 2 peatust | `applique_border` (3 mm) |
| `"stitch": "cross"` | ristpiste | `cross_size` (2 mm) |

Peatused ütleb PDF esilehel. Optimeerija neid tehnikaid ei muuda.

### 3.4 Kuidas pisted tehakse
Tatami, satiini ja muude täidiste algoritmid samm-sammult: `ALGORITHMS.md`. Loe seda, kui parandad koodi või kui proov näitab viga, mille põhjust on vaja leida (nt kriipsu ots lühem, kiil lahti, nurgas lehvik).

## 4. Failid
- **PES:** nullpunkt vasakus ülanurgas, pistete min x ja y = 0. Nihe on `floor(min + 0,5)`, et ümardamine ei jätaks 0,1 mm nihet. `write_pes(p, fn, {'version': 6})`, siis v10 päis töötava faili järgi (`pes10.py`). Nimi masina ekraanil on max 8 märki. Masin kasutab lähimat PEC paleti värvi.
- **JEF:** keskpunktiga, lõiked lõikekäsuna (`{'trims': True}`), juurde `.bmp` eelvaade 400×400, taust (236,236,236).
- **Nimed:** failinimes täpitähti pole, kuju `Nimi 102` (pikem külg mm, 3 kohta tühikuga). PDF-is on nimi täpitähtedega. Niidi nimi tuleb `--color "#rrggbb=Nimi"` kaudu, muidu jääb PDF-i ainult värvikood.
- Mitu värvi: esmakordse ilmumise järjekorras, värvide vahel lõige ja värvivahetus.
- `outpos/<fail>.under.json` (alustiku punktid PDF-i ja kattuvuse jaoks), `outpos/<fail>.shapes.json` (kujundite nähtav ala, kattuvuse jaoks), `out/meta.json` (parameetrid, failid, värvid, kasutatud pistetüübid `kinds`, niidiplokkide värvid `blocks`, masina peatused `stops`). PES-i tagasi lugedes läheb korduva värvi plokkide värv segi, seega `preview.py` ja `pdfcad.py` võtavad värvi `blocks` järgi.
- Rohkem tehnikaid, mida veel pole: `TODO.md`.

## 5. Kontroll
- Võrdle töötava failiga: versioon, päis, min-koordinaadid (0, 0), mõõdud, lõigete arv.
- `check.py`: pikim piste < 7 mm; ≤ ~13 läbistust/mm² (satiini ristumistes ≤ 16; 3× sirgpiste torkab samadesse aukudesse ja annab ise kõrge arvu); mõõdud vastavad nimele ja mahuvad raami.
- Täidises pole kolmnurki (kaks > 1,5 mm pistet vastassuunas ilma astmeta). Pisted on kuni 0,3 mm kujundi servast väljas (kompensatsioon). Read on ühtlased, sama kujundi osad sama suuna ja tihedusega.
- Vaata pisteid suurendusega koos kontuuriga: täidise servad, satiini otsad, läbivate joonte otsad (sama kaugel kui risti oleva samba serv), ristumised, kinnitused.
- `preview.py`: tihedusekaart (7 taset, vt 7). Oranžid ja punased kohad vaata üle ja ütle kasutajale numbritega.
- **Kattuvus ja üle serva** (`coverage.py`, käivitub ise `gen.py` ja `check.py` sees). Kattuvus: iga pealmine piste joonistatakse niidi laiusena (40 wt 0,35 mm, 60 wt 0,25 mm) (alustikku ei arvestata, see jääb pealmise alla) ja võrreldakse kujunditega (0,25 mm servast sissepoole). Katmata koht, kuhu mahub ≥ 0,25 mm ring, annab `WARNING: … uncovered spot(s): <suurus> mm at x …, y …` (mm PES-i vasakust ülanurgast). Nii leitakse praod satiinisammaste vahel, kiilud seal, kus pisted pööravad liiga järsku, ja vahed täidise osade vahel. Hoiatusega faili ei anta kasutajale enne, kui põhjus on leitud ja parandatud või kasutajale numbritega öeldud. `python3 coverage.py outpos/*.pes` joonistab ka `check/<fail>.holes.png` (kaetud hall, augud punased). Silmaga eelvaatest seda ei leia: 105 mm hargi 0,5 mm kiil jäi väikesel pildil märkamata. Kõrvuti kujundid kontrollitakse koos, nii et ka nende vaheline pragu tuleb välja. Üle serva: iga pealmine nõelapiste mõõdetakse lähimast kujundist (joon koos laiusega); kaugemal kui kompensatsioon (venival kangal suurim suunaline) + õhukese satiini laiendus + 0,3 mm annab `WARNING: … place(s) over the edge: <kaugus> mm at x …, y …`. Ristpiste ruudud võivad kujundist välja ulatuda ühe ruudu võrra (see on lubatud). Pildil on üle serva kohad sinised.

## 6. Kontrollpildid (ainult enda jaoks)
Kasutaja saab **ainult tikkimisfailid ja projekti PDF-i** (7). Pilte talle ei anta; kui ta tahab tulemust näha, saada PDF.
- `preview.py out/*.pes --long 1200` → `check/<fail>.thread.png` (pisted täpselt nagu failis), `check/<fail>.look.png` (eeldatav välimus, nagu PDF-is) ja `check/<fail>.density.png` (tihedusekaart) ning tiheduse tasemed protsentidena. Vaata need enne PDF-i üle.
- `--line` → `check/<fail>.line.png` (400×400 joonepilt niidi värvis helehallil taustal) ainult siis, kui tikand lisatakse kogusse (`tikandikogu` skill).

## 7. PDF (`pdfcad.py` → `<Nimi> - Projekt.pdf`)
- **Esileht (A4 püsti):** pealkiri; failide tabel (lehed, fail, mõõdud, pisted, lõiked); värvitabel (originaal, Brother, Janome värvinäidistega); „Valikud“ – kõik, mida kasutaja valis või seadistas (masin, raam, suurused ja mõõdu liik, kangas, tugimaterjal all ja peal, niit, täidise nurk, niidinimed, plaan, `--set`); kui midagi on valimata, märgitakse soovitus; „Kuidas on tehtud“ ainult kasutatud pistetüüpide ja vormingute kohta; „Kuidas testida“ + proovitabel; märkus alaservas (1 : 1, prindi 100 %, mõõtjoonlaud 50 mm). Mahub ühele lehele.
- **Joonised (A4 rõhtsalt), iga suuruse kohta 3 lehte, kõik 1:1, CAD-stiilis** (topeltraam, tsoonimärgid, pealkirjaplokk koos JOONIS-reaga, mõõtjooned, telgjooned, mõõtjoonlaud):
  1. *Eeldatav välimus:* tikand pärast tikkimist (`preview.look`): satiinipisted tõmbuvad otstest kompensatsiooni võrra sisse (kangal venivam suund rohkem, alla 1,5 mm pisted vähem), satiinisammas pikeneb otstest 0,4 × kompensatsioon, satiin kumer (keskelt hele, otstest tume), sirgpiste jääb pidevaks; kanga tekstuur kanga järgi (trikotaaž silmused, lina/puuvill riie), kanga värv keskkonnamuutujast `FABRIC`. See on hinnang: kompensatsiooni arv on eeldatav tõmme, tegeliku näitab proov. Fail ise (pisted enne tõmmet) on `check/<fail>.thread.png`.
  2. *Pistete käik:* alustikk helesinine ja peenike; pealmised pisted järjekorras, igaüks valge äärisega, nii et pealmine jääb nähtavalt peale.
  3. *Niidi tihedus:* niiti mm/mm², silutud ~1 mm alale, 7 taset rohelisest punaseni (`preview.LEVELS`). Tavaline on 4–7; üle 8,5 kuhjuvad kihid.

## 8. Animatsioon (soovi korral)
1280×720, 60 fps, 3 kaadrit piste kohta. Helehall taust, ümar puitraam, kaamera paigal perspektiivis. Nõel on vertikaalne, hüpetel üleval, lõike juures tõuseb. Ülal failinimi ja „pisted N/M“. Enne täisrenderdust vaata proovikaadrid üle.

## 9. Proov
- Kui väärtus pole selge (tihedus, kompensatsioon, nurk), tee proovileht: `swatch.py --vary nimi=v1,v2,…` paneb sama kujundi mitu korda ühte faili, iga variandi alla number. Numbrid ja väärtused on failis `out/<Nimi>.txt`. Raskemad kujundid samas mõõtkavas: `--only 10,11,0 --size <terve mustri suurus>`. Küsi, milline number on parim.
- Masinas: kontrolli suurust, tee raami jälgimine, kasuta jäägitükki, sobivat tugimaterjali ja uut nõela 75/11. Pärast proovi küsi fail, kangas ja tugimaterjal.
- **Foto tikitud tulemusest** (`photo_check.py foto.jpg "outpos/<fail>.pes" [--box x0,y0,x1,y1]`): niit leitakse fotolt värvi järgi, joondatakse failiga (nihe, pööre, mõõtkava) ja võrreldakse. Annab protsendi, kui palju oodatud niidist fotol on, ning kohad (mm faili vasakust ülanurgast), kus niiti on puudu (pragu, kangas tõmbas sisse, osa jäi tikkimata) või üle (kuju venis, pisted üle serva). Pilt `check/photo.png`: punane puudu, sinine üle. `--box` siis, kui fotol on mitu tikandit. Foto otse pealt, kangas raamis sirge; nurga all, varjus või kangaga sarnase niidi korral on tulemus ligikaudne: need on kohad, mida vaadata, mitte mõõtmine. Näide: EMTA 104 mm hark T-särgil (lina-seadetega fail) – vasak haru oli ~0,7 mm kitsam kui failis, st kangas tõmbas sisse → trikoo seaded (suurem ja suunaline kompensatsioon).

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
| Kriipsu ots jääb lühemaks kui ristuv kriips | läbiv ots kompensatsiooni võrra üle serva (ALGORITHMS.md 2 p 4) |
| Kangas kortsub | reavahe suuremaks, tugevam tugimaterjal |
| Niit katkeb ühes kohas | hõrenda tihedaimat kohta |
| Kinnitus harutub | kinnitus 3× edasi-tagasi |

Pärast iga parandust tee kõik suurused uuesti, käivita kontroll ning uuenda PDF ja animatsioon.

## Skriptid (`scripts/`)

`pip install --break-system-packages shapely svgelements pyembroidery scikit-image networkx reportlab pillow scipy`

| Fail | Mida teeb |
|---|---|
| `design.py` | SVG → elemendid (värv, kujund/joon), taustavärvi ja pealmiste värvide väljalõige |
| `digitize.py` | tatami, sirgpiste ja muud tehnikad (`PatternBuilder`), `build()`, `DEFAULTS`, `FABRICS`, plaan |
| `satin.py` | satiin (skelett, sambad, nurgad, otsad, järjekord), `letter()` |
| `gen.py` | kõik suurused → `out/` (PES, JEF, BMP, `meta.json`) |
| `pes10.py` | PES v6 → v10 töötava faili päisega |
| `check.py` | kontroll (koos kattuvusega, kui `outpos/<fail>.shapes.json` on olemas) |
| `coverage.py` | kattuvus ja üle serva: katmata kohad ja liiga kaugele ulatuvad pisted, pilt `check/<fail>.holes.png` |
| `photo_check.py` | foto tikitud tulemusest vs fail: puudu/üle kohad mm-des, pilt `check/photo.png` |
| `preview.py` | kontrollpildid kausta `check/`: niidipilt `.thread.png` (`--long 1200`), eeldatav välimus `.look.png`, tihedusekaart `.density.png`, joonepilt `.line.png` (`--line`) |
| `swatch.py` | proovileht; `--list` kujundite numbrid, reeglite valik ja tehnikate ettepanekud |
| `optimize.py` | proovib kujundite variandid läbi → `plan.json` |
| `pdfcad.py` | `<Nimi> - Projekt.pdf` `out/meta.json` põhjal |
| `anim3d2.py` | 3D-animatsioon: `python3 anim3d2.py "<fail>.pes" välja.mp4 60 3 [test]` |
| `texts.py`, `strings_et.json` | kasutajale nähtavad tekstid (PDF, masina peatused, proovilehe `.txt`, animatsioon) eesti keeles; teine keel: `strings_<keel>.json` ja `STITCH_LANG=<keel>` |

Käivitus töökaustas (skriptid ja `strings_et.json` sinna kopeeritud):
```
python3 swatch.py pilt.svg --size 200 --list
python3 optimize.py pilt.svg --size 150 --ref-size 200 --fabric linen --angle 45 [--plan plan.json] --out plan.json
python3 gen.py pilt.svg --name "Nimi" --sizes 100,150,200 [--exact] [--thread 60] [--hoop 130x180] [--stabilizer cutaway] [--topping washaway-film] --machines brother,janome --working toimiv.pes \
    --color "#rrggbb=Niidi nimi" --fabric linen --plan plan.json [--angle 45] [--background "#ffffff"] [--set nimi=väärtus]
python3 check.py out/*.pes out/*.jef
python3 preview.py out/*.pes --long 1200
python3 pdfcad.py
```
Ilma `--working` failita jääb PES v6. Parameetrid: `--set nimi=väärtus` (vt `digitize.DEFAULTS`), nt `fill_spacing`, `fill_under_spacing`, `satin_spacing`, `satin_max`, `satin_min`, `satin_widen_max`, `satin_blob`, `satin_force_max`, `satin_mitre`, `satin_split`, `satin_short`, `satin_reach`, `satin_gap`, `comp`, `run_tol`, `overlap`, `trim`.
