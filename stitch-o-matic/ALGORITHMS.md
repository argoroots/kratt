# Algoritmid

Kuidas `scripts/` teeb pisted: samm-sammult, koos arvudega. Loe seda, kui parandad koodi või kui tulemus ei vasta ootusele. Tavalise tikandi tegemiseks piisab SKILL.md-st. Reeglid ja nende põhjused on KNOWLEDGE.md-s.

## 1. Tatami
- 0,1 mm võrk: rea samm on 0,1 mm kordne ja rea otspunktid ümardatakse oma rea joonele (`snap_to_grid()`). Muu samm teeb triipe.
- Kujundi osad tikitakse samas suunas ülevalt alla, ülemise serva järjekorras; osade vahel lõige ja hüpe.
- Iga rida algab eelmise lõpule lähemast otsast. Järgmise reani minnakse otse, kui see jääb kujundi sisse; pikk üleminek jagatakse ≤ 4 mm pisteteks. Osa pikendatakse ühe reaga ainult lõpus.
- Läbistused on ühisel võrgul: x = (j + faas) × max piste, faas nihkub igal real 1/`fill_staggers` (4) võrra. Reaotsale lähemal kui 0,4 mm läbistust ei tehta.
- Puhastus eemaldab ainult alla 0,15 mm pisted. Tsentreerimine käib täisarvulise nihkega (0,1 mm).

## 2. Satiin
1. Rasterda täht (0,02 mm/px), `skeletonize`, ehita pikslite graaf (diagonaal ainult siis, kui 4-naabri teed pole). Joone laius = 2·pindala/ümbermõõt.
2. Eemalda otsaga lõppevad harud < 1,8 × laius (nurgaartefaktid). Alles jääb haru, mis on üle 0,9 × laiuse pikk ja jätkab teist haru sirgelt (±14°): see on päris ots (d, b püstkriips kõhu all).
   Silmus, mis algab ja lõpeb samas ristumiskohas (a, b, d kõht), on sammas; ainult alla 2 × laiuse jupp ristumiskoha sees jäetakse ära.
3. Ristumisel ühenda kaks vastassuunalist haru üheks läbivaks sambaks (suunad vähemalt ~148° lahku). Kolme haru ristumisel, kus mõlemad harud on üle 8 × laiuse pikad, piisab ~130°: hargi U kaardub ristumisse ja peab jääma üheks sambaks, vars lõpeb selle vastu. Kahe joone kohtumisel läheb pikem läbi välisservani, teine lõpeb selle serval.
4. **Läbiv ots** läheb välisservast üle `comp` võrra (+ laienduse võrra, kui sammas on alla `satin_min`), sest risti olev sammas on samuti nii palju laiem (nt E püstkriips).
5. **Nurgad:** kuni `satin_mitre` (60°) pöörde korral jääb sammas tervikuks ja pisted pööravad ühe laiuse jooksul nurga poolitaja kaudu. Teravam nurk (täisnurk, A tipp) lõigatakse kaheks (mitte otsale lähemal kui 1,4 × laius) ja läheb edasi nagu punkt 3.
6. **Vaba ots:** skeleti saba lõigatakse ära ja sammas pikeneb sirgelt tipuni. Laial sambal (≥ 2,5 mm) kõverdub skelett otsas nurga poole: kui viimane tükk (lühem kui 1,5 × laius) pöörab üle 15°, jäetakse see ära ja ots jätkub samba suunas. Viimase laiuse jooksul pööravad pisted otsa serva suunaliseks (pikim sirge kontuurilõik tipu juures; üle 60° viltu jäävad pisted risti). Iga piste lõigatakse kontuuriga; alla 0,25 mm pisted tipus jäetakse ära. Lehvikut ei tehta.
7. **Laius:** ≤ min(1,12 × mediaan; 0,62 × laius), nurga pööramisel jagatud nurga koosinusega. Kontuurist väljas (läbiv ots) kantakse edasi viimane täislaiusega piste. Kompensatsioon `comp` + `satin_pull_pct` %, vabad otsad `satin_push` mm lühemaks. Alla `satin_min` (1,0 mm; froteel 1,5) sambad laiendatakse, aga kokku kõige rohkem `satin_widen_max` (0,3 mm) võrra, et väikese kirja augud lahti jääks. Kitsenev sammas (laius kasvab mööda sammast ühtlaselt: 90. protsentiil > 1,6 × 10. ja korrelatsioon > 0,85) piiratakse kohaliku mediaaniga ±1,5 laiuse ulatuses, mitte kogu samba mediaaniga; muidu lõigatakse lai ots keskmise laiuseni ja jääb vaheketäiteks.
8. **Tihedus:** järgmine piste tuleb, kui enim liikunud külg (kurvi väliskülg) on eelmisest pistest risti mõõtes `satin_spacing`/2 kaugusel.
   **Üle serva ei lähe:** iga satiinipiste lõigatakse kontuuri + kompensatsiooni (+ õhukese satiini laiendus + 0,1 mm) järgi, ümara puhvriga (nurga puhver ulatuks teravates tippudes kaugele välja). Kus keskjoon jookseb kujundist välja (M, N, W, A tipud, läbivad otsad), ei jää piste täislaiusena õhku.
   **Pistete suund** arvutatakse keskjoonest ±pool laiust ulatuses, mitte ainult punktist. Kui keskjoonel on murdekoht (nt seal, kus haru ühineb), pööravad pisted järk-järgult; muidu pöörduvad nad korraga ja välisküljele jääb lahtine kiil (EMTA hargi U põhi, südame tipp).
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

## Täidise erijuhud

- **Äärisega täidise teravad tipud (< 60°):** äärise satiini nurgapiste võib olla kõige rohkem kaks korda poollaius, nii et tipp jääks paljaks. Täidis ulatub seal äärise alt tipuni: tipu ümber raadiusega `w/2 / sin(θ/2) − w + 0,4` (w = äärise laius).
- **Kontuuritäite keskkoht:** viimane ring jätab kuni ühe reavahe laiuse ava (ellipsil pilu pika telje suunas). Keskele tikitakse sirgpiste mööda kujundi pikka telge, kolme ringi kaugusele, kus ringide teravad otsad veel lahku jäävad. Auguga kujundil (rõngas) seda ei tehta.


- **Rõngas kontuuritäitega** (kujund ühe auguga): servast sissepoole minevad read ja augu ümber minevad read on kaks samakeskset perekonda; kumbki tikitakse ühe spiraalina (väljast sisse, siis keskelt augu poole), nii et ringide algust (õmblust) pole.
- **Spiraali algus:** esimene ring tikitakse enne triivi järgmisele täis, muidu jääks alguse taha serva üks reavahe laiune kiil.
- **Sirgpiste kõveral:** piste on lühem, kui muidu kalduks joonest üle 0,05 mm (`run_tol`).
- **Satiini juuksenõel:** kui pööre on väljast ümar (ükski välisserva tipp ei pöördu üle 40°, kokku ≥ 90°) ja seest terav, jääb sammas üheks ja pisted pöörduvad lehvikuna ümber sisemise tipu. Mõlemalt poolt terav pööre (päris nurk) jagatakse endiselt sammasteks.
- **Kitsas V (haarad lähevad sõlmest kõrvuti välja, vahe alla 70°):** kui tegeliku tipu (haarade sirgete osade keskjoonte lõikepunkt) juures on välisserv ümar, liidetakse haarad üheks sambaks läbi selle punkti ja lühike tipu jupp jäetakse ära; pisted pöörduvad seal lehvikuna. Terav tipp (mitre) jääb poolitatuks – proovis oli see parim. `satin_hairpin`: `auto` (vaikimisi), `fan` (alati üks sammas), `split` (alati kaks).
- **Alustikke liik** valitakse joonistatud laiuse järgi (veeru laius miinus 2 × kompensatsioon) ja servajooned mõõdetakse joonistatud servast: muidu sai 1,7 mm joon servajooned, mis jäid pärast kokkutõmbumist satiinist välja.
- **Sammas, mis lõpeb teise vastu** (A tipp, M keskel): pikeneb, kuni mõlemad küljed on teise sees; kui see läheks üle joonise serva, pikeneb nii kaugele, kui serva sees saab (varem jäi siis pikendamata ja tipu alla jäi kolmnurk).
- **Läbiv sammas** (E post nurgas) lõpeb joonise servas nagu vaba ots: sammast otsa ei tõmmata kokku (pisted on servaga paralleelsed), vaid lükatakse välja; risti kriipsu külg tõmbub kompensatsiooni võrra tagasi servani.

## Eeldatav välimus (preview.look)

Fail ei ole see, mis kangale jääb: satiin tõmbab kangast piste suunas kokku (selle vastu on tõmbekompensatsioon) ja lükkab sammast piki pikemaks. Eeldatav välimus teeb selle tagasi kanga enda arvudega:
- satiinisammas = järjestikused üle 0,8 mm pisted, mis pööravad iga kord üle 120° uude nõelapisti (kolmekordne sirgpiste läheb sama joont tagasi ja ei ole satiin);
- iga satiinipiste lüheneb kummastki otsast `comp × (1 + comp_stretch × (c − 0,5))` (c = |cos| venivuse suunaga), alla 1,5 mm pisted proportsionaalselt vähem, kõige rohkem 30 % pikkusest;
- sammas pikeneb otstest 0,4 × comp (keskelt 0, otstes täis);
- sirgpiste ja alustikk jäävad paika; satiin joonistatakse kumerana, sirgpiste ühtlase niidina, all kerge vari ja kanga tekstuur.
Arvud on hinnang (comp on eeldatav tõmme); kui proov näitab muud, muuda kanga kompensatsiooni, mitte pilti.
