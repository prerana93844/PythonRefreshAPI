from fastapi import FastAPI, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta
import httpx

app = FastAPI()

POWER_BI_API_URL = "https://api.powerbi.com/v1.0/myorg/datasets/{datasetId}/refreshes"
TOKEN_URL = "https://login.microsoftonline.com/85f78c4c-ad11-4735-9624-0b2c11611dff/oauth2/token"  # Replace with your tenant ID

CLIENT_ID = "d59456b1-5e3a-477c-ad13-8c29a79c85df"
CLIENT_SECRET = "oNb9-P1Ajm-CEb.1GMmuHEu1K1nUI_6WqV"
USERNAME = "svcpowerbi02@polarisind.com"
PASSWORD = "QYuqHUusdkByNT"
RESOURCE = "https://analysis.windows.net/powerbi/api"

# Token cache
token_cache = {
    "access_token": None,
    "expiry": datetime.utcnow()
}

async def get_access_token():
    """
    Fetches and caches an access token from the Azure AD authentication endpoint.
    """
    global token_cache
    # Check if the cached token is still valid
    if token_cache["access_token"] and token_cache["expiry"] > datetime.utcnow():
        return token_cache["access_token"]

    # Token request payload
    payload = {
        'grant_type': 'password',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'username': USERNAME,
        'password': PASSWORD,
        'resource': RESOURCE
    }

    # Fetch new token
    async with httpx.AsyncClient() as client:
        response = await client.post(TOKEN_URL, data=payload)
        if response.status_code == 200:
            data = response.json()
            expires_in=int(data.get("expires_in", 3600))
            token_cache["access_token"] = data["access_token"]
            token_cache["expiry"] = datetime.utcnow() + timedelta(seconds=expires_in)
            return token_cache["access_token"]
        else:
            raise HTTPException(status_code=response.status_code, detail="Error obtaining access token")

@app.get("/get-refresh-history")
async def get_refresh_history(
    datasetId: str = Query(..., description="The ID of the Power BI dataset"),
    days: Optional[int] = Query(90, description="Number of days to filter refresh history (default: 90)")
):
    """
    Fetch and filter refresh history for a Power BI dataset.
    """
    try:
        # Calculate the start date for filtering
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get access token
        access_token = await get_access_token()

        # Construct API request
        url = POWER_BI_API_URL.format(datasetId=datasetId)
        headers = {"Authorization": f"Bearer {access_token}"}

        # Call Power BI API
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
        
        # Handle API errors
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Error fetching data from Power BI API")
            )

        # Parse the API response
        refresh_history = response.json().get("value", [])

        # Filter refresh history by date
        filtered_history = [
            refresh for refresh in refresh_history
            if start_date <= datetime.strptime(refresh["startTime"], "%Y-%m-%dT%H:%M:%S.%fZ") <= end_date
        ]

        return {
            "filtered_refresh_history": filtered_history,
            "total_count": len(filtered_history)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))