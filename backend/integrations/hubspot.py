# hubspot.py

from datetime import datetime
import json
import secrets

from typing import List
import urllib
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import base64
import requests
from integrations.integration_item import IntegrationItem

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis
import os
from dotenv import load_dotenv
load_dotenv()

CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID")
CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET")
REDIRECT_URI = os.getenv("HUBSPOT_REDIRECT_URI")

authorization_url = (
    f"https://app.hubspot.com/oauth/authorize?"
    f"client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}"
    f"&scope=crm.objects.contacts.read%20crm.objects.contacts.write%20crm.schemas.contacts.read"
)


encoded_client_id_secret = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

async def authorize_hubspot(user_id, org_id):
    state_data = {
        "state": secrets.token_urlsafe(32),
        "user_id": user_id,
        "org_id": org_id
    }
    encoded_state = json.dumps(state_data)
    await add_key_value_redis(f"hubspot_state:{org_id}:{user_id}", encoded_state, expire=600)

    return f"{authorization_url}&state={encoded_state}"

async def oauth2callback_hubspot(request: Request):
    if request.query_params.get("error"):
        raise HTTPException(status_code=400, detail=request.query_params.get("error"))

    code = request.query_params.get("code")
    encoded_state = request.query_params.get("state")

    # Properly decode the URL-encoded JSON
    decoded_state = urllib.parse.unquote(encoded_state)
    state_data = json.loads(decoded_state)

    original_state = state_data.get("state")
    user_id = state_data.get("user_id")
    org_id = state_data.get("org_id")

    saved_state = await get_value_redis(f"hubspot_state:{org_id}:{user_id}")

    if not saved_state or original_state != json.loads(saved_state).get("state"):
        raise HTTPException(status_code=400, detail="State does not match.")

    async with httpx.AsyncClient() as client:
        response, _ = await asyncio.gather(
            client.post(
                "https://api.hubapi.com/oauth/v1/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "redirect_uri": REDIRECT_URI,
                    "code": code
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            ),
            delete_key_redis(f"hubspot_state:{org_id}:{user_id}")
        )

    await add_key_value_redis(
        f"hubspot_credentials:{org_id}:{user_id}",
        json.dumps(response.json()),
        expire=3600
    )

    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    print("OAuth callback received, saved credentials.")

    return HTMLResponse(content=close_window_script)

async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f"hubspot_credentials:{org_id}:{user_id}")
    if not credentials:
        raise HTTPException(status_code=400, detail="No credentials found.")
    credentials = json.loads(credentials)
    # await delete_key_redis(f"hubspot_credentials:{org_id}:{user_id}")

    return credentials


def create_integration_item_metadata_object(item: dict) -> IntegrationItem:
    props = item.get("properties", {})
    created_at = item.get("createdAt")
    updated_at = item.get("updatedAt")

    return IntegrationItem(
        id=item.get("id"),
        name=props.get("firstname", "") + " " + props.get("lastname", ""),
        type="Contact",
        creation_time=datetime.fromisoformat(created_at.replace("Z", "+00:00")) if created_at else None,
        last_modified_time=datetime.fromisoformat(updated_at.replace("Z", "+00:00")) if updated_at else None,
        visibility=True,
        url=f"https://app.hubspot.com/contacts/{item.get('id')}" if item.get("id") else None,
    )


async def get_items_hubspot(credentials: str) -> List[IntegrationItem]:
    credentials = json.loads(credentials)
    access_token = credentials.get("access_token")

    if not access_token:
        raise HTTPException(status_code=401, detail="Missing access token")

    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, params={"limit": 10})
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"HubSpot API error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch HubSpot contacts")

    contacts = response.json().get("results", [])
    items = [create_integration_item_metadata_object(contact) for contact in contacts]

    print(f"\n HubSpot Integration Items:\n{[item.__dict__ for item in items]}")
    readable_string = "\n".join([
        f"{i+1}. {item.type} - {item.name} ({'in ' + item.parent_path_or_name if item.parent_path_or_name else 'ID: ' + item.id})"
        for i, item in enumerate(items)
    ])
    print("readable_string", readable_string)
    return readable_string