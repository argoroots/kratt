---
name: tikkimisfail
description: Vektorpildi (SVG) muutmine tikkimisfailiks (Brother PES + Janome JEF) koos kontrolli, CAD-stiilis 1:1 PDF-i ja 3D-animatsiooniga.
---

# Tikkimisfaili loomine vektorpildist

## Masinad
Faile tehakse ainult nendele kahele masinale:

| Masin | Fail | Suurim tikkimisala |
|---|---|---|
| Brother Innov-is V3 | PES (v10 töötava faili päisega, nullpunkt ülal vasakul) | 300 × 180 mm |
| Janome Memory Craft 550E | JEF (+ BMP eelvaade, keskpunktiga) | 200 × 360 mm |


## 1. Küsi enne alustamist
- Suurused (pikem külg mm), kuhu salvestada. Variandid (nt ilma tekstita) on eraldi SVG-d.
- **Mis masinale:** Brother Innov-is V3, Janome Memory Craft 550E või mõlemale – küsi alati masina järgi (failivorming tuleb masinast, kasutaja ei pea seda teadma). Iga suurus peab mahtuma valitud masina tikkimisalasse (`gen.py` hoiatab).
- Töötav fail samale masinale – sellega võrdled oma faili.
- Failide nimi ja niitide nimed, kui kasutaja pole neid öelnud (ära tuleta ise).
- Näita pilti PNG-na ja oota kinnitust, enne kui digiteerid.
- Muudatusi tee ainult kasutaja nõusolekul. Kui valikul on hind (nt rohkem lõikeid), ütle see numbritega.

## 2. Pildi hankimine
- Küsi fail (SVG parim; PNG/PDF tuleb enne vektoriks teha) või URL.
- Veebilehelt: ava leht brauseris ja võta SVG JS-iga (`document.getElementById('logo').outerHTML` või `header svg`).
- SVG kihid: hilisem element on peal. Taustavärvi (vaikimisi valge) kujundid lõikavad alla jääva välja ja neid ei tikita; teise värvi kujund lõikab alumisest välja, jättes 0,3 mm ülekatet. Joonena (stroke) antud peened jooned tikitakse sirgpistena, laiemad (≥ 0,8 mm) kujundina.
- Eemalda SVG-st nähtamatud elemendid (animatsiooni klassid jms), kui `display:none` neid ei peida.

## 3. Digiteerimine

| Element | Meetod | Parameetrid |
|---|---|---|
| Joon (stroke) < 0,8 mm | 3× sirgpiste | samm 2,0 mm |
| Lai kujund (2·pindala/ümbermõõt > 2,8 mm suurimas suuruses) | servaalustikk + ristialustikk + tatami | servaalustikk 0,35 mm seest; ristialustikk täidisega risti, 2 mm vahe; reavahe 0,30 mm (0,1 mm võrgul); max piste 4,0 mm |
| Kitsas kujund, tekst | satiin + keskjoone alustikk | tihedus 0,40 mm; satiin või tatami valitakse suurima suuruse järgi, et kõik suurused oleks ühtemoodi |
| Kõik täidised | tõmbekompensatsioon | +0,18 mm (`buffer(0.18, join_style=2)`) |
| Kinnitus | algus 2× edasi-tagasi ≤ 0,7 mm; lõpp tagasi mööda viimast pistet ≤ 0,5 mm | jääb kujundi sisse |
| Niidilõige | järgmine algus > 2 mm või üleminek läheks üle valmis satiini | TRIM + JUMP |

### 3.1 Tatami
- Koordinaadid on 0,1 mm täpsusega: rea vertikaalne samm on 0,1 mm kordne ja rea otspunktid ümardatakse oma rea joonele (`snap()`).
- Kujundi osad tikitakse samas suunas ülevalt alla, järjestatud ülemise serva järgi; osade vahel lõige + hüpe.
- Iga rida algab eelmise rea lõpule lähemast otsast. Ühendus järgmise reani otse, kui see jääb kujundi sisse.
- Osa pikendatakse ühe reaga ainult lõpus.
- Puhastus eemaldab ainult alla 0,15 mm pisted.
- Tsentreeri STITCH-punktide järgi ja täisarvulise nihkega (0,1 mm).

### 3.2 Satiin
1. Rasterda täht (0,02 mm/px), `skeletonize`, ehita pikslite graaf (diagonaal ainult siis, kui 4-naabri teed pole).
2. Eemalda otsaga lõppevad harud < 1,8 × joone laius. Joone laius = 2·pindala/ümbermõõt.
3. Ristumiskohas ühenda kaks vastassuunalist haru üheks läbivaks sambaks.
4. Lõika sammas teravas nurgas (> 25°), mitte otsale lähemal kui 1,4 × laius.
5. Kahe joone kohtumisel läheb pikem läbi kuni välisservani, teine lõpeb selle servas.
6. Vaba ots: lõika skeleti saba, pikenda sirgelt; otsakork viib mõlemad servad mööda kontuuri otsa nurkadeni.
7. Satiini laius ≤ min(1,12 × mediaan; 0,62 × joone laius).
8. Katmata jäägid (≥ 0,15 mm² ja ≥ 0,3 mm laiad): tatami 45° enne satiini.
9. Järjekord: proovi läbi kõik sammaste järjekorrad ja suunad ning vali vähim lõigete arv. Üleminek käib mööda keskjoont ja ei lähe üle valmis satiini; satiin tuleb alati pärast alustikku.
10. Iga tähekuju arvutatakse üks kord ja kopeeritakse (sama täht = samad pisted).

## 4. Failid
- **PES:** nullpunkt vasakusse ülanurka (pistete min x ja y = 0). `write_pes(p, fn, {'version': 6})`, vajadusel v10 päis töötava faili järgi (`pes10.py`). Nimi masina ekraanil: `p.metadata('name', …)` (max 8 märki). Masin kasutab lähimat PEC paleti värvi.
- **JEF:** keskpunktiga, lõiked lõikekäsuna (`{'trims': True}`), `write_jef` + `.bmp` eelvaade 400×400, taust (236,236,236).
- **Failinimed:** ilma täpitähtedeta, `Nimi 102` (pikem külg mm-des, 3 kohta tühikuga täidetud). PDF-is täpitähtedega.
- Mitme värvi korral: värvid tikitakse esmakordse ilmumise järjekorras, värvide vahel lõige + värvivahetus.
- Alustiku punktid salvesta `<fail>.under.json`, et PDF joonistaks need heledalt.

## 5. Kontroll enne üleandmist
- Võrdle töötava failiga: versioon, päis, min-koordinaadid (0, 0), mõõdud, lõigete arv.
- `check.py`: max piste < 7 mm; tihedus ≤ ~13 läbistust/mm² (satiini ristumiskohtades ≤ 16); mõõdud vastavad nimele ja mahuvad raami.
- Täidises pole kolmnurki (kaks > 1,5 mm pistet vastassuunas ilma astmeta).
- Kõik pisted ≤ 0,3 mm kujundi servast.
- Reavahed ühtlased; sama kujundi osad ühesuguse tiheduse ja suunaga.
- Vaata pisteid suurendusega koos kontuuriga: täidise servad, satiini otsad, ristumiskohad, kinnitused.


## 6. PDF
- **Esileht (A4 püsti):** pealkiri; failide tabel (leht, fail, mõõdud, pisted, lõiked); värvitabel üks rida värvi kohta (originaal ja niit värvinäidistega, kasutus); „Kuidas on tehtud“; „Kuidas testida“ + proovitabel. Vahe enne alapealkirju 28 pt. Märkus lehe alaservas (1 : 1, prindi 100 %, mõõtjoonlaud 50 mm). Mahub ühele lehele.
- **Joonised (A4 rõhtsalt), CAD-stiilis:** topeltraam ja tsoonimärgid, pealkirjaplokk raamiga joondatud, pisted 1:1 (alustikk helesinine, pealmised niidi värvis), mõõtjooned, telgjooned, mõõtjoonlaud. Printimisjuhendit joonistele ei panda.

## 7. Animatsioon
- 1280×720, 60 fps, 3 kaadrit piste kohta.
- Helehall taust, ümar puitraam valge sisepinnaga, kaamera paigal perspektiivis.
- Nõel vertikaalne; hüpetel üleval, lõike juures tõuseb.
- Ülal failinimi ja „pisted N/M“ niidi värvis.
- Enne täisrenderdust vaata proovikaadrid üle.

## 8. Proovitikkimine
Kontrolli masinas suurust, tee raami jälgimine, kasuta jäägitükki, rebitavat või lõigatavat tugimaterjali ja uut nõela 75/11. Pärast proovi küsi: fail, kangas, tugimaterjal.

| Proovil näed | Muuda |
|---|---|
| Täidis hõre | reavahe väiksemaks, ristialustikk |
| Pilu osade vahel | ülekate osa lõpus |
| Korrapärased heledad triibud | reavahe 0,1 mm võrgule |
| Osad erinevad | sama tikkimissuund, osade vahel lõige |
| Tähed narmendavad | satiin |
| Pikad niidid tähe peal | üleminekud mitte üle valmis satiini |
| Niidid tähtede vahel | lõige iga tähe järel (küsi) |
| Tähtede augud kinni | kompensatsioon väiksemaks |
| Kangas kortsub | reavahe suuremaks, tugevam tugimaterjal |
| Niit katkeb ühes kohas | hõrenda tihedaimat kohta |
| Kinnitus harutub | kinnitus 3× edasi-tagasi |

Pärast iga parandust tee kõik suurused uuesti, käivita kontrollid ning uuenda PDF ja animatsioon.

## Skriptid (`scripts/`)

`pip install --break-system-packages shapely svgelements pyembroidery scikit-image networkx reportlab pillow`

| Fail | Mida teeb |
|---|---|
| `design.py` | SVG → elemendid (värv, kujund/joon), taustavärvi ja pealmiste värvide väljalõige |
| `digitize.py` | tatami, sirgpiste, `build()`, parameetrid `DEFAULTS` |
| `satin.py` | satiin (skelett, sambad, otsad, järjekord) |
| `gen.py` | kõik suurused → `out/` (PES, JEF, BMP, `meta.json`) |
| `pes10.py` | PES v6 → v10 töötava faili päisega |
| `check.py` | kontroll: `python3 check.py out/*.pes out/*.jef` |
| `pdfcad.py` | PDF `out/meta.json` põhjal |
| `anim3d2.py` | 3D-animatsioon: `python3 anim3d2.py "<fail>.pes" välja.mp4 60 3 [test]` |

Käivitus töökaustas (skriptid sinna kopeeritud):
```
python3 gen.py pilt.svg --name "Nimi" --sizes 100,150,200 --machines brother,janome --working toimiv.pes \
    --color "#rrggbb=Niidi nimi" [--angle 45] [--background "#ffffff"] [--set satin_max=2.5]
python3 check.py out/*.pes out/*.jef
python3 pdfcad.py
```
Ilma `--working` failita jääb PES v6. Parameetreid muuda `--set nimi=väärtus` (vt `digitize.DEFAULTS`).
