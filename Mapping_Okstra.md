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

CREATE INDEX idx_dictionary_id IF NOT EXISTS FOR (n:XtdDictionary) ON (n.id);
CREATE INDEX idx_subject_id IF NOT EXISTS FOR (n:XtdSubject) ON (n.id);
CREATE INDEX idx_referencedocument_id IF NOT EXISTS FOR (n:XtdReferenceDocument) ON (n.id);
CREATE INDEX idx_property_id IF NOT EXISTS FOR (n:XtdProperty) ON (n.id);
CREATE INDEX idx_valuelist_id IF NOT EXISTS FOR (n:XtdValueList) ON (n.id);
CREATE INDEX idx_orderedvalue_id IF NOT EXISTS FOR (n:XtdOrderedValue) ON (n.id);
CREATE INDEX idx_value_id IF NOT EXISTS FOR (n:XtdValue) ON (n.id);
CREATE INDEX idx_unit_id IF NOT EXISTS FOR (n:XtdUnit) ON (n.id);
CREATE INDEX idx_object_id IF NOT EXISTS FOR (n:XtdObject) ON (n.id);
CREATE INDEX idx_root_id IF NOT EXISTS FOR (n:XtdRoot) ON (n.id);
CREATE INDEX idx_concept_id IF NOT EXISTS FOR (n:XtdConcept) ON (n.id);
CREATE INDEX idx_entity_id IF NOT EXISTS FOR (n:Entity) ON (n.id);
CREATE INDEX idx_language_id IF NOT EXISTS FOR (n:XtdLanguage) ON (n.id);
CREATE INDEX idx_reltosubject_id IF NOT EXISTS FOR (n:XtdRelationshipToSubject) ON (n.id);
CREATE INDEX idx_reltype_id IF NOT EXISTS FOR (n:XtdRelationshipType) ON (n.id);
CREATE INDEX idx_catalogrecord_id IF NOT EXISTS FOR (n:CatalogRecord) ON (n.id);

## Ergebnisse
2026-08-11 12:26:57,480 INFO Dauer Erstellung Entities: 4628.77 Sekunden
2026-08-12 11:32:58,749 INFO Dauer Erstellung Relationen: 1246.23 Sekunden

2026-08-12 13:40:08,498 INFO Anzahl der Maßeinheiten: 99
2026-08-12 13:40:08,499 INFO Anzahl der Entities: 8469
2026-08-12 13:40:08,499 INFO Anzahl der Relationen vor Optimierung: 7440
2026-08-12 13:40:08,531 INFO Anzahl der Relationen nach Optimierung: 4675
2026-08-12 13:40:08,534 INFO Einfache Relationen: 2640
2026-08-12 13:40:08,534 INFO Komplexe RELATIONSHIP_TO_SUBJECT-Relationen: 2035
2026-08-12 13:40:08,548 INFO CPU-Kerne: 8, Verwende 4 Worker

D8symd3W

SHOW TRANSACTIONS
YIELD transactionId, currentQuery, status, currentQueryStatus, elapsedTime, waitTime, activeLockCount
RETURN transactionId, currentQuery, status, currentQueryStatus, elapsedTime, waitTime, activeLockCount
ORDER BY elapsedTime DESC