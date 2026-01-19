import random
import tkinter
import weakref
import xml.etree.ElementTree as ET
import uuid
import logging
from enum import Enum
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from GraphQLRequests import (add_tag, create_catalog_entry, create_relationship, create_tag,
    get_tag, login)

# Logfile zu Beginn leeren
open("logfile.txt", "w").close()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),  # Konsole
        logging.FileHandler("logfile.txt", encoding="utf-8")  # Datei
    ]
)

class EntityType(Enum):
    DICTIONARY = ("Dictionary", "Dictionary", "c1c7016b-f85c-43c7-a696-71e75555062b")
    THEMA = ("Thema", "Subject", "5997da9b-a716-45ae-84a9-e2a7d186bcf9")
    KLASSE = ("Klasse", "Subject", "e9b2cd6d-76f7-4c55-96ab-12d084d21e96")
    MERKMALSGRUPPE = ("Merkmalsgruppe", "Subject", "7c9ffe6e-3c8b-4cd2-b57b-4cd102325603")
    REFERENZDOKUMENT = ("Referenzdokument", "ReferenceDocument", "992c8887-301e-4764-891c-ae954426fc22")
    MERKMAL = ("Merkmal", "Property", "d4b0ba83-eb40-4997-85e0-9d6181e85639")
    WERTELISTE = ("Werteliste", "ValueList", "57172977-a42f-4e05-8109-cd906ec7f43c")
    WERT = ("Wert", "Value", "a5d13c88-7d83-42c1-8da2-5dc6d8e8a749")
    MASSEINHEIT = ("Maßeinheit", "Unit", "09da1ebb-8641-47fa-b82e-8588c7fef09e")

class RelType(str, Enum):
    RELATIONSHIP_TO_SUBJECT = "RelationshipToSubject"
    PROPERTIES = "Properties"
    POSSIBLE_VALUES = "PossibleValues"
    DICTIONARY = "Dictionary"
    VALUES = "Values"
    UNITS = "Units"

#
# --------------Bis hier ist alles generisch----------------
#

# Enum für alle relevanten XML-Tags
class XmlTag(Enum):
    MODEL = ("uml", "Model")
    PACKAGEDELEMENT = ("", "packagedElement")
    OWNEDATTRIBUTE = ("", "ownedAttribute")
    GENERALIZATION = ("", "generalization")
    MEMBEREND = ("", "memberEnd")
    OWNEDEND = ("", "ownedEnd")

    def tag(self, ns):
        return f"{{{ns[self.value[0]]}}}{self.value[1]}"

subdatatypes = [
    "EAID_ED4B232F_5EF1_4793_9DAE_32DC0D70A047",
    "EAID_AF7C81A6_B1C1_4469_A09F_B97989024A14",
    "EAID_475E7573_D79F_4d66_A409_045AF233ED79",
    "EAID_6FF43F87_FD8E_4c40_8A4D_EB136AB2AA7B",
    "EAID_9752F3C4_00B0_43af_B9C2_948FD245129C",
    "EAID_6D08D328_8034_496e_BD66_678B4E078207",
    "EAID_61A592F5_3BE3_46a7_BB49_54169308D753",
    "EAID_75F88288_F562_4fb7_A7CF_F044151629AC",
    "EAID_6019CCF6_855B_48f2_84E2_4D923348DC79",
    "EAID_3BF98F82_7897_4821_893F_1E52CB3CB9FC",
    "EAID_F9AF5F63_16F0_4af5_B343_E09625C32108",
    "EAID_16A86DD1_3DA0_45b6_A135_31BC5AB5B43C"
]

def find_datatype(attribute, ns):
    dType = attribute.find("type")
    # logging.info(dType.attrib)
    name = dType.get(f"{{{ns['xmi']}}}idref")
    if name is None:
        name = "EAJava_Boolean"
        
    if name in ("EAJava_CharacterString","EAID_AF7C81A6_B1C1_4469_A09F_B97989024A14"):
        return "XTD_STRING"
    elif name in ("EAJava_Integer", "EAID_ED4B232F_5EF1_4793_9DAE_32DC0D70A047"):
        return "XTD_INTEGER"
    elif name in ("EAJava_Boolean","EAID_751057C8_1B7E_4000_89CD_67D1EBAD3E4D"):
        return "XTD_BOOLEAN"
    elif name in ("EAJava_Real", "EAID_61A592F5_3BE3_46a7_BB49_54169308D753"):
        return "XTD_REAL"
    elif name in ("EAJava_ClockTime", "EAJava_Date", "EAID_8F39BC74_02D2_4a24_A39F_61FC4650AC98", "EAID_47C07903_9CF4_47d3_AB12_B656977FC995"):
        return "XTD_DATETIME"
    elif name in ("EAID_3CC5A3E8_2ECA_4e42_B09C_935BD5D3B64A","EAID_96D39787_43AA_4ba9_9628_F2DA5295EE9C", "EAID_E4A21E02_DDCA_4c74_BA07_D4AFAB523690", "EAID_FD776E60_9DAC_47bb_BD74_0E616A29326C", "EAID_F23E617D_5FEA_4cd6_AAE5_F38E34971B2E", "EAID_642283DE_4A64_4b12_B987_2F095D1C49FB", "EAID_5E740584_6743_42da_8CD0_2E342F9A5FDE", "EAID_EAAC4305_1147_4752_801A_48B1BB977958"):
        return None
    else:
        return None

def prepare_entity_attributes(domain, entity_type, ns):
    name = domain.get("name")
    id = domain.get(f"{{{ns['xmi']}}}id")

    # Erweiterten Lookup-Key mit description erstellen
    lookup_key = (name, entity_type.value[1])
    
    # Prüfen, ob Entity bereits existiert
    if lookup_key in entity_lookup:
        existing_id = entity_lookup[lookup_key]
        return {
            "id": existing_id,
            "properties": None, 
            "entityType": entity_type,
            "is_new": False
        }
    
    # Entity noch nicht vorhanden, neue erstellen
    properties = {"names": {"languageTag": "de", "value": name}}
    properties["id"] = id
    if entity_type.value[1] == EntityType.MERKMAL.value[1]:
        datatype = find_datatype(domain,ns)
        if datatype:
            properties["propertyProperties"] = {"dataType": datatype}
    
    # In die Lookup-Tabelle eintragen
    entity_lookup[lookup_key] = properties["id"]
    return {
        "id": properties["id"],
        "properties": properties,
        "entityType": entity_type,
        "is_new": True
    }

def create_entry(attributes, token, tagId):
    properties = attributes["properties"]
    entityType = attributes["entityType"]
    
    max_retries = 5
    
    for attempt in range(1, max_retries + 1):
        try:
            result = create_catalog_entry(token, entityType.value[1], properties, [entityType.value[2], tagId])
            if result is None:
                # Retry-Logik für add_tag
                # max_retries = 5
                addTag = None
                
                for tag_attempt in range(1, max_retries + 1):
                    addTag = add_tag(token, properties["id"], tagId)
                    if addTag is not None:
                        # logging.info(f"Tag für '{properties['names']['value']}' erfolgreich hinzugefügt nach Versuch {attempt}")
                        break
                    
                    if tag_attempt < max_retries:
                        wait_time = tag_attempt * 0.5  # Progressiv längere Wartezeit
                        time.sleep(wait_time)
                    else:
                        # Alle Versuche fehlgeschlagen
                        error_msg = f"add_tag fehlgeschlagen nach {max_retries} Versuchen für Entity {properties['names']['value']} (ID: {properties['id']})"
                        logging.error(error_msg)
                        raise Exception(error_msg)
            
            if entityType == EntityType.DICTIONARY:
                return None  # Keine ID für Dictionary
            return properties["id"]
        except Exception as e:
            error_str = str(e).lower()
            is_403_error = '403' in error_str or 'client error' in error_str
            is_lock_error = 'lock' in error_str
            
            # Bei 403 oder Lock-Fehler: Retry
            if (is_403_error or is_lock_error) and attempt < max_retries:
                sleep_time = random.uniform(1, 5)
                # logging.warning(f"Versuch {attempt}/{max_retries} fehlgeschlagen für '{properties['names']['value']}': {e}. Warte {sleep_time:.2f}s...")
                time.sleep(sleep_time)
                continue
            
            # Bei 403-Fehler nach allen Retries: Programm abbrechen
            if is_403_error:
                logging.error(f"403 Client Error in create_entry nach {max_retries} Versuchen - Abbruch des gesamten Prozesses: {e}")
                logging.error(f"EntityType: {entityType}, Properties: {properties}")
                raise SystemExit(f"Programm abgebrochen wegen 403 Client Error nach {max_retries} Versuchen: {e}")
            
            logging.error(f"Fehler in create_entry: {e}, EntityType: {entityType}, Properties: {properties}")
            raise

def log_unknown_schema_type(level, tag):
    logging.info(f"Unbekannter Schema-Typ [{level}]: {tag}")

def dict_to_hashable(obj):
    """
    Konvertiert ein Dictionary (auch verschachtelt) zu einem hashbaren Tupel.
    """
    if obj is None:
        return None
    elif isinstance(obj, dict):
        return tuple(sorted((k, dict_to_hashable(v)) for k, v in obj.items()))
    elif isinstance(obj, list):
        return tuple(dict_to_hashable(item) for item in obj)
    else:
        return obj

def hashable_to_dict(obj):
    """
    Konvertiert ein hashbares Tupel zurück zu einem Dictionary.
    """
    if obj is None:
        return None
    elif isinstance(obj, tuple) and len(obj) > 0 and isinstance(obj[0], tuple) and len(obj[0]) == 2:
        # Es ist ein Dictionary-Tupel
        return {k: hashable_to_dict(v) for k, v in obj}
    else:
        return obj

def optimize_relationship_tasks(relationship_tasks):
    """
    Optimiert relationship_tasks, indem Einträge mit gleichen (relationship_type, props, from_id) 
    zusammengeführt werden und die to_ids in einem Array gesammelt werden.
    """
    # Dictionary zum Sammeln der optimierten Relationships
    # Key: (relationship_type, props_hash, from_id)
    # Value: set of to_ids
    optimized = {}
    
    for rel_type, props, from_id, to_ids in relationship_tasks:
        # Props zu einem hashbaren Wert konvertieren (für Dictionary-Key)
        props_key = dict_to_hashable(props)
        
        # Schlüssel für die Gruppierung erstellen
        key = (rel_type, props_key, from_id)
        
        # to_ids zu einem Set hinzufügen (um Duplikate zu vermeiden)
        if key not in optimized:
            optimized[key] = set()
        
        # Alle to_ids hinzufügen
        if isinstance(to_ids, list):
            optimized[key].update(to_ids)
        else:
            optimized[key].add(to_ids)
    
    # Zurück zu der ursprünglichen Struktur konvertieren
    result = []
    for (rel_type, props_key, from_id), to_ids_set in optimized.items():
        # props_key zurück zu Dictionary konvertieren
        props = hashable_to_dict(props_key)
        
        # Set zurück zu List konvertieren
        to_ids_list = list(to_ids_set)
        
        result.append((rel_type, props, from_id, to_ids_list))
    
    return result

def create_relationship_with_retry(rel_args, auth_token):
    rel_type, properties, from_id, to_ids = rel_args
    new_to_ids = []
    for to_id in to_ids:
        rel_key = (rel_type, from_id, to_id)
        if rel_key in relation_lookup:
            continue
        relation_lookup.add(rel_key)
        new_to_ids.append(to_id)
    if new_to_ids:
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                result = create_relationship(auth_token, rel_type, properties, from_id, new_to_ids)
                if result and isinstance(result, dict) and 'errors' in result:
                    error_messages = str(result['errors'])
                    error_lower = error_messages.lower()
                    is_403_error = '403' in error_lower or 'client error' in error_lower
                    is_lock_error = 'lock' in error_lower
                    
                    # Bei 403 oder Lock-Fehler: Retry
                    if (is_403_error or is_lock_error) and attempt < max_retries:
                        sleep_time = random.uniform(1, 5)
                        time.sleep(sleep_time)
                        continue
                    
                    # Bei 403-Fehler nach allen Retries: Programm abbrechen
                    if is_403_error:
                        logging.error(f"403 Client Error beim Anlegen der Beziehung nach {max_retries} Versuchen - Abbruch des gesamten Prozesses")
                        logging.error(f"Fehlerdetails: {error_messages}")
                        logging.error(f"Beziehungsparameter: type={rel_type}, fromId={from_id}, toId={new_to_ids}")
                        raise SystemExit(f"Programm abgebrochen wegen 403 Client Error nach {max_retries} Versuchen: {error_messages}")
                    
                    logging.error(f"Fehler beim Anlegen der Beziehung: {error_messages}\nBeziehungsparameter: type={rel_type}, fromId={from_id}, toId={new_to_ids}")
                break
            except Exception as e:
                error_str = str(e).lower()
                is_403_error = '403' in error_str or 'client error' in error_str
                is_lock_error = 'lock' in error_str
                
                # Bei 403 oder Lock-Fehler: Retry
                if (is_403_error or is_lock_error) and attempt < max_retries:
                    sleep_time = random.uniform(1, 5)
                    time.sleep(sleep_time)
                    continue
                
                # Bei 403-Fehler nach allen Retries: Programm abbrechen
                if is_403_error:
                    logging.error(f"403 Client Error beim Anlegen der Beziehung nach {max_retries} Versuchen - Abbruch des gesamten Prozesses: {e}")
                    logging.error(f"Beziehungsparameter: type={rel_type}, fromId={from_id}, toId={new_to_ids}")
                    raise SystemExit(f"Programm abgebrochen wegen 403 Client Error nach {max_retries} Versuchen: {e}")
                
                logging.error(f"Fehler beim Anlegen der Beziehung: {e}\nBeziehungsparameter: type={rel_type}, fromId={from_id}, toId={new_to_ids}")
                break
 
 #
 # --------------Hauptprogramm----------------
 #
                
if __name__ == "__main__":
    start = time.time()
    # Login
    token = login()
    # logging.info("Login erfolgreich")

    # Find or create tag
    tagId = "OkstraId"
    tagName = "Okstra"

    file_path = "resources/okstra_short.xml"

    tag = get_tag(token, tagId)
    # logging.info("Tag abgerufen:", tag)
    if not tag:
        logging.info("Tag nicht gefunden, erstelle neuen Tag.")
        tag = create_tag(token, tagName, tagId)
        logging.info(f"Tag erstellt: {tag}")
    
    # Validierung, dass tagId korrekt ist
    if tagId is None:
        logging.error("tagId ist None - kann nicht fortfahren")
        exit(1)
    
    # logging.info(f"Verwende tagId: {tagId}")

    ns = {}
    for event, elem in ET.iterparse(file_path, events=("start-ns", "start")):
        if event == "start-ns":
            ns[elem[0] or ""] = elem[1]

    tree = ET.parse(file_path)
    root = tree.getroot()
    # logging.info(ns)
    ns[''] = ""  # Default Namespace auf leeren String setzen
 
    # Lookup-Tabellen und Task Sammlungen für Entities und Relationen
    entity_lookup = {}  # (name, typ, description) -> id
    relation_lookup = set()  # (relationship_type, from_id, [to_ids])
    tasks = [] # List of entity dictionaries: {id, properties, entityType, is_new}
    relationship_tasks = [] # (relationship_type, props, from_id, [to_ids])
    entry_ids = []  # IDs die eine Dictionary-Beziehung benötigen
    collected_associations = {}
    collected_association_props = {} 
    key_tables = []
    units = []
    rel_to_subj_props = {"relationshipToSubjectProperties": {"relationshipType": "XTD_SCHEMA_LEVEL"}}
    
    model = root.find(XmlTag.MODEL.tag(ns))
    dictionary =model.find(XmlTag.PACKAGEDELEMENT.tag(ns))
      
    # Create Dictionary from FeatureCatalogue
    dictAttrs = prepare_entity_attributes(dictionary, EntityType.DICTIONARY, ns)
    create_entry(dictAttrs, token, tagId)
    dictionaryId = dictAttrs["id"]
    
    # Schlüsseltabellen zuerst verarbeiten
    valuelists = next((child for child in dictionary.findall(XmlTag.PACKAGEDELEMENT.tag(ns)) 
                       if child.get("name") == "Schluesseltabellen"), None)
    for valueListEl in valuelists.findall(XmlTag.PACKAGEDELEMENT.tag(ns)):
        attrs1 = prepare_entity_attributes(valueListEl, EntityType.WERTELISTE, ns)
        if attrs1.get("is_new", True):
            tasks.append(attrs1)
        key_tables.append(attrs1["id"])
    # e = 0
    for child in dictionary.findall(XmlTag.PACKAGEDELEMENT.tag(ns)):
        if child.get("name") != "Schluesseltabellen":
            attrs1 = prepare_entity_attributes(child, EntityType.THEMA, ns)
            if attrs1.get("is_new", True):
                tasks.append(attrs1)

            collected_class_ids = []
            
            for classEl in child.findall(XmlTag.PACKAGEDELEMENT.tag(ns)):
                
                if classEl.get(f"{{{ns['xmi']}}}type") == "uml:Class":
                    if child.get("name") == "Datentypen" and classEl.findall(XmlTag.OWNEDATTRIBUTE.tag(ns)).__len__() == 0:
                        attrs2 = prepare_entity_attributes(classEl, EntityType.MASSEINHEIT, ns)
                        units.append(attrs2["id"])
                    else:
                        attrs2 = prepare_entity_attributes(classEl, EntityType.KLASSE, ns)
                        collected_class_ids.append(attrs2["id"])
                    if attrs2.get("is_new", True):
                        tasks.append(attrs2)
                    
                    
                    for propertyEl in classEl.findall(XmlTag.OWNEDATTRIBUTE.tag(ns)):
                        if propertyEl.get("association") is not None:
                            # logging.info(f"Association-Property gefunden: {propertyEl.get('name')}")
                            collected_association_props[propertyEl.get(f"{{{ns['xmi']}}}id")] = [attrs2["id"],propertyEl.get("name")]
                        else:
                            prop_attrs = prepare_entity_attributes(propertyEl, EntityType.MERKMAL, ns)
                            if prop_attrs.get("is_new", True):
                                tasks.append(prop_attrs)
                            relationship_tasks.append((RelType.PROPERTIES, None, attrs2["id"], [prop_attrs["id"]]))
                            # logging.info(f"Eigenschaft gefunden: {prop_attrs['properties']['names']['value']}")
                            pType = propertyEl.find("type")
                            typeId = pType.get(f"{{{ns['xmi']}}}idref") 
                            if typeId != None and find_datatype(propertyEl,ns) is None: 
                                if typeId in key_tables:
                                    relationship_tasks.append((RelType.POSSIBLE_VALUES, None, prop_attrs["id"], [typeId]))
                                elif typeId in units:
                                    relationship_tasks.append((RelType.UNITS, None, prop_attrs["id"], [typeId]))
                            
                        
                    for generalizationEl in classEl.findall(XmlTag.GENERALIZATION.tag(ns)):
                        ref_class = generalizationEl.get("general")
                        if ref_class not in subdatatypes:
                            relAttrs = {
                                "relationshipToSubjectProperties": {
                                    "relationshipType": "XTD_SCHEMA_LEVEL",
                                    "name": "specializes"
                                }
                            }
                            relationship_tasks.append((RelType.RELATIONSHIP_TO_SUBJECT, relAttrs, ref_class, [attrs2["id"]]))
                        else:
                            logging.info(f"Subdatatype Generalization übersprungen: {ref_class}")
                        
                elif classEl.get(f"{{{ns['xmi']}}}type") == "uml:Association":
                    ass_id = classEl.get(f"{{{ns['xmi']}}}id")
                    memberIds = []
                    for member in classEl.findall(XmlTag.MEMBEREND.tag(ns)):
                        memberIds.append(member.get(f"{{{ns['xmi']}}}idref"))
                    collected_associations[ass_id] = memberIds
                    
                    ownedEndNames = []
                    for ownedEnd in classEl.findall(XmlTag.OWNEDEND.tag(ns)):
                        pName = None
                        if ownedEnd.get("name") is not None:
                            pName = ownedEnd.get("name")
                        collected_association_props[ownedEnd.get(f"{{{ns['xmi']}}}id")] = [ownedEnd.find("type").get(f"{{{ns['xmi']}}}idref"),pName]
                        
                else:
                    log_unknown_schema_type(2, classEl.get(f"{{{ns['xmi']}}}type")) 
        
            relationship_tasks.append((RelType.RELATIONSHIP_TO_SUBJECT, rel_to_subj_props, attrs1["id"], collected_class_ids))
        # e += 1
        # if e == 1:
        #     break
            
    for assId, (dstMember, scrMember) in collected_associations.items():  
        (scrId, scrName) = collected_association_props.get(scrMember, (None, None))
        (dstId, dstName) = collected_association_props.get(dstMember, (None, None))
        
        if scrId is None or dstId is None:
            logging.error(f"Association ohne gültige Mitglieder gefunden: {assId} mit Mitgliedern {dstMember}, {scrMember}")
            continue
        
        def create_rel_attrs(name):
            return {
                "relationshipToSubjectProperties": {
                    "relationshipType": "XTD_INSTANCE_LEVEL",
                    "name": name
                }
            }
        
        if scrName is not None:
            relationship_tasks.append((RelType.RELATIONSHIP_TO_SUBJECT, create_rel_attrs(scrName), scrId, dstId))
        if dstName is not None:
            relationship_tasks.append((RelType.RELATIONSHIP_TO_SUBJECT, create_rel_attrs(dstName), dstId, scrId))

#
# --------------Ab hier ist alles generisch----------------
#
    logging.info(f"Anzahl der Maßeinheiten: {len(units)}")
    logging.info(f"Anzahl der Entities: {len(tasks)}")
    logging.info(f"Anzahl der Relationen vor Optimierung: {len(relationship_tasks)}")

    # Relationship-Tasks optimieren (zusammenführen)
    relationship_tasks = optimize_relationship_tasks(relationship_tasks)
    logging.info(f"Anzahl der Relationen nach Optimierung: {len(relationship_tasks)}")

    # Relationship-Tasks in Datei ausgeben
    with open("relationship_tasks.txt", "w", encoding="utf-8") as f:
        for idx, (rel_type, props, from_id, to_ids) in enumerate(relationship_tasks, 1):
            f.write(f"Task {idx}: Type={rel_type}, Properties={props}, FromID={from_id}, ToIDs={to_ids}\n")

    # Optimale Anzahl an Threads
    cpu_count = os.cpu_count()
    optimal_workers = min(cpu_count*3, 20)

    logging.info(f"CPU-Kerne: {cpu_count}, Verwende {optimal_workers} Worker")

    start0 = time.time()
    # Parallelisierte Entity-Erstellung
    with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
        # Alle Tasks als Futures starten
        future_to_task = {executor.submit(create_entry, task, token, tagId): task for task in tasks}
        
        # Ergebnisse sammeln
        for future in as_completed(future_to_task):
            try:
                id = future.result()
                if id:
                    entry_ids.append(id)
            except Exception as e:
                task = future_to_task[future]
                logging.error(f"Fehler bei Entity-Erstellung: {e}, Task: {task}")

    logging.info(f"Dauer Erstellung Entities: {time.time() - start0:.2f} Sekunden")
    
    start1 = time.time()
    # Dictionary-Beziehungen erstellen
    for idx, id in enumerate(entry_ids, 1):
        # Re-Login alle 500 Einträge zur Vermeidung von Token-Ablauf
        if idx % 500 == 0:
            token = login()
            logging.info(f"Re-Login nach {idx} Dictionary-Relationen durchgeführt - Warte 5 Sekunden...")
            time.sleep(5)
        create_relationship_with_retry((RelType.DICTIONARY, None, id, [dictionaryId]), token)
    logging.info(f"Dauer Erstellung Dictionary-Relationen: {time.time() - start1:.2f} Sekunden")
  
    token = login()
 
    start2 = time.time()

    logging.info(f"Starte Verarbeitung von {len(relationship_tasks)} Relationen")

    for idx, rel_args in enumerate(relationship_tasks, 1):
        rel_type = rel_args[0]
        is_complex = rel_type == RelType.RELATIONSHIP_TO_SUBJECT
        
        # Dynamisches Re-Login: Bei komplexen alle 100, bei einfachen alle 500
        login_interval = 100 if is_complex else 500
        
        if idx % login_interval == 0:
            token = login()
            pause_time = 10 if is_complex else 1
            logging.info(f"Re-Login nach {idx} Relationen ({'komplex' if is_complex else 'einfach'}) - Warte {pause_time} Sekunden...")
            time.sleep(pause_time)
        
        # Kleine Pause bei komplexen Relations für DB-Entlastung
        if is_complex and idx % 10 == 0:
            time.sleep(1)
            
        create_relationship_with_retry(rel_args, token)

    logging.info(f"Dauer Erstellung Relationen: {time.time() - start2:.2f} Sekunden")
    logging.info(f"Gesamtdauer: {time.time() - start:.2f} Sekunden")
