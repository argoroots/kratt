---
name: kratt
description: Kasuta, kui kasutaja palub seadistada kratt.roots.ee/skill.md või paigaldada tikkimise oskused STITCH-O-MATIC, Tikand Entusse või Tikandikogu.
---

# Kratt – tikkimise oskuste paigaldamine

Kratt on kolm Claude'i oskust (skilli) masintikkimiseks:

- **STITCH-O-MATIC** (`stitch-o-matic`) – teeb vektorpildist (SVG) tikkimisfailid Brotherile (PES) ja Janomele (JEF) mitmes suuruses, kontrollib neid ja teeb 1:1 projekti-PDF-i.
- **Tikand Entusse** (`tikand-entusse`) – viib valmis tikandi kasutaja Entu andmebaasi. Vajab Claude'is Entu ühendust (MCP, server `https://mcp.entu.app`); kui seda pole, juhenda kasutajat see enne lisama: https://entu.ee/configuration/mcp/
- **Tikandikogu** (`tikandikogu`) – korrastab tikandimustrite kausta masinale sobivaks koguks (kategooriad, ühtsed nimed, eelvaated, kataloogi PDF).

Lähtekood: https://github.com/argoroots/kratt (litsents CC BY-NC-SA 4.0).

Paigalda see oskus, mille kasutaja käsus nimetas (nt `Set up kratt.roots.ee/skill.md – Tikandikogu`). Kui ta ei nimetanud ühtegi, küsi, milliseid. Vali allpool juhend selle keskkonna järgi, kus sa töötad.

## Claude Code

Käivita kasutaja terminalis (`install` ainult nende oskuste kohta, mida ta paigaldab):

```bash
claude plugin marketplace add argoroots/kratt
claude plugin install stitch-o-matic@kratt
claude plugin install tikand-entusse@kratt
claude plugin install tikandikogu@kratt
```

Pythoni paketid (Tikand Entusse ei vaja ühtegi):

```bash
# STITCH-O-MATIC
pip install pyembroidery shapely numpy scipy reportlab pillow networkx svgelements opencv-python-headless scikit-image
# Tikandikogu
pip install pyembroidery pillow reportlab
```

Kontrolli: `claude plugin list` näitab paigaldatud pluginat olekuga *enabled*. Uue seansi alguses on oskused kasutusel.

Uuendused: `claude plugin marketplace update kratt`, siis `claude plugin update <oskus>@kratt`.

## Claude (claude.ai, töölaua- ja mobiilirakendus)

Kui töötad Claude'i rakenduses, ära küsi, kuhu paigaldada – kasuta seda juhendit. Menüüde nimed on ingliskeelsed, nagu Claude'i rakenduses: kirjuta need samamoodi (ka eestikeelses vastuses), et kasutaja leiaks need üles. Oskuse laeb üles kasutaja ise. Ära tee ZIP-i ise, ära lisa faili ega proovi brauseriga üles laadida: anna lihtsalt link ja juhend, **ühe vastusena**:

1. Lae alla: (ainult see oskus, mida ta paigaldab)
   - STITCH-O-MATIC: https://kratt.roots.ee/stitch-o-matic.zip
   - Tikand Entusse: https://kratt.roots.ee/tikand-entusse.zip
   - Tikandikogu: https://kratt.roots.ee/tikandikogu.zip

   ZIP-i ei pea lahti pakkima.
2. **Settings → Capabilities:** lülita sisse koodi käivitamine ja failide loomine (kui pole juba sees).
3. **Customize → Skills** → „+" → **Create skill** → **Upload a skill** → vali alla laaditud ZIP.
4. Valmis: oskus on nimekirjas ja sisse lülitatud. Proovi uues vestluses.

Team- ja Enterprise-plaanil peab organisatsiooni omanik oskused enne lubama. Kui kasutaja ütleb, et miski ei klapi (nt menüü nimi on teine), küsi, mida ta näeb, ja aita edasi.

## Tikand Entusse: Entu ühendus

Tikand Entusse vajab Claude'is Entu ühendust. Vaata, kas sinu tööriistade seas on Entu tööriistad (nimes „Entu“, nt `search_entities`). Kui on, pole midagi vaja teha. Kui ei ole, lisa samasse vastusesse:

- **Claude'i rakendus:** **Customize → Connectors** → „+" → **Add custom connector** → nimi `Entu`, aadress `https://mcp.entu.app` → **Add** → **Connect**, logi Entusse sisse ja vali andmebaasid.
- **Claude Code:** `claude mcp add --transport http entu https://mcp.entu.app`, siis logi brauseris Entusse sisse.

Täpsem juhend: https://entu.ee/configuration/mcp/

## Teised agendid (Codex, Cursor jt)

Kui sinu keskkond toetab Agent Skills vormingut (kaust, milles on `SKILL.md`):

```bash
git clone https://github.com/argoroots/kratt.git
```

Kopeeri vajalikud kaustad (`kratt/stitch-o-matic`, `kratt/tikand-entusse`, `kratt/tikandikogu`) oma keskkonna oskuste kausta. Vaata selle keskkonna enda dokumentatsioonist, kus see kaust on – ära arva. Paigalda ülal nimetatud Pythoni paketid.

## Kontroll

Ütle kasutajale, et paigaldus õnnestus, ainult siis, kui oskused on tõesti nähtaval (pluginate nimekirjas või oskuste nimekirjas). Kui ei ole, ütle, mis samm jäi tegemata, ja ära väida, et kõik on valmis.

Proovi: „Tee sellest SVG-st tikkimisfail Brotherile, 100 mm."
