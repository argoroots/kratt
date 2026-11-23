# Tikkimise teadmised

Reeglid, mille järgi digiteerija tavaliselt otsustab, koos põhjustega. `digitize.py` järgib neid vaikimisi, `plan.json` ja `--fabric` lubavad neid kujundi või kanga kaupa muuta. Arvud on lähtepunktid: lõpliku otsuse teeb proovitikand.

## 1. Füüsika lühidalt

- **Tõmme (pull):** piste tõmbab kangast oma suunas kokku. Satiin jääb kitsamaks, tatami rida lühemaks. Seetõttu tehakse pisted **piste suunas** pisut pikemaks (kompensatsioon), mitte kogu kujund igas suunas suuremaks.
- **Surve (push):** sama piste lükkab kangast risti tema suunaga välja. Satiinisammas läheb otstes pikemaks, tatami ala ridadega risti laiemaks. Vajadusel lühendatakse satiini vabu otsi.
- **Kangas liigub:** venivad kangad (trikoo, fliis) liiguvad rohkem. Neile on vaja rohkem kompensatsiooni ja alustikku, hõredamat pealmist kihti ning järjekorda keskelt väljapoole.
- **Niit peegeldab valgust oma pikkuse suunas.** Sama värvi alad, mille pisted on eri nurga all, paistavad eri tooni. Seda kasutatakse sügavuse (3D) tegemiseks ja seda tuleb vältida seal, kus ala peab ühtlane paistma.

## 2. Pistetüübid

| Tüüp | Millal | Piirid | Miks |
|---|---|---|---|
| Sirgpiste (1× või 3× edasi-tagasi) | jooned < ~1 mm, kontuurid, üleminekud | piste 1,5–3 mm; kurvil lühem, et niit ei lõikaks kurvi otse (kõrvalekalle ≤ 0,1 mm) | õhuke joon, vähe niiti |
| Satiin | kitsad kujundid, tekst | laius **1–7 mm** (froteel, fliisil vähemalt 1,5–2 mm); üle ~7 mm jagatakse pisted nihkega või tehakse tatami | läikiv, sile; pikk piste jääb asjade taha kinni ja lõtvub |
| Tatami | laiad alad | reavahe 0,3–0,45 mm, piste ≤ 4 mm, läbistused nihkega (4 rida) | katab ühtlaselt, ei lõtvu |

Satiini ja tatami vahel valitakse kujundi laiuse järgi: 2 × pindala / ümbermõõt ≤ `satin_max`. Valik tehakse suurima suuruse järgi, et kõik suurused oleks ühtemoodi.

## 3. Tihedus ja kihid

- Juhendid annavad tiheduse ühe kihi kohta (satiin 0,35–0,45 mm, tatami 0,35–0,45 mm). Kattumisel niit kuhjub: nõel kuumeneb või murdub, niit katkeb, kangas jääb kõvaks või läheb auklikuks. Üht standardarvu, kus „liiga paks“ algab, pole olemas.
- Meie hinnang niidi pikkuse järgi: 1 kiht on ~4–6 mm niiti/mm², 2 kihti ~9–11 mm/mm². Üle ~8,5 mm/mm² (kaks täiskihti) tasub üle vaadata. See piir on hinnang, mitte mõõtmine. Täpse piiri saab sinu kanga ja niidiga tiheduse proovist.
- Tavalised paksud kohad: satiinide ristumised (A tipp, K keskkoht), värvide ülekate, sirgpiste üle täidise. Kitsas katmata kiil paistab tikandis rohkem välja kui natuke paksem koht.

## 4. Satiin

- **Tihedus:** sama külje pistete vahe 0,35–0,45 mm (vaikimisi 0,40). Vahe mõõdetakse **välimise serva järgi** ja eelmise pistega risti, nii et kurvi väliskülg jääb sama tihedaks kui sirge osa.
- **Kurvi sisekülg:** punktid tulevad liiga lähestikku. Kui samal küljel on punkt eelmisest täispikast lähemal kui 0,25 mm, lühendatakse pistet kordamööda 15% ja 30% võrra („lühikesed pisted“). Muidu kuhjub niit ja kangas läheb katki.
- **Alustikk laiuse järgi:** alla 2 mm keskjoon; 2–4 mm mõlemad servad (kontuur, 0,2–0,4 mm seest); üle 4 mm kontuur ja madal siksak. Alustikk kinnitab kanga tugimaterjali külge ja tõstab satiini kiudude kohale.
- **Nurgad:** kuni ~60° pöördes jääb sammas tervikuks ja pisted pööravad ümber nurga (nurga poolitaja kaudu). Teravamas nurgas (täisnurk, A tipp) jagatakse sammas kaheks: üks läheb läbi välisservani ja kompensatsiooni võrra üle selle, teine lõpeb tema serval. Täisnurgas jätab pööramine välisnurka lehvikuvahed, jagamine mitte (mõõdetud E-tähel).
- **Otsad kontuuril** lõpevad täispika pistega mõlemalt servalt, muidu jääb nurka kolmnurk.
- **Vabad otsad:** viimased pisted pööravad otsa serva suunaliseks (kaldus otsal, nt K ja A jalal, viltu). Nii sulgub ots täpselt ning tippu ei kuhju lehvikut.
- **Ristumised:** pikem joon läheb läbi ja lühem lõpeb selle serval. Läbiv joon läheb välisservast üle sama palju, kui risti olev joon on kompensatsiooni tõttu laiem (muidu paistab ots lühem, nt E püstkriips). Kitsas kiil, mida täide ei kata, kaetakse pikendusega. Laiem tühimik saab enne satiini väikese tatami.
- **Silmused (o, a, b, d, p, q kõhud):** sammas käib ringiga ümber, pisted on alati üle sammaste (risti), mitte silmusega kaasa. Kõht algab ja lõpeb püstkriipsu serval. Püstkriips läheb ise läbi kuni oma otsani, ka siis, kui kõhu all on sellest järel vaid umbes üks laius.
- **Kompensatsioon:** 0,15–0,3 mm kummalegi poole (vaikimisi 0,18). Venivale kangale rohkem, stabiilsele vähem.
- **Väike kiri:** 40 wt niit on ~0,4 mm paks. Alla ~5 mm kõrgune kiri kipub kinni minema: augud sulguvad, täpid sulavad tähe külge. Kitsast sammast laiendatakse kõige rohkem 0,3 mm, aga päris lahendus on suurem kiri või 60 wt niit ja 65/9 nõel.
- **Mis pole joon, pole satiin:** ring, täpp või kujund, mille kõige laiem koht on palju laiem kui keskmine (kammi lai riba), ei sobi satiinile, sest satiin käib skeleti järgi ja ringi skelett on üks punkt. Need tehakse tatamina.

## 5. Tatami

- **Reavahe:** 0,30 mm on testitud linasel kangal ja sobis. Tavaline vahemik on 0,35–0,45 mm. Meil on reavahe alati 0,1 mm kordne (0,3 / 0,4 / 0,5), sest 0,1 mm võrgul teeb muu samm triipe.
- **Ridade otsad:** ühe kujundi kõik osad tikitakse samas suunas (ülevalt alla) ning iga rida algab eelmise lõpule lähemast otsast. Eri suunas tikitud osad paistavad eri tooni.
- **0,1 mm võrk:** rea samm ja otspunktid on 0,1 mm võrgul. Muidu teeb ümardamine korrapärased heledad triibud.
- **Läbistused:** nihkega võrgul (4 rida kordub), nii et augud moodustavad ühtlase diagonaali, mitte juhuslikke jooni.
- **Alustikk:** serv 0,35 mm seest ja täidisega risti read ~3 × reavahe kaugusel (0,9 mm). Hõredam alustikk laseb kangal läbi paista ja kujund vajub.
- **Kompensatsioon:** ainult ridade suunas (rida on mõlemast otsast pikem).
- **Nurk:** kõrvuti alad tehakse eri nurgaga, et tõmme ei teeks pilusid ja alad eristuks. Ühe kujundi osad tehakse sama nurgaga. Pika kitsa ala korral on rida parem pikkupidi, siis tuleb vähem pöördeid.

## 6. Niidi suund ja „3D“

- Sama nurgaga kõrvuti alad sulavad üheks laigaks. Nurga muutmine 30–90° võrra annab valgusest tooni erinevuse ilma uue värvita.
- Ümar kujund paistab kumer, kui pisted järgivad kuju: satiin mööda kaart, tatami raadiusega või kujuga kaasa pööravalt.
- Valgus tuleb tavaliselt ülevalt. Püstised pisted paistavad heledamad, rõhtsad tumedamad (sõltub ka niidist ja vaatenurgast).
- Esiplaan tikitakse viimasena ja võib olla tihedam või kõrgema alustikuga. Nii tõuseb see tausta kohale.

## 7. Järjekord, lõiked, kinnitus

- Värv korraga, vähem värvivahetusi. Taust enne esiplaani. Venival kangal keskelt väljapoole.
- Üleminek kujundi sees peidetakse järgmiste pistete alla. Üle valmis satiini üleminekut ei tehta: siis tuleb lõige.
- Lõige, kui järgmine algus on > 2 mm kaugusel. Lõike ees ja järel on kinnitus (0,5–0,7 mm edasi-tagasi kujundi sees).
- Pikim piste ≤ 7 mm (jääb millegi taha kinni). Lühim ~0,3 mm, väiksem lõikab niiti ja kangast.

## 8. Kanga järgi (lähtepunktid)

`--fabric <nimi>` seab need väärtused. Ülejäänu jääb vaikimisi.

| Kangas | Tatami reavahe | Satiin | Kompensatsioon | Alustikk | Satiin vähemalt | Tugimaterjal |
|---|---|---|---|---|---|---|
| `linen`, `cotton` (linane, puuvill; kootud, stabiilne) | 0,30 | 0,40 | 0,18 | tavaline | 1,0 mm | rebitav |
| `denim`, `canvas` (teksas, kanvas; paks, stabiilne) | 0,40 | 0,40 | 0,15 | tavaline | 1,0 mm | rebitav |
| `jersey` (trikoo: T-särk, polo, veniv) | 0,40 | 0,45 | 0,30 (suunaline ±25 %) | tihedam (0,75) | 1,2 mm | lõigatav + kinnitus |
| `fleece`, `terry` (fliis, frotee; karvane) | 0,40 | 0,40 | 0,25 | tihedam (0,75), satiinile siksak | 1,5 mm | lõigatav; peale vees lahustuv kile |
| `leather`, `vinyl` (nahk, vinüül) | 0,50 | 0,45 | 0,12 | vähe (ainult serv) | 1,2 mm | rebitav; augud jäävad – vähem pisteid |

**Venivad kangad (trikoo, fliis):** silmuskude venib ühes suunas rohkem (T-särgi esiosal risti, mööda silmuseridu). Pisted, mis on venivuse suunas, tõmbavad kangast rohkem kokku, seega on kompensatsioon suunaline: `comp × (1 − s/2 … 1 + s/2)`, kõige suurem venivuse suunas (`comp_stretch`: trikoo 0,5, fliis 0,3; `stretch_angle` 0° = risti, kui kangas on raamis sirge). Trikool on horisontaalsel satiinipistel 0,375 mm, vertikaalsel 0,225 mm. Kui toode on raamis viltu või külili, muuda `--set stretch_angle=…`. Päris tikandi foto (EMTA 104 mm hark lina-seadetega) näitas, et haru tuli ~0,7 mm kitsam.

**Niidi jämedus:** tavaline 40 wt (~0,35–0,4 mm), peen 60 wt (~0,25 mm) väikese kirja ja peente detailide jaoks, nõel 65/9. 60 wt korral on pisted tihedamad ja satiin kitsam: satiini reavahe × 0,7, täidise reavahe × 0,75, satiin vähemalt × 0,6, kompensatsioon × 0,7 (kanga väärtustest).

Allikad: Ink/Stitch'i lähtekood (vaikeväärtused: reavahe 0,25, satiin 0,4, lühikesed pisted 0,25 mm / 15%, 4 nihet, alustikk 3 × reavahe). Tööstuslikud digiteerimisjuhendid (EmbroideryHoop, Embroidery Legacy, Forum fonts, mySewnet). StitchPilot (reavahe kanga järgi).

## 9. Automaatne valik

Inimene proovib tavaliselt 1–2 varianti. Arvuti saab proovida sadu ja hinnata neid mõõdetavalt (`optimize.py`):

- **katmata ala** kujundi sees (niit loetakse 0,3 mm laiuseks, sest kangal tõmbub see kokku; nurk, mille 0,4 mm niit napilt katab, jääb tikandis lahti);
- **üle serva** minev niit;
- **paksud kohad** (niiti > 8,5 mm/mm²);
- lõigete arv, pistete arv, lühikesed ja pikad pisted.

Valitakse väikseima kaaluga summaga variant ja otsused kirjutatakse `plan.json` faili. Kaalud on `optimize.py` alguses. Kanga käitumist arvuti ei näe: lõpliku kinnituse annab proovitikand.

## 10. Ääris, kontuuritäide, aplikatsioon, ristpiste

- **Ääris (satiin täidise ümber):** tatami serv on alati veidi sakiline ja tõmbub. Satiinriba (2–4 mm) katab selle ja annab terava, läikiva serva. Täidis läheb ääriste alla 0,3–0,5 mm, muidu tekib tõmbest pilu. Alla ääriste keskjoon. Nurgad tehakse pöördega (lehvik sisenurga ümber); seal on niiti rohkem, tihedusekaardil punane täpp nurgas on tavaline. Ringi algus sirge külje keskel, mitte nurgas (nurgas jääb algus ja lõpp näha).
- **Sirgpiste serv täidise peal:** pärast tatamit 1× (või 3×) sirgpiste mööda serva teeb serva teravaks ja peidab ridade sakilised otsad. Kitsale täidisele on see kergem kui satiinääris.
- **Kontuuritäide:** read käivad kujundi servaga kaasa. Ümar kujund (ring, leht, süda) paistab kumer, sest niidi suund muutub pidevalt ja valgus langeb igal pool eri nurga all (vt 6). Tõmme on kõigis suundades ühtlane, nii et ring jääb ümmargune (tatami teeb ringi ridade suunas lühemaks). Ringid tikitakse ühe spiraalina: eraldi ringide algused teevad nähtava „õmbluse“ kiire. Spiraal töötab, kuni kujund on üks tükk ilma aukudeta; keerulisemal kujundil tikitakse ringid eraldi, igaüks lähima ringi kõrvalt. Üks kiht annab ~3–4 mm/mm² (õhem kui tatami alustikuga); tugev kangas või õhuke välimus on siis OK, muidu väiksem reavahe.
- **Aplikatsioon:** suur ala tehakse kangatükist, mitte niidist: vähem pisteid, pehmem, kiirem. Järjekord on alati sama: (1) paigutusjoon näitab, kuhu kangas panna; peatus; (2) kinnitusjoon 0,5 mm joonest seespool hoiab kanga paigal; peatus, lõika liigne kangas kinnitusjoone lähedalt ära; (3) satiinääris (2,5–4 mm) katab lõigatud serva. Kitsam ääris kui ~2,5 mm laseb kiudu välja. Masin peatub värvivahetusena sama värviga, seega peab tikkija teadma, mis peatuse ajal teha (PDF esileht).
- **Ristpiste:** folk- ja tikandimustrid (nt rahvariided) on ruudustikul; käsitöö ristpiste matkimiseks tehakse iga rist kahe diagonaaliga ühisel ruudustikul. Ruudu suurus 1,5–3 mm: väiksem ruut kuhjub (keskpunktis kaks kihti), suurem jääb lahtiseks. Ruudustik on ühine kogu tikandil, muidu ei lähe eri kujundite ristid kokku. Kujundi serv on astmeline (ruudustiku järgi) – see kuulub stiili juurde; täpse kontuuri jaoks on vaja teist tehnikat.
