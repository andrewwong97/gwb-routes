class Location:
    def __init__(self, lat: float, lon: float, name: str = None):
        self.lat = lat
        self.lon = lon
        self.name = name
        
        if name is None:
            self.name = f"{self.lat},{self.lon}"

    def to_key(self):
        return f"{self.lat},{self.lon}"
    
    def get_name(self):
        return self.name

    def __str__(self):
        return f"{self.name}: {self.lat}, {self.lon}"

    def __repr__(self):
        return f"Location(lat={self.lat}, lon={self.lon}, name={self.name})"