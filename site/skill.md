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

Siin ei saa sa oskust ise paigaldada: ZIP-i laeb üles kasutaja. Sinu töö on teha see talle võimalikult lihtsaks. Juhenda samm-sammult, üks samm korraga, ja oota iga sammu järel, et kasutaja ütleks, et see on tehtud või mis takerdus.

1. **ZIP.** Anna oskuse ZIP-i link (ainult selle oskuse, mida ta paigaldab):
   - STITCH-O-MATIC: https://kratt.roots.ee/stitch-o-matic.zip
   - Tikand Entusse: https://kratt.roots.ee/tikand-entusse.zip
   - Tikandikogu: https://kratt.roots.ee/tikandikogu.zip

   Ütle, et ZIP-i ei pea lahti pakkima.
2. **Koodi käivitamine.** Seaded → **Capabilities**: koodi käivitamine ja failide loomine peab olema sees. Kui on juba sees, mine edasi.
3. **Üleslaadimine.** **Customize → Skills** → „+" → **Create skill** → **Upload a skill** → vali alla laaditud ZIP.
4. **Kontroll.** Oskus peab nüüd olema oskuste nimekirjas ja sisse lülitatud.

Team- ja Enterprise-plaanil peab organisatsiooni omanik oskused enne lubama; kui kasutaja ei leia Skills-osa, ütle seda.

Kui menüü nimi kasutaja ekraanil erineb, küsi, mida ta näeb, ja juhata selle järgi – ära arva.

## Tikand Entusse: Entu ühendus

Kui kasutaja paigaldab Tikand Entusse, kontrolli pärast oskuse paigaldamist, kas Entu MCP on ühendatud: sinu tööriistade seas on Entu tööriistad (nimes „Entu“, nt `search_entities`, `get_entity`, `add_file`). Kui on, ütle seda ja oled valmis.

Kui ei ole, juhenda kasutajat samm-sammult, üks samm korraga:

**Claude'i rakendus (claude.ai, töölaud):**
1. **Customize → Connectors** → „+“ → **Add custom connector**.
2. Nimi `Entu`, aadress `https://mcp.entu.app` → **Add**.
3. **Connect** → logi Entusse sisse ja märgi andmebaasid, mida Claude tohib kasutada.
4. Uues vestluses peab Entu konnektor olema sisse lülitatud.

**Claude Code:**
```bash
claude mcp add --transport http entu https://mcp.entu.app
```
Seejärel logi brauseris Entusse sisse.

Täpsem juhend: https://entu.ee/configuration/mcp/. Claude'il on ainult kasutaja enda Entu õigused. Kui menüü nimed kasutaja ekraanil erinevad, küsi, mida ta näeb.

## Teised agendid (Codex, Cursor jt)

Kui sinu keskkond toetab Agent Skills vormingut (kaust, milles on `SKILL.md`):

```bash
git clone https://github.com/argoroots/kratt.git
```

Kopeeri vajalikud kaustad (`kratt/stitch-o-matic`, `kratt/tikand-entusse`, `kratt/tikandikogu`) oma keskkonna oskuste kausta. Vaata selle keskkonna enda dokumentatsioonist, kus see kaust on – ära arva. Paigalda ülal nimetatud Pythoni paketid.

## Kontroll

Ütle kasutajale, et paigaldus õnnestus, ainult siis, kui oskused on tõesti nähtaval (pluginate nimekirjas või oskuste nimekirjas). Kui ei ole, ütle, mis samm jäi tegemata, ja ära väida, et kõik on valmis.

Proovi: „Tee sellest SVG-st tikkimisfail Brotherile, 100 mm."
