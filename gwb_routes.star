load("render.star", "render")
load("time.star", "time")
load("http.star", "http")

# Fetch route data from deployed web service
def fetch_route_data():
    r = http.get("https://gwb-routes.vercel.app/")
    if r.status_code != 200:
        return None
    return r.body()

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
    # Fetch data from web service
    route_data = fetch_route_data()
    
    if not route_data:
        return render.Root(child=render.Text(content="Service unavailable", font="6x10"))

    # Parse the text response
    # Expected format:
    # NJ to NYC:
    # Upper Level GWB: 25 mins
    # Lower Level GWB: 30 mins
    # 
    # NYC to NJ:
    # Upper Level GWB: 22 mins
    # Lower Level GWB: 28 mins
    
    lines = route_data.split("\n")
    
    # Default values
    up_to_nyc = "—"
    lo_to_nyc = "—"
    up_to_nj = "—"
    lo_to_nj = "—"
    
    # Parse the response
    current_section = ""
    for line in lines:
        line = line.strip()
        if line == "NJ to NYC:":
            current_section = "to_nyc"
        elif line == "NYC to NJ:":
            current_section = "to_nj"
        elif line.startswith("Upper Level GWB:"):
            time_str = line.replace("Upper Level GWB:", "").strip()
            if current_section == "to_nyc":
                up_to_nyc = time_str
            elif current_section == "to_nj":
                up_to_nj = time_str
        elif line.startswith("Lower Level GWB:"):
            time_str = line.replace("Lower Level GWB:", "").strip()
            if current_section == "to_nyc":
                lo_to_nyc = time_str
            elif current_section == "to_nj":
                lo_to_nj = time_str

    rows = []
    rows.append(render.Text(content="GWB → NYC", font="6x10"))
    rows.append(pill("Upper", up_to_nyc))
    rows.append(pill("Lower", lo_to_nyc))
    rows.append(render.Text(content="NYC → GWB", font="6x10"))
    rows.append(pill("Upper", up_to_nj))
    rows.append(pill("Lower", lo_to_nj))
    rows.append(render.Text(content=time.now().format("3:04 PM"), font="6x10"))

    return render.Root(child=render.Column(children=rows))