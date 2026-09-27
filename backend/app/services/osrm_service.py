import httpx

OSRM_URL = "http://localhost:5000"


async def get_route(waypoints):
    """
    waypoints:
        [(longitude, latitude), ...]
    """

    coordinates = ";".join(
        f"{lon},{lat}"
        for lon, lat in waypoints
    )

    url = (
        f"{OSRM_URL}/route/v1/driving/"
        f"{coordinates}"
        "?overview=full&geometries=geojson"
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()

        data = response.json()

    route = data["routes"][0]

    return {
        "distance_km": round(
            route["distance"] / 1000, 2
        ),
        "duration_minutes": round(
            route["duration"] / 60, 2
        ),
        "geometry": route["geometry"]
    }
async def match_trajectory(points):
    """
    points:
        [(longitude, latitude), ...]
    """

    coordinates = ";".join(
        f"{lon},{lat}"
        for lon, lat in points
    )

    url = (
        f"{OSRM_URL}/match/v1/driving/"
        f"{coordinates}"
        "?overview=full&geometries=geojson"
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()

        return response.json()
    
async def get_travel_matrix(locations):

    coordinates = ";".join(
        f"{lon},{lat}"
        for lon, lat in locations
    )

    url = (
        f"{OSRM_URL}/table/v1/driving/"
        f"{coordinates}"
        "?annotations=duration,distance"
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()

        data = response.json()

    return {
        "durations": data["durations"],
        "distances": data["distances"]
    }