load("render.star", "render")
load("time.star", "time")
load("http.star", "http")

API_URL = "https://maps.googleapis.com/maps/api/directions/json"

# Fetch ETA in minutes
def fetch_minutes(api_key, orig, dest):
    if not api_key or not orig or not dest:
        return None

    q = {
        "origin": orig,
        "destination": dest,
        "mode": "driving",
        "units": "imperial",
        "key": api_key,
        "departure_time": "now",
        "traffic_model": "best_guess",
        "alternatives": "false",
    }

    r = http.get(API_URL, params=q)
    if r.status_code != 200:
        return None

    d = r.json()
    if d.get("status") != "OK":
        return None

    routes = d.get("routes", [])
    if not routes:
        return None

    legs = routes[0].get("legs", [])
    if not legs:
        return None

    leg = legs[0]
    duration_info = leg.get("duration_in_traffic") or leg.get("duration")
    if not duration_info:
        return None

    s = duration_info.get("value")
    if s == None:
        return None

    return (s + 30) // 60

# UI helpers
def pill(label, value):
    return render.Box(
        width=64,
        height=14,
        child=render.Row(
            main_align="space_between",
            children=[
                render.Text(content=label, font="6x10"),
                render.Text(content=value, font="6x10"),
            ],
        ),
    )

def main(config):
    api_key = config.get("api_key")
    upper_origin = config.get("upper_origin") or "40.854144,-73.965899"
    lower_origin = config.get("lower_origin") or "40.854603,-73.969891"
    destination = config.get("destination") or "40.8640,-73.9336"

    if not api_key:
        return render.Root(child=render.Text(content="Missing API key", font="6x10"))

    up = fetch_minutes(api_key, upper_origin, destination)
    lo = fetch_minutes(api_key, lower_origin, destination)

    rows = []
    rows.append(render.Text(content="GWB → Bus Terminal", font="6x10"))
    rows.append(pill("Upper", "%dm" % up if up != None else "—"))
    rows.append(pill("Lower", "%dm" % lo if lo != None else "—"))
    rows.append(render.Text(content=time.now().format("3:04 PM"), font="6x10"))

    return render.Root(child=render.Column(children=rows))