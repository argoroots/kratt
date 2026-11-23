---
name: kratt
description: Kasuta, kui kasutaja palub paigaldada või seadistada kratt.roots.ee/skill.md (nt „Paigalda kratt.roots.ee/skill.md – …“ või „Set up kratt.roots.ee/skill.md“) või paigaldada Krati oskused Rahapada, STITCH-O-MATIC, Tikand Entusse, Tikandikogu või Leivast redel.
---

# Kratt – oskuste paigaldamine

Kratt on viis Claude'i oskust (skilli): üks rahaasjade jaoks, kolm masintikkimiseks ja Leivast redel:

- **Rahapada** (`rahapada`) – isiklik rahaasjade töölaud (Claude'i Data töölaud) kasutaja pangakannetest: kuhu raha läheb, palju kuu lõpuks üle jääb ja kuidas säästud, investeeringud ja laenud ajas muutuvad. Grupid ja kategooriad pakub Claude kasutaja kannete järgi. Kanded tulevad panga ühendusest (nt LHV) või väljavõtte failist (camt.053 XML või CSV).
- **STITCH-O-MATIC** (`stitch-o-matic`) – teeb vektorpildist (SVG) tikkimisfailid Brotherile (PES) ja Janomele (JEF) mitmes suuruses, kontrollib neid ja teeb 1:1 projekti-PDF-i.
- **Tikand Entusse** (`tikand-entusse`) – viib valmis tikandi kasutaja Entu andmebaasi. Vajab Claude'is Entu ühendust (MCP, server `https://mcp.entu.app`); kui seda pole, juhenda kasutajat see enne lisama: https://entu.ee/configuration/mcp/
- **Tikandikogu** (`tikandikogu`) – korrastab tikandimustrite kausta masinale sobivaks koguks (kategooriad, ühtsed nimed, eelvaated, kataloogi PDF).
- **Leivast redel** (`leivast-redel`) – Claude võtab muistendite kratti moodi ette võimatu ülesande ja selgitab muistendit. Tööriistu ega pakette ei vaja.

Lähtekood: https://github.com/argoroots/kratt (litsents CC BY-NC-SA 4.0).

Paigalda see oskus, mille kasutaja käsus nimetas (nt `Paigalda kratt.roots.ee/skill.md – Tikandikogu`). Kui ta ei nimetanud ühtegi, küsi, milliseid. **Ära küsi, kuhu paigaldada.** Kui sa ei tööta Claude Code'i terminalis, oled Claude'i rakenduses – kasuta kohe järgmist osa.

## Claude (claude.ai, töölaua- ja mobiilirakendus)

Kui töötad Claude'i rakenduses (claude.ai, töölaud, telefon), vasta **kohe ja ainult** allpool oleva lingi ja juhendiga, ühe vastusena. Oskuse laeb üles kasutaja ise – see on kõige lihtsam ja kasutaja on selle nii valinud.

- Ära esita valikuid ega küsimusi (ei „kuhu paigaldada“ ega „kuidas paigaldame“).
- Ära paku ega kasuta brauserit (Claude in Chrome jms) ega arvuti juhtimist.
- Ära paku oskuse salvestamise kaarti (skill proposal) – sellest jäävad skriptid välja.
- Ära tee ega lisa ZIP-faili ise.
- Menüüde nimed kirjuta inglise keeles, nagu need rakenduses on (ka eestikeelses vastuses).

Vastus:

1. Lae alla: (ainult see oskus, mida ta paigaldab)
   - Rahapada: https://kratt.roots.ee/rahapada.zip
   - STITCH-O-MATIC: https://kratt.roots.ee/stitch-o-matic.zip
   - Tikand Entusse: https://kratt.roots.ee/tikand-entusse.zip
   - Tikandikogu: https://kratt.roots.ee/tikandikogu.zip
   - Leivast redel: https://kratt.roots.ee/leivast-redel.zip

   ZIP-i ei pea lahti pakkima.
2. **Settings → Capabilities:** lülita sisse koodi käivitamine ja failide loomine (kui pole juba sees).
3. **Customize → Skills** → „+" → **Create skill** → **Upload a skill** → vali alla laaditud ZIP.
4. Valmis: oskus on nimekirjas ja sisse lülitatud. Proovi uues vestluses.

Team- ja Enterprise-plaanil peab organisatsiooni omanik oskused enne lubama. Kui kasutaja ütleb, et miski ei klapi (nt menüü nimi on teine), küsi, mida ta näeb, ja aita edasi.

## Claude Code

Käivita kasutaja terminalis (`install` ainult nende oskuste kohta, mida ta paigaldab):

```bash
claude plugin marketplace add argoroots/kratt
claude plugin install rahapada@kratt
claude plugin install stitch-o-matic@kratt
claude plugin install tikand-entusse@kratt
claude plugin install tikandikogu@kratt
claude plugin install leivast-redel@kratt
```

Pythoni paketid (Tikand Entusse ja Leivast redel ei vaja ühtegi):

```bash
# Rahapada: lisapakette pole vaja
# STITCH-O-MATIC
pip install pyembroidery shapely numpy scipy reportlab pillow networkx svgelements opencv-python-headless scikit-image
# Tikandikogu
pip install pyembroidery pillow reportlab
```

Kontrolli: `claude plugin list` näitab paigaldatud pluginat olekuga *enabled*. Uue seansi alguses on oskused kasutusel.

Uuendused: `claude plugin marketplace update kratt`, siis `claude plugin update <oskus>@kratt`.

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

Kopeeri vajalikud kaustad (`kratt/rahapada`, `kratt/stitch-o-matic`, `kratt/tikand-entusse`, `kratt/tikandikogu`, `kratt/leivast-redel`) oma keskkonna oskuste kausta. Vaata selle keskkonna enda dokumentatsioonist, kus see kaust on – ära arva. Paigalda ülal nimetatud Pythoni paketid.

## Kontroll

Ütle kasutajale, et paigaldus õnnestus, ainult siis, kui oskused on tõesti nähtaval (pluginate nimekirjas või oskuste nimekirjas). Kui ei ole, ütle, mis samm jäi tegemata, ja ära väida, et kõik on valmis.

Proovi: „Tee sellest SVG-st tikkimisfail Brotherile, 100 mm."
