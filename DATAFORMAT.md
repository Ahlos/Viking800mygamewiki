# Stödda dataformer i version 1.0

Källfilens namn bestämmer kategori. Exempel: en post i `characters.json` blir en
personartikel och en post i `military.json` blir ett militärt objekt.

## Listor och samlingsobjekt

En enkel lista:

```json
[
  {"id": "PER-000001", "name": "Exempelperson", "organization_ids": ["ORG-000001"]}
]
```

Samma samling med omslutande nyckel:

```json
{
  "characters": [
    {"id": "PER-000001", "name": "Exempelperson"}
  ]
}
```

En karta med ID som nyckel:

```json
{
  "characters": {
    "PER-000001": {"name": "Exempelperson"}
  }
}
```

ID-nycklar i kartor ska likna `PER-000001`: bokstav först, ett prefix och bindestreck.
Nyckeln används som artikel-ID om posten saknar `id`. Om både nyckel och `id`
finns måste de vara identiska. `id` i en post får i övrigt vara en valfri icke-tom
sträng. Utfilernas namn skapas säkert av generatorn, inte som sökvägar från ID.

Kapslade samlingar fungerar också:

```json
{
  "navy": {
    "ships": [{"id": "SHIP-000001", "name": "Exempelfartyg"}]
  },
  "units": [{"id": "MIL-000001", "name": "Exempelenhet"}]
}
```

Generatorn letar rekursivt i samlingsbehållare. En post känns igen genom `id`, ett
identifierarfält nedan, en ID-kartnyckel eller textfält som `name`, `title`, `namn`
eller `rubrik`. Även ett platt objekt utan ID kan bli en post. När en post har
identifierats stannar sökningen i just den posten; dess kapslade data blir fält,
inte ytterligare artiklar. En omslutande samlingsbehållare bör därför inte själv
ha `id`, `name` eller andra artikelliknande identifierare.

Om en artikel saknar ID får den ett deterministiskt `LOCAL-...` baserat på filnamn
och JSON-sökväg. Detta ger en varning. ID:t skrivs aldrig tillbaka till sparningen
och kan ändras om du flyttar eller ordnar om posterna. Använd riktiga, stabila ID:n
för beständiga korslänkar. Dubblerade artikel-ID:n är fel även över kategorigränser.

## Identifierarfält och rubriker

`id` rekommenderas alltid. Följande alternativa identifierare stöds per fil:

| Fil | Alternativa identifierare |
|---|---|
| characters | character_id, person_id |
| organizations | organization_id |
| projects | project_id |
| military | unit_id, ship_id, object_id |
| locations | location_id |
| resources | resource_id |
| events | event_id |
| decisions | decision_id |

Titel väljs från `name`, `title`, `label`, `namn` eller `rubrik`, i den ordningen.
Finns ingen titel används ID. Ingress visas från `summary`, `description` eller
`overview`. Alla andra fält återges i faktatabellen med bibehållna värden. Originalets
fältnamn kan läsas i den formaterade JSON-visningen på källsidan.

## Korsreferenser och relationer

Exakta strängvärden som matchar ett känt ID länkas automatiskt. ID-liknande
referenser såsom `PER-000001` kan även länkas mitt i löptext. Fält som slutar med
`_id` och `_ids` används för kontroll av saknade mål och inkommande hänvisningar.
Kampanj-, sparnings- och turidentifierare behandlas inte som artikelreferenser.
`null` och `UNKNOWN` får stå kvar som okända värden.

```json
{
  "relationships": [
    {
      "id": "REL-000001",
      "source_id": "PER-000001",
      "relation_type": "samarbetar med",
      "target_id": "PER-000002"
    }
  ]
}
```

Relationen visas på båda berörda artiklarna med sin ursprungliga riktning. Generatorn
gissar inte om en relation ska vara symmetrisk. Kända ID:n för regler, konsekvenser
och andra stödkällor länkas till motsvarande del av källsidan.

## Tidslinje

```json
{
  "entries": [
    {"date": "2030-04-12", "event_id": "EVT-000001", "turn": 12},
    {"title": "Ännu inte daterat", "date": null}
  ]
}
```

Datum läses från `date`, `game_date`, `start_date` eller `datum`, i den ordningen.
Händelse- och beslutsartiklar tas också med. En tidslinjepost med `event_id`,
`decision_id`, `entity_id` eller ett känt `id` får länk till målet.
Exakt samma kombination av datum, titel och länk visas en gång. Olika titlar eller
datum behålls; generatorn löser inte motsägelser genom att välja en källa.
`turn` eller `turn_id` visas om det finns.

## Wikiindex och övriga filer

```json
{
  "articles": [
    {"id": "WIKI-000001", "title": "Indexrubrik", "entity_id": "PER-000001"}
  ]
}
```

Wikiindex blir en sökbar källsida och dess kända referenser länkas till artiklar.
En alternativ indexrubrik ersätter inte personens sparade namn. Ett okänt
`entity_id` ger en varning. Indexet styr inte vilka fakta eller kategorier som skapas.

Manifest läses först och visas som källdata, men styr inte filåtkomst. Version 1
validerar inte manifestspecifika versionsregler, filhashar eller UPDATE-kedjor.
Rapportens SHA-256-värden är en dokumentation av lästa bytes, inte ett bevis på kanon.

Politik, ekonomi, relationer, konsekvenser, regler och öppna frågor behålls på sina
källsidor. `game_state` visas även på huvudsidan. Samtliga källor ingår i sökindexet.
JSON-fälten återges som text, tabeller och listor. HTML och Markdown i data körs eller
tolkas inte som formatering. Internetadresser blir vanlig text.
