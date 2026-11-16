import time
import requests


def probe(url):
    start = time.monotonic()

    try:
        response = requests.get(url, timeout=5)
        elapsed = time.monotonic() - start

        return {
            "status": response.status_code,
            "success": response.status_code == 200,
            "response_time": round(elapsed, 3)
        }

    except requests.RequestException:
        return {
            "status": 0,
            "success": False,
            "response_time": round(
                time.monotonic() - start, 3
            )
        }


if __name__ == "__main__":
    url = input("Enter application URL: ")
    result = probe(url)
    print(result)

