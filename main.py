import random
import xml.etree.ElementTree as ET
import uuid
import logging
import threading
from enum import Enum
import time
import os
import html
import re
from bs4 import BeautifulSoup
from contextlib import contextmanager
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

# Einfache Umschaltung für Testläufe:
# True -> nur XTD-Wert-Entities werden neu erstellt, danach nur deren Dictionary-Beziehungen
ONLY_RECREATE_XTD_VALUE_ENTITIES = True
RELATIONSHIP_AUTH_COOLDOWN_SECONDS = 150
RELATIONSHIP_AUTH_COOLDOWN_LONG_SECONDS = 300
RELATIONSHIP_MANUAL_PAUSE_INTERVAL = 100

relation_cooldown_until = 0.0
relation_auth_failures = 0
relation_auth_failure_streak = 0
relation_lookup_lock = threading.Lock()

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

add_tag_lock = threading.Lock()
auth_token_lock = threading.Lock()
current_auth_token = None
relation_node_locks = {}
relation_node_locks_lock = threading.Lock()

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
    EXTENSION = ("xmi", "Extension")

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
    elif name in ("EAID_3CC5A3E8_2ECA_4e42_B09C_935BD5D3B64A","EAID_96D39787_43AA_4ba9_9628_F2DA5295EE9C", "EAID_E4A21E02_DDCA_4c74_BA07_D4AFAB523690", "EAID_FD776E60_9DAC_47bb_BD74_0E616A29326C", "EAID_F23E617D_5FEA_4cd6_AAE5_F38E34971B2E", "EAID_642283DE_4A64_4b12_B987_2F095D1C49FB", "EAID_5E740584_6743_42da_8CD0_2E342F9A5FDE", "EAID_EAAC4305_1147_4752_801A_48B1BB977958", 
                  'EAJava_GM_MultiPoint', 'EAJava_GM_MultiCurve', 'EAJava_GM_MultiSurface', 'EAJava_GM_MultiSolid', 'EAJava_GM_Point', 'EAJava_GM_Curve', 'EAJava_GM_Surface', 'EAJava_Sequence_Bit_'):
        return "Geometry"
    else:
        return None

def get_http_status_code(error):
    response = getattr(error, "response", None)
    return getattr(response, "status_code", None)

def is_auth_error(error):
    error_str = str(error).lower()
    status_code = get_http_status_code(error)
    return status_code in (401, 403) or "401" in error_str or "403" in error_str or "unauthorized" in error_str or "forbidden" in error_str

def is_lock_related_error(error):
    error_str = str(error).lower()
    return "lock" in error_str or "deadlock" in error_str or "transienterror" in error_str


def mask_auth_token(token):
    if not token:
        return "<leer>"
    token_text = str(token)
    if len(token_text) <= 12:
        return token_text
    return f"{token_text[:8]}...{token_text[-4:]}"


def store_auth_token(token):
    global current_auth_token
    with auth_token_lock:
        current_auth_token = token
    return token


def ensure_auth_token(reason):
    with auth_token_lock:
        token = current_auth_token
    if token:
        return token
    return refresh_auth_token(reason)


def refresh_auth_token(reason):
    token = login()
    store_auth_token(token)
    logging.info("Auth-Token erneuert%s: %s", f" ({reason})" if reason else "", mask_auth_token(token))
    return token

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
        if datatype and datatype != "Geometry":
            properties["propertyProperties"] = {"dataType": datatype}
    
    definition = element_definitions.get(id)
    if definition:
        properties["definition"] = {"languageTag": "de", "value": definition}
    
    # In die Lookup-Tabelle eintragen
    entity_lookup[lookup_key] = properties["id"]
    return {
        "id": properties["id"],
        "properties": properties,
        "entityType": entity_type,
        "is_new": True
    }

def prepare_value_entity_attributes(value_lists):
    value_attributes = []
    for valueListId, values in value_lists.items():
        valIds = []
        for name in values:
            
            # Erweiterten Lookup-Key mit description erstellen
            lookup_key = (name, EntityType.WERT.value[1])
            
            # Prüfen, ob Entity bereits existiert
            if lookup_key in entity_lookup:
                existing_id = entity_lookup[lookup_key]
                value_attributes.append({
                    "id": existing_id,
                    "properties": None, 
                    "entityType": EntityType.WERT,
                    "is_new": False
                })
                valIds.append(existing_id)
                continue
            
            # Entity noch nicht vorhanden, neue erstellen
            properties = {"valueProperties": {"nominalValue": name}}
            properties["names"] = {"languageTag": "de", "value": name}
            properties["id"] = str(uuid.uuid4())  # Generiere eine eindeutige ID für den Wert
            valIds.append(properties["id"])
            
            # In die Lookup-Tabelle eintragen
            entity_lookup[lookup_key] = properties["id"]
            value_attributes.append({
                "id": properties["id"],
                "properties": properties,
                "entityType": EntityType.WERT,
                "is_new": True
            })
        relationship_tasks.append((RelType.VALUES, None, valueListId, valIds))
    return value_attributes

    
def create_entry(attributes, tagId):
    properties = attributes["properties"]
    entityType = attributes["entityType"]
    token = ensure_auth_token("Entity-Start")
    
    max_retries = 5
    
    for attempt in range(1, max_retries + 1):
        try:
            result = create_catalog_entry(token, entityType.value[1], properties, [entityType.value[2], tagId])
            if result is None:
                # Retry-Logik für add_tag
                # max_retries = 5
                addTag = None
                
                for tag_attempt in range(1, max_retries + 1):
                    with add_tag_lock:
                        addTag = add_tag(token, properties["id"], tagId)
                    if addTag is not None:
                        # logging.info(f"Tag für '{properties['names']['value']}' erfolgreich hinzugefügt nach Versuch {attempt}")
                        break
                    
                    if tag_attempt < max_retries:
                        wait_time = tag_attempt * 1.0  # Progressiv längere Wartezeit
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
            status_code = get_http_status_code(e)
            auth_error = is_auth_error(e)
            lock_error = is_lock_related_error(e)
            
            # Bei 401: Token erneuern und erneut versuchen
            if status_code == 401 and attempt < max_retries:
                token = refresh_auth_token("Entity-Erstellung")
                time.sleep(random.uniform(0.5, 1.5))
                continue

            # Bei 403 oder Lock-Fehler: Retry mit Backoff
            if (auth_error or lock_error) and attempt < max_retries:
                sleep_time = random.uniform(1, 5)
                # logging.warning(f"Versuch {attempt}/{max_retries} fehlgeschlagen für '{properties['names']['value']}': {e}. Warte {sleep_time:.2f}s...")
                time.sleep(sleep_time)
                continue
            
            # Bei 401/403-Fehler nach allen Retries: Programm abbrechen
            if auth_error:
                logging.error(f"Auth-Fehler in create_entry nach {max_retries} Versuchen - Abbruch des gesamten Prozesses: {e}")
                logging.error(f"EntityType: {entityType}, Properties: {properties}")
                raise SystemExit(f"Programm abgebrochen wegen Auth-Fehler nach {max_retries} Versuchen: {e}")
            
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

def split_relationship_tasks(relationship_tasks):
    simple_relationship_tasks = []
    complex_relationship_tasks = []

    for rel_args in relationship_tasks:
        if rel_args[0] == RelType.RELATIONSHIP_TO_SUBJECT:
            complex_relationship_tasks.append(rel_args)
        else:
            simple_relationship_tasks.append(rel_args)

    random.shuffle(simple_relationship_tasks)
    random.shuffle(complex_relationship_tasks)
    return simple_relationship_tasks, complex_relationship_tasks


def get_relation_node_lock(node_id):
    with relation_node_locks_lock:
        node_lock = relation_node_locks.get(node_id)
        if node_lock is None:
            node_lock = threading.Lock()
            relation_node_locks[node_id] = node_lock
        return node_lock


@contextmanager
def acquire_relation_node_scope(from_id, to_ids):
    node_ids = sorted({node_id for node_id in [from_id, *(to_ids or [])] if node_id is not None}, key=str)
    node_locks = [get_relation_node_lock(node_id) for node_id in node_ids]

    for node_lock in node_locks:
        node_lock.acquire()

    try:
        yield
    finally:
        for node_lock in reversed(node_locks):
            node_lock.release()

def execute_relationship_batch_serial(relationship_tasks, total_count, total_offset=0):
    processed_count = 0
    for rel_args in relationship_tasks:
        processed_count += 1

        # Bereits exisiterende Beziehungen überspringen
        if rel_args[0] == RelType.PROPERTIES or rel_args[0] == RelType.POSSIBLE_VALUES or rel_args[0] == RelType.UNITS:
            continue

        create_relationship_with_retry(rel_args)

        absolute_count = total_offset + processed_count
        if processed_count % RELATIONSHIP_MANUAL_PAUSE_INTERVAL == 0 or processed_count == len(relationship_tasks):
            logging.info("Relations-Fortschritt: %s/%s verarbeitet", absolute_count, total_count)

    return processed_count


def execute_relationship_batch_parallel(relationship_tasks, total_count, total_offset=0, max_workers=4, max_iterations=5):
    if not relationship_tasks:
        return 0

    processed_count = 0
    pending_tasks = list(relationship_tasks)

    for iteration in range(1, max_iterations + 1):
        if not pending_tasks:
            break

        logging.info(
            "Starte Relationsrunde %s/%s mit %s offenen Tasks",
            iteration,
            max_iterations,
            len(pending_tasks),
        )

        round_failed_tasks = []
        worker_count = min(max_workers, len(pending_tasks))

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_rel = {executor.submit(create_relationship_with_retry, rel_args): rel_args for rel_args in pending_tasks}

            for future in as_completed(future_to_rel):
                processed_count += 1
                rel_args = future_to_rel[future]

                try:
                    result = future.result()
                    if not result:
                        round_failed_tasks.append(rel_args)
                except Exception as e:
                    logging.error("Fehler bei paralleler Relationsverarbeitung: %s, Task: %s", e, rel_args)
                    round_failed_tasks.append(rel_args)

                absolute_count = total_offset + processed_count
                if processed_count % RELATIONSHIP_MANUAL_PAUSE_INTERVAL == 0 or processed_count == len(relationship_tasks):
                    logging.info("Relations-Fortschritt: %s/%s verarbeitet", absolute_count, total_count)

        if round_failed_tasks:
            logging.warning(
                "Runde %s abgeschlossen: %s fehlgeschlagene Tasks werden erneut eingeplant",
                iteration,
                len(round_failed_tasks),
            )

        pending_tasks = round_failed_tasks

    if pending_tasks:
        logging.error(
            "Nach %s Iterationen sind noch %s Relations-Tasks offen und werden nicht weiter erneut versucht",
            max_iterations,
            len(pending_tasks),
        )

    return processed_count


def set_relationship_cooldown(seconds, reason):
    global relation_cooldown_until
    relation_cooldown_until = max(relation_cooldown_until, time.time() + seconds)
    logging.warning("Setze globalen Cooldown für Beziehungen auf %.0f Sekunden wegen: %s", seconds, reason)


def handle_relation_auth_retry(error_message, attempt, max_retries, rel_type, from_id, to_ids, retry_reason):
    global relation_auth_failures
    global relation_auth_failure_streak

    relation_auth_failures += 1
    relation_auth_failure_streak += 1

    cooldown_seconds = RELATIONSHIP_AUTH_COOLDOWN_SECONDS if relation_auth_failures == 1 else RELATIONSHIP_AUTH_COOLDOWN_LONG_SECONDS
    set_relationship_cooldown(cooldown_seconds, error_message)

    if relation_auth_failure_streak >= 3:
        logging.error("Mehrere aufeinanderfolgende Auth-Fehler bei Beziehungen, breche die Relationsphase ab: %s", error_message)
        logging.error("Letzte Beziehung: type=%s fromId=%s toIds=%s", rel_type, from_id, to_ids)
        raise SystemExit(f"Programm abgebrochen wegen wiederholter Auth-Fehler bei Beziehungen: {error_message}")

    if attempt >= max_retries:
        logging.error("Auth-/403-Fehler bei Beziehung nach %s Versuchen - überspringe Eintrag: %s", max_retries, error_message)
        return None

    auth_pause_seconds = random.uniform(120, 180)
    logging.warning(
        "Auth-/403-Fehler %s, warte %.0f Sekunden vor erneutem Versuch %s/%s: type=%s fromId=%s toIds=%s",
        retry_reason,
        auth_pause_seconds,
        attempt,
        max_retries,
        rel_type,
        from_id,
        to_ids,
    )
    time.sleep(auth_pause_seconds)
    return refresh_auth_token("Beziehung")


def create_relationship_with_retry(rel_args):
    rel_type, properties, from_id, to_ids = rel_args
    auth_token = ensure_auth_token("Relationen Start")
    new_to_ids = []
    with relation_lookup_lock:
        for to_id in to_ids:
            rel_key = (rel_type, from_id, to_id)
            if rel_key in relation_lookup:
                continue
            relation_lookup.add(rel_key)
            new_to_ids.append(to_id)

    if not new_to_ids:
        return True

    with acquire_relation_node_scope(from_id, new_to_ids):
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                result = create_relationship(auth_token, rel_type, properties, from_id, new_to_ids)
                if result and isinstance(result, dict) and 'errors' in result:
                    error_messages = str(result['errors'])

                    if attempt < max_retries:
                        logging.warning("FEHLER beim Anlegen der Beziehung, versuche erneut")
                        time.sleep(5)
                        continue

                    logging.error("FEHLER trotz erfogreichem try: %s\nBeziehungsparameter: type=%s, fromId=%s, toId=%s", error_messages, rel_type, from_id, new_to_ids)
                    return False

                if rel_type == RelType.RELATIONSHIP_TO_SUBJECT and new_to_ids and len(new_to_ids) > 1:
                    time.sleep(0.25 * len(new_to_ids))
                elif rel_type == RelType.RELATIONSHIP_TO_SUBJECT:
                    time.sleep(0.25)

                return True
            except Exception as e:
                error_str = str(e).lower()
                # logging.warning("Fehler beim Anlegen der Beziehung: %s", error_str)

                if attempt < max_retries:
                    waiting = random.uniform(3, 8)
                    time.sleep(waiting)
                    continue                

                logging.error("Fehler beim Anlegen der Beziehung: %s\nBeziehungsparameter: type=%s, fromId=%s, toId=%s", e, rel_type, from_id, new_to_ids)
                return False

    return False
 
 #
 # --------------Hauptprogramm----------------
 #
                
if __name__ == "__main__":
    start = time.time()
    # Login
    token = refresh_auth_token("Initial-Login")
    # logging.info("Login erfolgreich")

    # Find or create tag
    tagId = "OkstraId"
    tagName = "Okstra"

    file_path = "resources/okstra_2_23_xmi_21.xml"
    # file_path = "resources/okstra_2_23_short_Wertelisten.xml"
    # file_path = "resources/okstra_2_23_short_Datentypen.xml"   


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
            prefix = elem[0] or ""
            if prefix not in ns:
                ns[prefix] = elem[1]

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
    element_definitions = {} # elementId, definition
    value_lists = {} # valueListId, [valueIds]
    
    extension = root.find(XmlTag.EXTENSION.tag(ns))
    elements = extension.find("elements")
    for element in elements.findall("element"):
        elementId = element.get(f"{{{ns['xmi']}}}idref")
        props = element.find("properties")
        if props.get("documentation") is not None:
            docu = props.get("documentation")
            docu = docu.replace("<li>", "-").replace("</li>", "")
            docu = html.unescape(docu)
            docu = BeautifulSoup(docu, "html.parser").get_text()
            docu = "\n".join(line.strip() for line in docu.splitlines() if line.strip())
            element_definitions[elementId] = docu
            # logging.info(docu)
            
        if element.find("extendedProperties").get("package_name") == "Schluesseltabellen":
            try:
                desc = element.find("constraints").find("constraint").get("description")
                desc = html.unescape(desc)
                werte = re.findall(r"'[^']+'\s*,\s*'([^']*)'", desc)
                # logging.info(werte)
                value_lists[elementId] = werte
                # logging.info(f"Schlüsseltabelle gefunden: {element.get('name')} mit Beschreibung: {desc}")
            except Exception as e:
                # logging.warning(f"Fehler beim Abrufen der Beschreibung für Schlüsseltabelle {element.get('name')}: {e}")
                pass

    vattrs = prepare_value_entity_attributes(value_lists) 
    for vattr in vattrs:
        if vattr.get("is_new", True):
            tasks.append(vattr)
    # logging.info(f"Anzahl der Werte: {len(tasks)}")   
  
    model = root.find(XmlTag.MODEL.tag(ns))
    dictionary =model.find(XmlTag.PACKAGEDELEMENT.tag(ns))
      
    # Create Dictionary from FeatureCatalogue
    dictAttrs = prepare_entity_attributes(dictionary, EntityType.DICTIONARY, ns)
    # create_entry(dictAttrs, token, tagId)
    dictionaryId = dictAttrs["id"]
    
    # Schlüsseltabellen zuerst verarbeiten
    valuelists = next((child for child in dictionary.findall(XmlTag.PACKAGEDELEMENT.tag(ns)) 
                       if child.get("name") == "Schluesseltabellen"), None)
    if valuelists is not None:
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
                    elif child.get("name") == "Datentypen" and classEl.findall(XmlTag.OWNEDATTRIBUTE.tag(ns)).__len__() > 0:
                        # attrs2 = prepare_entity_attributes(classEl, EntityType.MERKMALSGRUPPE, ns)
                        attrs2 = prepare_entity_attributes(classEl, EntityType.KLASSE, ns)
                        collected_class_ids.append(attrs2["id"])
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

                                pType = propertyEl.find("type")
                                typeId = pType.get(f"{{{ns['xmi']}}}idref") 
                                has_type = typeId is not None
                                has_datatype = find_datatype(propertyEl, ns) is not None

                                # Das Merkmal hat keine Informationen
                                if not has_type and not has_datatype:
                                    tasks.append(prop_attrs)
                                    relationship_tasks.append((RelType.PROPERTIES, None, attrs2["id"], [prop_attrs["id"]]))
                                    logging.info(f"Merkmal ohne Typ gefunden: {propertyEl.get('name')} in Klasse {classEl.get('name')}")

                                # Das Merkmal hat einen einfachen Datentyp oder einen Geometrie-Datentyp
                                elif has_type and has_datatype:
                                    dt = find_datatype(propertyEl, ns)
                                    if dt == "Geometry":
                                        logging.info(f"Merkmal mit Geometry-Typ gefunden: {propertyEl.get('name')} in Klasse {classEl.get('name')}. Merkmal wird ohne Datentyp angelegt.")
                                        
                                    tasks.append(prop_attrs)
                                    relationship_tasks.append((RelType.PROPERTIES, None, attrs2["id"], [prop_attrs["id"]]))
                                    
                                # Das Merkmal hat eine Werteliste
                                elif typeId in key_tables:
                                    tasks.append(prop_attrs)
                                    relationship_tasks.append((RelType.PROPERTIES, None, attrs2["id"], [prop_attrs["id"]]))
                                    relationship_tasks.append((RelType.POSSIBLE_VALUES, None, prop_attrs["id"], [typeId]))

                                # Das Merkmal hat eine Maßeinheit
                                elif typeId in units:
                                    tasks.append(prop_attrs)
                                    relationship_tasks.append((RelType.PROPERTIES, None, attrs2["id"], [prop_attrs["id"]]))
                                    relationship_tasks.append((RelType.UNITS, None, prop_attrs["id"], [typeId]))

                                # Das Merkmal hat einen einfachen Datentyp
                                elif not has_type:
                                    tasks.append(prop_attrs)
                                    relationship_tasks.append((RelType.PROPERTIES, None, attrs2["id"], [prop_attrs["id"]]))

                                # Das Merkmal hat einen komplexen Datentyp (Klasse)
                                else: 
                                    relName = {
                                        "relationshipToSubjectProperties": {
                                            "relationshipType": "XTD_INSTANCE_LEVEL",
                                            "name": propertyEl.get("name")
                                        }
                                    }
                                    relationship_tasks.append((RelType.RELATIONSHIP_TO_SUBJECT, relName, attrs2["id"], [typeId]))                            
                        
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
    simple_relationship_tasks, complex_relationship_tasks = split_relationship_tasks(relationship_tasks)
    logging.info(f"Einfache Relationen: {len(simple_relationship_tasks)}")
    logging.info(f"Komplexe RELATIONSHIP_TO_SUBJECT-Relationen: {len(complex_relationship_tasks)}")
    total_relationship_count = len(relationship_tasks)

    # # Relationship-Tasks in Datei ausgeben
    # with open("relationship_tasks.txt", "w", encoding="utf-8") as f:
    #     for idx, (rel_type, props, from_id, to_ids) in enumerate(complex_relationship_tasks, 1):
    #         f.write(f"Task {idx}: Type={rel_type}, Properties={props}, FromID={from_id}, ToIDs={to_ids}\n")

    # Optimale Anzahl an Threads
    cpu_count = os.cpu_count()
    optimal_workers = min(max(cpu_count or 1, 2), 16)

    logging.info(f"CPU-Kerne: {cpu_count}, Verwende {optimal_workers} Worker")

    # if ONLY_RECREATE_XTD_VALUE_ENTITIES:
    #     logging.info("Testlauf aktiv: nur XTD-Wert-Entities und deren Dictionary-Beziehungen werden verarbeitet")
    #     xtd_value_tasks = [task for task in tasks if task.get("entityType") == EntityType.WERT]
    #     xtd_value_ids = []

    #     start0 = time.time()
    #     with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
    #         future_to_task = {executor.submit(create_entry, task, tagId): task for task in xtd_value_tasks}
    #         processed_entities = 0

    #         for future in as_completed(future_to_task):
    #             processed_entities += 1
    #             try:
    #                 id = future.result()
    #                 if id:
    #                     xtd_value_ids.append(id)
    #             except Exception as e:
    #                 task = future_to_task[future]
    #                 logging.error(f"Fehler bei Entity-Erstellung: {e}, Task: {task}")

    #             if processed_entities % 1000 == 0 or processed_entities == len(future_to_task):
    #                 logging.info(f"Entity-Fortschritt: {processed_entities}/{len(future_to_task)} verarbeitet")

    #     logging.info(f"Dauer Erstellung XTD-Wert-Entities: {time.time() - start0:.2f} Sekunden")

    #     # start1 = time.time()
    #     # for idx, id in enumerate(xtd_value_ids, 1):
    #     #     if idx % 500 == 0:
    #     #         token = login()
    #     #         logging.info(f"Re-Login nach {idx} Dictionary-Relationen durchgeführt - Warte 5 Sekunden...")
    #     #         time.sleep(5)
    #     #     create_relationship_with_retry((RelType.DICTIONARY, None, id, [dictionaryId]), token)
    #     #     if idx % 1000 == 0 or idx == len(xtd_value_ids):
    #     #         logging.info(f"Dictionary-Relationen-Fortschritt: {idx}/{len(xtd_value_ids)} verarbeitet")
    #     # logging.info(f"Dauer Erstellung Dictionary-Relationen für XTD-Wert-Entities: {time.time() - start1:.2f} Sekunden")
    # else:
    #     start0 = time.time()
    #     # Parallelisierte Entity-Erstellung
    #     with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
    #         # Alle Tasks als Futures starten
    #         future_to_task = {executor.submit(create_entry, task, tagId): task for task in tasks}
    #         processed_entities = 0
            
    #         # Ergebnisse sammeln
    #         for future in as_completed(future_to_task):
    #             processed_entities += 1
    #             try:
    #                 id = future.result()
    #                 if id:
    #                     entry_ids.append(id)
    #             except Exception as e:
    #                 task = future_to_task[future]
    #                 logging.error(f"Fehler bei Entity-Erstellung: {e}, Task: {task}")

    #             if processed_entities % 1000 == 0 or processed_entities == len(future_to_task):
    #                 logging.info(f"Entity-Fortschritt: {processed_entities}/{len(future_to_task)} verarbeitet")

    #     logging.info(f"Dauer Erstellung Entities: {time.time() - start0:.2f} Sekunden")
        
    #     # start1 = time.time()
    #     # # Dictionary-Beziehungen erstellen
    #     # for idx, id in enumerate(entry_ids, 1):
    #     #     # Re-Login alle 500 Einträge zur Vermeidung von Token-Ablauf
    #     #     if idx % 500 == 0:
    #     #         token = login()
    #     #         logging.info(f"Re-Login nach {idx} Dictionary-Relationen durchgeführt - Warte 5 Sekunden...")
    #     #         time.sleep(5)
    #     #     create_relationship_with_retry((RelType.DICTIONARY, None, id, [dictionaryId]), token)
    #     #     if idx % 1000 == 0 or idx == len(entry_ids):
    #     #         logging.info(f"Dictionary-Relationen-Fortschritt: {idx}/{len(entry_ids)} verarbeitet")
    #     # logging.info(f"Dauer Erstellung Dictionary-Relationen: {time.time() - start1:.2f} Sekunden")
    
    start2 = time.time()

    token = ensure_auth_token("Entity-Erstellung")
    logging.info("Auth-Token für Relationsphase verwendet: %s", mask_auth_token(token))

    logging.info(f"Starte Verarbeitung von {total_relationship_count} Relationen")

    # processed_simple = execute_relationship_batch_serial(
    #     simple_relationship_tasks,
    #     total_relationship_count,
    #     total_offset=0,
    # )

    if complex_relationship_tasks:
        logging.info("Starte parallele Verarbeitung der komplexen RELATIONSHIP_TO_SUBJECT-Relationen")
        execute_relationship_batch_parallel(
            complex_relationship_tasks,
            total_relationship_count,
            # total_offset=processed_simple,
            total_offset=len(simple_relationship_tasks),
            max_workers=optimal_workers,
        )

    logging.info(f"Dauer Erstellung Relationen: {time.time() - start2:.2f} Sekunden")
    logging.info(f"Gesamtdauer: {time.time() - start:.2f} Sekunden")

# create dictionary ist auskommentiert
# existierende Relationen sind auskommentiert, um die Verarbeitung zu beschleunigen