# Verifiering av version 1.0

Verifierad 2026-09-10 i Windowsmiljö med den tillgängliga Python-tolken.

## Genomförda kontroller

- 18 automatiska Python-tester med verklig kommandoradskörning och temporära filer.
- Sju JavaScript-kontroller av sökning: namn, ID, kategorifilter, flera sökord,
  svenska tecken, tom sökning, inga träffar och rangordning av exakta träffar.
- Demobygge i strikt läge från alla 18 JSON-filnamn: 18 artiklar och inga varningar.
- 48 genererade HTML-sidor samt 1 566 lokala länkar och ankare kontrollerade.
- SHA-256 på samtliga 18 källfiler kontrollerad mot byggrapporten.
- Tester verifierar att generatorn inte ändrar källfiler eller skriver över en
  befintlig wiki, samt avvisar överlappande käll- och utdatamappar.
- HTML- och skriptinnehåll i JSON verifierat som text; sökindexet undviker råa
  avslutande script-taggar. ID:n kan inte användas som utgående filsökvägar.
- Testfall för saknade filer, okända referenser, ID-kartor, kapslade samlingar,
  alternativa ID-fält, `null`, ogiltig JSON, dubblerade nycklar, NaN och dubblerade ID:n.
- Separat kodgranskning hittade utebliven referenskontroll i samlingsbehållares
  metadata. Felet rättades och täcks av ett regressionstest för både varning och länk.
- Ziparkivets CRC, uppackad kommandoradskörning, tester och omgenerering kontrolleras
  vid paketering. Den omgenererade demowikin ska vara identisk byte för byte.

## Avgränsningar

Ingen verklig FULLSAVE från användarens kampanj fanns tillgänglig. Demodata är
påhittade. Godkänt demobygge betyder inte att kampanjkanon eller alla framtida
JSON-varianter har verifierats.

En extra kontroll med dold Edge försöktes, men testmiljön kunde inte läsa de
genererade sidorna från webbläsarprocessen. Därför görs inget påstående om genomförd
visuell webbläsargranskning eller fullständig klicktestning. Söklogiken har körts
som JavaScript, och HTML-filerna har granskats programmatiskt för länkar och ankare.
Sökningen är byggd med klassiska lokala skript, utan `fetch` eller modulimporter,
för att fungera vid direkt öppning av `index.html`.

Windows-startfilen medföljer som bekvämlighet. De automatiska körningarna använder
Python-programmet direkt; en faktisk Python-installation via `py`/`python` och
dubbelklicksstart har inte verifierats på användarens värdsystem.

Python 3.10 är lägsta avsedda version. Ingen separat testmatris för varje
Pythonversion ingår i denna första leverans.
