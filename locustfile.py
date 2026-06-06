import random
from locust import HttpUser, between, task


class BouncerUser(HttpUser):
    wait_time = between(0.05, 0.3)

    def on_start(self):
        # Each simulated user gets its own ID so rate limits are per-user
        self.client_id = f"user-{random.randint(1, 20)}"

    @task(15)
    def hit_protected(self):
        self.client.get(
            "/request",
            headers={"X-Client-ID": self.client_id},
            name="/request",
        )

    @task(1)
    def check_stats(self):
        self.client.get("/stats", name="/stats")

    @task(1)
    def advisor_recommend(self):
        self.client.get("/advisor", name="/advisor")

    @task(1)
    def advisor_apply(self):
        self.client.post("/advisor/apply", name="/advisor/apply")
