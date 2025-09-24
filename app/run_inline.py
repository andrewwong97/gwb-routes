#!/usr/bin/env python3

import sys

from api_client import ApiClient

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <GOOGLE_MAPS_API_KEY>")
        sys.exit(1)

    api_key = sys.argv[1]
    
    response_text = ApiClient(api_key).get_times_as_text()

    print(response_text)


if __name__ == "__main__":
    main()

