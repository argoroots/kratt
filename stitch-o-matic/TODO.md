# Veel tegemata tehnikad

Tikkimise võtted, mida `digitize.py` veel ei tee. Iga rea juures on, mis see on, millal seda vaja on ja mida teostus nõuab. Kui pilt vajab mõnda neist, ütle seda kasutajale enne digiteerimist: kas lihtsustame või teeme tehnika enne valmis.

## Täidised

| Tehnika | Mis ja millal | Mida teostus vajab |
|---|---|---|
| Juhitud täide (guided fill) | tatami read painduvad mööda antud joont (lint, juuksed, lehed) | juhtjoon SVG-s või plaanis; read juhtjoone paralleelnihketena, read lõigatakse kujundiga |
| Radiaalne täide | read kiirtena ühest punktist (päike, lill, nupp) | keskpunkt plaanis; kiirte vahe välisservas = reavahe, keskel hõrendus (muidu kuhjub) |
| Gradient / tiheduse üleminek | tihedus muutub ühest servast teise, kangas paistab läbi; ka kahe värvi sulandumine | reavahe kohapõhiseks; kahe värvi korral read vaheldumisi, osakaal muutub |
| Meander / stippling | juhuslik looklev sirgpiste, kerge taust või tekstuur | ruumi täitev kõver (nt Hilberti või juhuslik kasv), joonte vahe ≈ 1–2 mm |
| Mustriga täited (tartan, pilu, reljeef) | tatami, mille läbistused või piste pikkus moodustavad mustri | läbistuste võrk mustri maski järgi; tartan = mitu kihti eri nurga ja värviga |
| Kahekordne / ristuv tatami | paksem või tekstuuriga pind | teine kiht teise nurgaga; tihedus kokku ≤ 8,5 mm/mm² |

## Satiin

| Tehnika | Mis ja millal | Mida teostus vajab |
|---|---|---|
| Muutuva laiusega satiin (kalligraafia, sulejoon) | sammas pakseneb ja kitseneb | on osaliselt olemas (laius tuleb kujundist); vaja käsitsi antud laiuse kõverat jooneteele |
| Siksak (hõre satiin) | kerge ääris, aplikatsiooni ajutine kinnitus | sama satiin, tihedus 1–2 mm |
| E-piste / tekk-piste (blanket) | aplikatsiooni äär „käsitöö“ stiilis, kangaserv | ühe serva sirgpiste + risti „hambad“ |
| Juhusliku laiusega satiin | karv, rohi, loomulik serv | sisemise serva punkte nihutatakse juhuslikult (seemnega, et suurused jääks samaks) |
| Jagatud satiin (split satin) | lai sammas (> 7 mm) satiinina, mitte tatamina | on osaliselt olemas (`satin_split`); vaja mustriga vahepunkte |

## Jooned

| Tehnika | Mis ja millal | Mida teostus vajab |
|---|---|---|
| Bean stitch (3× sirgpiste) | olemas (`run_passes`) | – |
| Kaunistuspisted (ripple, motiivjoon) | joon motiividest (lehed, lainete kaared) | motiivi kordamine mööda teed, motiivi suurus pikkuse järgi |
| Laineline (ripple) täide | kontsentrilised lained ühest punktist või joonest | sarnane kontuuritäitele, ainult sirgpiste ja suurem vahe |
| Peen tekst (< 4 mm) | väike kiri | 60 wt niit ja 65/9 nõel; satiini tihedus ja laiuse min väiksemaks; vaja niidi paksuse seadet |

## Ruumilisus ja eriliigid

| Tehnika | Mis ja millal | Mida teostus vajab |
|---|---|---|
| 3D vaht (puff) | kõrge kumer satiin (mütsid) | vahu alla paigutusjoon + peatus; satiin tihedam (0,25–0,3 mm), suletud otsad; tatamit vahule ei tehta |
| FSL (free-standing lace) | pits, mis jääb pärast vees lahustuva kile eemaldamist püsti | kõik osad peavad olema ühendatud võrgustikuga; kaks kihti alustikku risti; kontroll, et pole lahtisi saari |
| In-the-hoop (ITH) | raamis valmistatud ese (kotike, võtmehoidja) | mitu peatust ja paigutusjoont, samm-sammuline juhend PDF-is |
| Mitu raami (multi-hoop) | tikand suurem kui raam | jaotus kattuvusega, joondusmärgid, eraldi failid ja järjekord |
| Mütsi järjekord | kumer pind | keskelt väljapoole ja alt üles, vähem pikki üleminekuid |
| Niidi paksus (40 / 60 wt, metallik) | eri niidid | parameetrite komplektid nagu `--fabric`, nt `--thread 60` |
| Värvide segamine (blending) | varjund kahe niidiga | kaks kihti tatamit, kummagi tihedus muutub vastupidi |

## Mida tuleb enne igat uut tehnikat teha

1. Kirjuta KNOWLEDGE.md-sse reeglid ja põhjused (vahemikud, mida allikad ütlevad).
2. Teosta `digitize.py` funktsioonina, mis tuleb plaanist (`stitch` või uus võti); vaikimisi väljund ei tohi muutuda (regressioon).
3. Proovifail: tehnika eraldi, paar suurust/seadet kõrvuti; tihedusekaart ja eeldatav välimus üle.
4. PDF-i „Kuidas on tehtud“ lause ja vajadusel peatuse juhend.
