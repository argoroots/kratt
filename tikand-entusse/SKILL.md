---
name: tikand-entusse
description: Pane valmis tikand (masinafailid, projekti-PDF, eelvaade, lähte-SVG) kasutaja Entu andmebaasi; kontrollib ja vajadusel loob tikandi objektitüübi, küsib asukoha, kontrollib faile allalaadimisega.
---

# Tikand Entusse

Viib valmis tikandi (nt STITCH-O-MATICu tulemus) kasutaja **Entu** andmebaasi. Igal kasutajal on Entu erinev: ära eelda ühtegi andmebaasi, objektitüüpi, parameetrit ega ülemobjekti – vaata järele ja küsi. Kõik lugemine ja kirjutamine käib Entu MCP tööriistadega; failide baidid laaditakse üles shellist. Vasta kasutaja keeles; Entu terminid eesti keeles: objekt, objektitüüp, parameeter, ülemobjekt, alam-objekt.

Kui Entu MCP-d pole ühendatud, ütle seda ja juhenda kasutajat see lisama: server `https://mcp.entu.app`, juhend https://entu.ee/configuration/mcp/ – ära tee midagi mööda.

## 1. Andmebaas
Vaata, mis andmebaasid Entu tööriistades on (`db` valikud). Kui neid on mitu, küsi, millisesse. Loe skeem (`entu://<db>/schema`).

## 2. Objektitüüp
Otsi skeemist tikandite tüüpi: nimi või silt nagu embroidery, tikand, design, muster. Kui leiad:
- näita kasutajale tüübi nime ja parameetreid ning küsi, kas kasutada seda;
- kaardista failid ja väärtused **selle tüübi parameetritele** (tabel: mis läheb kuhu). Kui mõni vajalik parameeter puudub (nt eelvaate pilt või suurus), küsi, kas see lisada või jätta välja.

Kui ei leia, **paku loomist** ja näita plaani enne loomist. Ettepanek (nimed inglise keeles, sildid kasutaja keeles):

| Parameeter | Tüüp | List | Mis |
|---|---|---|---|
| `name` | string | | nimi |
| `category` | string | jah | kategooria, nt kaust ja alamkaust |
| `machine` | string | jah | masin (nt Brother, Janome) |
| `size` | number | jah | suurused mm-des |
| `file` | file | jah | masinafailid (PES, JEF …) |
| `original` | file | jah | lähte-SVG, projekti-PDF |
| `photo` | file | | eelvaade |
| `description` | string, markdown | | tehnika kirjeldus |

Küsi, kas kasutaja tahab midagi muuta (nimed, lisaparameetrid, masinate valikud). Loo ainult kinnituse järel: `create_entity_type`, siis iga parameeter `create_property_definition`. Kui andmebaasis on menüüd, küsi, kas uus tüüp lisada menüüsse. Enne loomist vaata, mida sarnased olemasolevad tüübid kasutavad (nt kirjelduse parameetri tüüp ja markdown), ja tee samamoodi.

## 3. Uus või olemasolev
Otsi nime järgi selle tüübi objektide seast (`search_entities`). Kui leiad, küsi: **asendada** failid ja väärtused või teha **uus**? Näita leitud objekti linki.

## 4. Asukoht (uue puhul alati küsi)
Küsi, mille alla tikand panna. Paku valikuks kohti, kus selle tüübi objekte juba on (nende ülemobjektid), ja võimalust anda muu. Ära vali ise.

## 5. Mis läheb Entusse
Küsi või kinnita: masinafailid, projekti-PDF, lähte-SVG, eelvaatepilt (keskmine suurus). Kontrollpildid ja tööfailid ei lähe. Kategooria, masin(ad), suurused – võta failidest või küsi.

## 6. Kirjeldus
Lühike, kasutaja keeles, markdownis (kui parameeter seda toetab): värv(id), suurused, kangas ja tugimaterjal, tabel osa → tehnika, tõmbekompensatsioon. Kirjuta ainult seda, mis on projekti-PDF-is või kasutaja öeldud. Lingid teistele objektidele üldkujul `[Nimi](<objekti link>)`.

## 7. Väärtused
- **Uus:** üks `create_entity` kõigi mittefailiväärtustega (sh `_parent`).
- **Asendamine:** `get_entity`, siis üks `update_entity` (`valueId`-ga asendus). Väärtuste id-d muutuvad iga asenduse järel – loe objekt enne iga muutmist uuesti.

## 8. Failid
Iga faili kohta üks `add_file` (asendamisel vana väärtuse `valueId`). Vastuses on `upload.url` ja `upload.headers`. Laadi kohe üles, kasutades **täpselt neid päiseid**, mis vastuses on:

```bash
# put.sh <fail> <url> <content-type> <content-disposition> [acl]
curl -sS -o /dev/null -w '%{http_code}\n' -X PUT --data-binary "@$1" \
  ${5:+-H "ACL: $5"} -H "Content-Type: $3" -H "Content-Disposition: $4" "$2"
```
Kirjuta URL enne faili või muutujasse (pikk, `&`-märkidega) – ära pane seda käsitsi osadest kokku. Ootus: `200`. URL aegub (vaata `expires`).

Kui üleslaadimine ebaõnnestus, jääb objektile tühi fail: eemalda see väärtus (`delete_property`) ja proovi uuesti.

## 9. Kontroll (kohustuslik)
Iga faili kohta `get_file_url` → lae alla → `cmp` kohaliku failiga. Raporteeri ainult kontrollitud tulemus: „N faili, kõik baidi kaupa samad“ või mis ebaõnnestus. Ära ütle, et midagi on tehtud, kui kontroll pole läbi läinud.

## 10. Lõpuks
Üks lause ja objekti link.

## Reeglid
- Muuda ainult seda, mida kasutaja palus. Objektitüüpe, parameetreid ja objekte loo või kustuta ainult tema kinnitusel.
- Ühe objekti kõik väärtused ühe kutsega; ainult eemaldamine eraldi.
- Ära kopeeri andmeid ühest andmebaasist teise.
