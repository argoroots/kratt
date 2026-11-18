# Algoritmid

Kuidas `scripts/` teeb pisted: samm-sammult, koos arvudega. Loe seda, kui parandad koodi või kui tulemus ei vasta ootusele. Tavalise tikandi tegemiseks piisab SKILL.md-st. Reeglid ja nende põhjused on KNOWLEDGE.md-s.

## 1. Tatami
- 0,1 mm võrk: rea samm on 0,1 mm kordne ja rea otspunktid ümardatakse oma rea joonele (`snap()`). Muu samm teeb triipe.
- Kujundi osad tikitakse samas suunas ülevalt alla, ülemise serva järjekorras; osade vahel lõige ja hüpe.
- Iga rida algab eelmise lõpule lähemast otsast. Järgmise reani minnakse otse, kui see jääb kujundi sisse; pikk üleminek jagatakse ≤ 4 mm pisteteks. Osa pikendatakse ühe reaga ainult lõpus.
- Läbistused on ühisel võrgul: x = (j + faas) × max piste, faas nihkub igal real 1/`fill_staggers` (4) võrra. Reaotsale lähemal kui 0,4 mm läbistust ei tehta.
- Puhastus eemaldab ainult alla 0,15 mm pisted. Tsentreerimine käib täisarvulise nihkega (0,1 mm).

## 2. Satiin
1. Rasterda täht (0,02 mm/px), `skeletonize`, ehita pikslite graaf (diagonaal ainult siis, kui 4-naabri teed pole). Joone laius = 2·pindala/ümbermõõt.
2. Eemalda otsaga lõppevad harud < 1,8 × laius (nurgaartefaktid). Alles jääb haru, mis on üle 0,9 × laiuse pikk ja jätkab teist haru sirgelt (±14°): see on päris ots (d, b püstkriips kõhu all).
   Silmus, mis algab ja lõpeb samas ristumiskohas (a, b, d kõht), on sammas; ainult alla 2 × laiuse jupp ristumiskoha sees jäetakse ära.
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

## 3. Muud täidised

| `stitch` / võti | Mis tuleb | Seaded |
|---|---|---|
| `fill_border` > 0 (tatami või contour juures) | täidis + satiinääris serval; täidis läheb 0,3 mm ääriste alla | laius mm (2–4); nurgad pöördega (kuni 135°), sisenurgas (südame lohk) keskjoon kaarega; ring algab sirge külje keskelt |
| `contour` | servaalustikk; read servaga paralleelselt sissepoole, reavahe `fill_spacing`; üks pidev spiraal, kuni kujund on üks tükk ilma aukudeta (siis ringid eraldi, lähim enne) | `fill_spacing`, `fill_maxlen`, `fill_border` |
| `applique` | paigutusjoon → **peatus** „aseta kangas“ → kinnitusjoon 0,5 mm seest → **peatus** „lõika kangas“ → satiinääris | `applique_border` (3 mm) |
| `cross` | ristid ühisel ruudustikul (algus mustri vasakus ülanurgas); ruut võetakse, kui kujund katab sellest ≥ 50%; read maona, naaberristid ühendatakse ühise nurga kaudu | `cross_size` (2 mm) |

Peatus on värvivahetus sama niidiga; `meta.json` → `stops` ja `blocks` (niidiplokk → värvitabeli rida) ning PDF ütleb peatused esilehel. Optimeerija neid ei muuda (ainult tatami nurk `--angles` korral).
