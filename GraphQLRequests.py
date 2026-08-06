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

def graphql_request(query, variables=None, token=None):
	headers = {"Content-Type": "application/json"}
	if token:
		headers["Authorization"] = f"Bearer {token}"
	_begin_graphql_request()
	try:
		response = requests.post(
			GRAPHQL_ENDPOINT,
			json={"query": query, "variables": variables},
			headers=headers,
			timeout=60
		)
		response.raise_for_status()
		if "errors" in response.json():
			logging.error(f"GraphQL-Fehler: {response.json()['errors'][0]['message']}")
		return response.json()
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
	if "errors" in result:
		logging.error(f"Fehler beim Login: {result['errors'][0]['message']}")
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
	result = graphql_request(query, variables, token)
	if "errors" in result:
		logging.error(f"Fehler beim Erstellen des Katalogeintrags: {result['errors'][0]['message']}")
		return None
	else:
		return result["data"]["createCatalogEntry"]["catalogEntry"]
	

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