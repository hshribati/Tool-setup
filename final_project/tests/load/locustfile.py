from locust import HttpUser, task, between


class WeatherUser(HttpUser):
    wait_time = between(1, 2)

    @task(3)
    def weather(self):
        self.client.get("/weather/60601", name="/weather/:zip")

    @task(1)
    def health(self):
        self.client.get("/health", name="/health")
