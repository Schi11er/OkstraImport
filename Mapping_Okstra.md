# Mapping OKSTRA Schema zu ISO 12006-3 

## Konzepte
|OKSTRA (XMI) UML| datacat (Merkmalserver)| ISO 12006-3|
|-------------|--------|-----------|
|Package| Dictionary| XtdDictionary|
|Package| Thema| XtdSubject|
|Class| Klasse| XtdSubject|
|Property| Merkmal| XtdProperty|
|Class unter Package:Schluesseltabelle| Weteliste| XtdValueList| 
|Extension element constraints| Wert| XtdValue|
|Class unter Package:Datentypen | Maßeinheit / Klasse | XtdUnit / XtdSubject|
|Property mit Attribut association| Relation zw. Klassen| XtdRelationshipToSubject|
|Association | Relation zw. Klassen| XtdRelationshipToSubject |
|Generalization| Vererbung zw. Klassen| XtdRelationshipToSubject|


## Attribute
|OKSTRA (XMI) |ISO 12006-3|
|-----------|-------------|
|xmi:id |id|
|name |name(de)|
|documentation | definition |

## Datentypen
|OKSTRA (XMI) |ISO 12006-3|
|-----------|-------------|
| EAJava_CharacterString | String |
| EAJava_Integer | Integer |
| EAJava_Boolean | Boolean |
| EAJava_Real | Real |
| EAJava_ClockTime | DateTime |
| EAJava_Date | DateTime |
| andere | keine Datentyp zugeordnet |

## Notizen
- in Beschreibungen in der XMI sind Umlaute teilweise fehlerhaft codiert, z.B. Schl�sseltabelle
- Subclass Relationen zu folgenden Datentypen konnten nicht implementiert werden, weil diese nicht als Klasse vorhanden sind: Integer, Real, Measure, Length, Currency, Angle, Area, Time, Volume, Weight, Velocity
- komplexe Datentypen als Klassen modelliert
- nicht berücksichtigte einfache Datentypen: EAJava_GM_MultiPoint, EAJava_GM_MultiCurve, EAJava_GM_MultiSurface, EAJava_GM_MultiSolid, ..., EAJava_Sequence_Bit_ (eventuell mit Datentyp XTD_COMPLEX anlegen?)
- Datentypen sind teilweise auch Maßeinheiten - daher als Maßeinheiten angelegt, wenn keine Merkmale dafür existieren und Verlinkung zu Merkmal
- Kann man die Datentypen, die Merkmale enthalten, als Merkmalsgruppen sehen?
- Datentypen macht aus, dass sie nicht als eigenständige Klassen "lebensfähig" sind und keine Relationen haben
- https://www.perplexity.ai/search/3752afc8-b6ca-4304-9c87-a46963eb25cc
- 

# Development
## datacat
GraphQL Endpoint: http://localhost:8080/graphql
User Variables in .env
GraphQL Schemas in resources folder

mutations:
- login
- createCatalogEntry
- createRelationship

## Terminal Command Prompt
conda activate ./.conda
python main.py

## Cypher Befehle Neo4j Datenbank leeren
MATCH(x)-[:TAGGED]->(c:Tag{name:"Okstra"}) DETACH DELETE x;
MATCH (n:XtdRelationshipToSubject) DETACH DELETE n;
MATCH (n:XtdRelationshipType)  DETACH DELETE n;
MATCH (n:XtdOrderedValue) DETACH DELETE n;
MATCH(x:XtdMultiLanguageText)-[:TEXTS]->(t) WHERE not ()-[:NAMES|NAME]->(x) DETACH DELETE x,t;

MATCH(x:XtdValue)-[:TAGGED]->(c:Tag{name:"Okstra"}) DETACH DELETE x;
MATCH (n:XtdRelationshipToSubject) DETACH DELETE n;
MATCH (n:XtdRelationshipType)  DETACH DELETE n;
MATCH (n:XtdOrderedValue) DETACH DELETE n;
MATCH(x:XtdMultiLanguageText)-[:TEXTS]->(t) WHERE not ()-[:NAMES|NAME]->(x) DETACH DELETE x,t;

2026-01-13 06:41:34,015 INFO Anzahl der Entities: 4749
2026-01-13 06:41:34,017 INFO Anzahl der Relationen vor Optimierung: 8217
2026-01-13 06:41:34,041 INFO Anzahl der Relationen nach Optimierung: 3237
2026-01-13 06:41:34,041 INFO CPU-Kerne: 8, Verwende 20 Worker
2026-01-13 07:46:45,120 INFO Dauer Erstellung Entities: 3911.08 Sekunden
2026-01-13 10:42:02,440 INFO Dauer Erstellung Relationen: 10517.32 Sekunden
2026-01-13 10:42:02,442 INFO Gesamtdauer: 14433.21 Sekunden

new
2026-07-30 07:10:56,296 INFO Anzahl der Maßeinheiten: 99
2026-07-30 07:10:56,296 INFO Anzahl der Entities: 7518
2026-07-30 07:10:56,297 INFO Anzahl der Relationen vor Optimierung: 6516
2026-07-30 07:10:56,323 INFO Anzahl der Relationen nach Optimierung: 4557
2026-07-30 07:10:56,359 INFO CPU-Kerne: 8, Verwende 8 Worker
2026-07-30 10:36:42,265 INFO Dauer Erstellung Entities: 3128.74 Sekunden
2026-07-30 12:29:38,701 INFO Dauer Erstellung Dictionary-Relationen: 6776.43 Sekunden

2026-07-31 08:46:51,319 INFO Dauer Erstellung Entities: 3764.88 Sekunden
2026-07-31 12:22:03,547 INFO Dauer Erstellung Dictionary-Relationen: 12912.23 Sekunden

2026-07-31 16:03:33,813 INFO Dauer Erstellung Entities: 2954.59 Sekunden
2026-07-31 17:48:51,404 INFO Dauer Erstellung Dictionary-Relationen: 6317.59 Sekunden

2026-07-31 14:18:46,354 ERROR Auth-/403-Fehler beim Anlegen der Beziehung nach 5 Versuchen - Abbruch des gesamten Prozesses: 401 Client Error:  for url: http://localhost:8080/graphql
2026-07-31 14:18:46,355 ERROR Beziehungsparameter: type=RelType.RELATIONSHIP_TO_SUBJECT, fromId=EAID_ED20D4FA_DC54_493c_BF8C_58241E48999E, toId=['EAID_DB304957_87F7_4472_AF92_9E6C0CD532C6']
Programm abgebrochen wegen Auth-/403-Fehler nach 5 Versuchen: 401 Client Error:  for url: http://localhost:8080/graphql