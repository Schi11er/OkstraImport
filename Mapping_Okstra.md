# Mapping OKSTRA Schema zu ISO 12006-3 

## Konzepte
|OKSTRA (XMI) UML| datacat (Merkmalserver)| ISO 12006-3|
|-------------|--------|-----------|
|Package| Dictionary| XtdDictionary|
|Package| Thema| XtdSubject|
|Class| Klasse| XtdSubject|
|Property| Merkmal| XtdProperty|
|Class unter Class:Schluesseltabelle| Weteliste| XtdValueList| 
|Class constraint*| Wert| XtdValue|
|Class unter Class:Datentypen teilweise| Maßeinheit | XtdUnit|
|Property mit Attribut association| Relation zw. Klassen| XtdRelationshipToSubject|
|Generalization| Vererbung zw. Klassen| XtdRelationshipToSubject|
\* nicht implementiert

## Attribute
|OKSTRA (XMI) |ISO 12006-3|
|-----------|-------------|
|xmi:id |id|
|name |name(de)|

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
- Beschreibungen der Konzepte fehlen
- Werte der Schlüsseltabellen fehlen im UML Modell (aber in Extension vorhanden)
- komplexe Datentypen als Klassen modelliert
- nicht berücksichtigte einfache Datentypen: EAJava_GM_MultiPoint, EAJava_GM_MultiCurve, EAJava_GM_MultiSurface, EAJava_GM_MultiSolid, ...
- Subclass Relationen zu folgenden Datentypen konnten nicht implementiert werden, weil diese nicht als Klasse vorhanden sind: Integer, Real, Measure, Length, Currency, Angle, Area, Time, Volume, Weight, Velocity
- Datentypen sind teilweise auch Maßeinheiten - daher als Maßeinheiten angelegt, wenn keine Merkmale dafür existieren und Verlinkung zu Merkmal
- Kann man die Datentypen, die Merkmale enthalten, als Merkmlasgruppen sehen?

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

2026-01-13 06:41:34,015 INFO Anzahl der Entities: 4749
2026-01-13 06:41:34,017 INFO Anzahl der Relationen vor Optimierung: 8217
2026-01-13 06:41:34,041 INFO Anzahl der Relationen nach Optimierung: 3237
2026-01-13 06:41:34,041 INFO CPU-Kerne: 8, Verwende 20 Worker
2026-01-13 07:46:45,120 INFO Dauer Erstellung Entities: 3911.08 Sekunden
2026-01-13 10:42:02,440 INFO Dauer Erstellung Relationen: 10517.32 Sekunden
2026-01-13 10:42:02,442 INFO Gesamtdauer: 14433.21 Sekunden

# Problem
Import der RelationshipToSubject Relationen läuft nicht durch