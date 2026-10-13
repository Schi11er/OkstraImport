import os
import re
import requests
import threading
from dotenv import load_dotenv
import logging

load_dotenv()

GRAPHQL_ENDPOINT = os.getenv("DATACAT_URL") + "/graphql"
USERNAME = os.getenv("DATACAT_USERNAME")
PASSWORD = os.getenv("DATACAT_PASSWORD")

_graphq_request_lock = threading.Lock()
_graphq_request_condition = threading.Condition(_graphq_request_lock)
_pending_graphql_requests = 0


def _begin_graphql_request():
	global _pending_graphql_requests
	with _graphq_request_condition:
		_pending_graphql_requests += 1


def _end_graphql_request():
	global _pending_graphql_requests
	with _graphq_request_condition:
		_pending_graphql_requests = max(0, _pending_graphql_requests - 1)
		_graphq_request_condition.notify_all()


def wait_for_pending_graphql_requests():
	with _graphq_request_condition:
		while _pending_graphql_requests > 0:
			_graphq_request_condition.wait()

class GraphQLTimeoutError(Exception):
    """Request timed out - unklar ob die Operation serverseitig trotzdem ausgeführt wurde."""
    pass


class GraphQLError(Exception):
    """GraphQL-Response enthielt einen 'errors'-Block."""
    def __init__(self, errors):
        self.errors = errors
        super().__init__(errors[0].get("message", str(errors)))


def graphql_request(query, variables=None, token=None, timeout=180, raise_on_error=True):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    _begin_graphql_request()
    try:
        response = requests.post(
            GRAPHQL_ENDPOINT,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=timeout
        )
        response.raise_for_status()
        data = response.json()
        
        if variables.get("id") == "OkstraId" and "errors" in data:
            return data  # Spezielle Behandlung für OkstraId-Fehler, um die Verarbeitung fortzusetzen

        if "errors" in data:
            logging.error(f"GraphQL-Fehler: {data['errors'][0]['message']}")
            if raise_on_error:
                raise GraphQLError(data["errors"])

        return data

    except requests.exceptions.ReadTimeout as e:
        # logging.warning(
        #     f"GraphQL-Request-Timeout (timeout={timeout}s). "
        #     f"Operation wurde möglicherweise serverseitig trotzdem ausgeführt."
        # )
        raise GraphQLTimeoutError(str(e)) from e

    finally:
        _end_graphql_request()

def login():
	query = """
	mutation Login($username: ID!, $password: String!) {
		login(input: {username: $username, password: $password})
	}
	"""
	variables = {"username": USERNAME, "password": PASSWORD}
	result = graphql_request(query, variables)
	# if "errors" in result:
		# logging.error(f"Fehler beim Login: {result['errors'][0]['message']}")
	return result["data"]["login"]

def create_catalog_entry(token, catalogEntryType, properties, tagId):
	query = """
	mutation CreateCatalogEntry($input: CreateCatalogEntryInput!) {
		createCatalogEntry(input: $input) {
			catalogEntry {__typename}
		}
	}
	"""
	variables = {"input": {"catalogEntryType": catalogEntryType, "properties": properties, "tags": tagId}}
	# variables = {"input": {"catalogEntryType": catalogEntryType, "properties": properties}}
	result = graphql_request(query, variables, token)
	return result
	# if "errors" in result:
	# 	# logging.error(f"Fehler beim Erstellen des Katalogeintrags: {result['errors'][0]['message']}")
	# 	return None
	# else:
	# 	return result["data"]["createCatalogEntry"]["catalogEntry"]
 	
	

def create_relationship(token, relationshipType, properties, fromId, toIds):
    
	query = """
	mutation CreateRelationship($input: CreateRelationshipInput!) {
		createRelationship(input: $input) {
			catalogEntry { __typename }
		}
	}
	"""
	if properties is not None:
		variables = {"input": {"relationshipType": relationshipType, "properties": properties, "fromId": fromId, "toIds": toIds}}
	else:
		variables = {"input": {"relationshipType": relationshipType, "fromId": fromId, "toIds": toIds}}

	result = graphql_request(query, variables, token)
	return result

def create_tag(token, tag_name, tagId):
	query = """
	mutation CreateTag($input: CreateTagInput!) {
		createTag(input: $input) {
			tag { id name}
		}
	}
	"""
	variables = {"input": {"name": tag_name, "tagId": tagId}}
	result = graphql_request(query, variables, token)
	return result["data"]["createTag"]["tag"]

def get_tag(token, tagId):
	query = """
	query GetTag($id: ID!) {
		getTag(id: $id) {
			id
			name
		}
	}
	"""
	variables = {"id": tagId}
	result = graphql_request(query, variables, token)
	if "errors" in result:
		logging.error(f"Fehler beim Abrufen des Tags: {result}")
		return None
	else:
		return result["data"]["getTag"]

def add_tag(token, entryId, tagId):
	query = """
	mutation AddTag($input: AddTagInput!) {
		addTag(input: $input) {
			catalogEntry { __typename }
		}
	}
	"""
	variables = {"input": {"catalogEntryId": entryId, "tagId": tagId}}
	result = graphql_request(query, variables, token)
	if "errors" in result:
		logging.error(f"Fehler beim Hinzufügen des Tags: {result}")
		return None
	else:
		return result["data"]["addTag"]["catalogEntry"]

def validate_entity(token, entityId):
	query = """
	query ValidateEntity($id: ID!) {
		node(id: $id) {
			id
		}
	}
	"""
	variables = {"id": entityId}
	result = graphql_request(query, variables, token)
	if result["data"]:
		return True
	return False