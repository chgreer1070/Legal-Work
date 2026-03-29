"""
Locust HTTP load tests for the FX Recovery System.

Usage:
    # Web UI mode (http://localhost:8089):
    locust -f stress_tests/locustfile.py --host=http://localhost:5000

    # Headless mode:
    locust -f stress_tests/locustfile.py --host=http://localhost:5000 \
        --headless -u 50 -r 5 -t 3m
"""

import random

from locust import HttpUser, between, task, tag


class ReadOnlyUser(HttpUser):
    """Simulates dashboard viewers hitting read-only endpoints."""

    weight = 3
    wait_time = between(0.5, 2)

    @tag("read", "dashboard")
    @task(5)
    def dashboard_summary(self):
        self.client.get("/fx/api/dashboard/summary", name="/fx/api/dashboard/summary")

    @tag("read", "dashboard")
    @task(3)
    def exposure_by_pair(self):
        self.client.get(
            "/fx/api/dashboard/exposure-by-pair",
            name="/fx/api/dashboard/exposure-by-pair",
        )

    @tag("read", "rates")
    @task(4)
    def current_rates(self):
        self.client.get("/fx/api/rates", name="/fx/api/rates")

    @tag("read", "rates")
    @task(3)
    def rate_history(self):
        pair = random.choice(["USD/BRL", "USD/MXN", "USD/CNY"])
        days = random.choice([7, 30, 90])
        self.client.get(
            f"/fx/api/rates/{pair}/history?days={days}",
            name="/fx/api/rates/[pair]/history",
        )

    @tag("read", "contracts")
    @task(3)
    def list_contracts(self):
        self.client.get("/fx/api/contracts", name="/fx/api/contracts")

    @tag("read", "contracts")
    @task(2)
    def contract_detail(self):
        # Try contract IDs 1-3 (seeded demo data)
        cid = random.randint(1, 3)
        self.client.get(
            f"/fx/api/contracts/{cid}", name="/fx/api/contracts/[id]"
        )

    @tag("read", "alerts")
    @task(3)
    def list_alerts(self):
        self.client.get("/fx/api/alerts", name="/fx/api/alerts")

    @tag("read", "alerts")
    @task(2)
    def list_alerts_filtered(self):
        status = random.choice(["triggered", "pending_approval", "approved", "sent"])
        self.client.get(
            f"/fx/api/alerts?status={status}",
            name="/fx/api/alerts?status=[status]",
        )

    @tag("read", "alerts")
    @task(1)
    def alert_detail(self):
        # Try a few alert IDs — some may 404 and that's fine
        aid = random.randint(1, 10)
        with self.client.get(
            f"/fx/api/alerts/{aid}",
            name="/fx/api/alerts/[id]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 404:
                resp.success()  # 404 is expected for non-existent alerts

    @tag("read", "predictions")
    @task(2)
    def list_predictions(self):
        self.client.get("/fx/api/predictions", name="/fx/api/predictions")

    @tag("read", "audit")
    @task(1)
    def audit_log(self):
        self.client.get("/fx/api/audit", name="/fx/api/audit")

    @tag("read", "audit")
    @task(1)
    def audit_log_filtered(self):
        entity_type = random.choice(["contract", "alert", "rate"])
        self.client.get(
            f"/fx/api/audit?entity_type={entity_type}&limit=50",
            name="/fx/api/audit?entity_type=[type]",
        )


class WriteUser(HttpUser):
    """Simulates users performing write operations."""

    weight = 1
    wait_time = between(1, 4)

    @tag("write", "rates")
    @task(3)
    def refresh_rates(self):
        self.client.post("/fx/api/rates/refresh", name="/fx/api/rates/refresh")

    @tag("write", "predictions")
    @task(2)
    def run_predictions(self):
        self.client.post(
            "/fx/api/predictions/run",
            json={"threshold_pct": 5.0, "horizon_days": 30},
            name="/fx/api/predictions/run",
        )

    @tag("write", "alerts")
    @task(1)
    def approve_alert(self):
        # First find a triggered or pending_approval alert
        with self.client.get(
            "/fx/api/alerts?status=triggered",
            name="/fx/api/alerts?status=triggered [write]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                alerts = resp.json()
                if alerts:
                    alert_id = random.choice(alerts)["id"]
                    with self.client.post(
                        f"/fx/api/alerts/{alert_id}/dismiss",
                        json={"dismissed_by": "stress_test"},
                        name="/fx/api/alerts/[id]/dismiss",
                        catch_response=True,
                    ) as write_resp:
                        # 400 is expected if alert state changed between read and write
                        if write_resp.status_code in (200, 400):
                            write_resp.success()
                resp.success()


class MixedUser(HttpUser):
    """Simulates realistic user doing both reads and writes."""

    weight = 2
    wait_time = between(1, 3)

    @tag("mixed", "dashboard")
    @task(5)
    def browse_dashboard(self):
        """Simulate loading the full dashboard (multiple API calls)."""
        self.client.get("/fx/api/dashboard/summary", name="/fx/api/dashboard/summary [mixed]")
        self.client.get("/fx/api/dashboard/exposure-by-pair", name="/fx/api/dashboard/exposure-by-pair [mixed]")
        self.client.get("/fx/api/rates", name="/fx/api/rates [mixed]")

    @tag("mixed", "contracts")
    @task(3)
    def browse_contracts(self):
        """Simulate browsing the contract list then viewing one."""
        resp = self.client.get("/fx/api/contracts", name="/fx/api/contracts [mixed]")
        if resp.status_code == 200:
            contracts = resp.json()
            if contracts:
                cid = random.choice(contracts)["id"]
                self.client.get(
                    f"/fx/api/contracts/{cid}",
                    name="/fx/api/contracts/[id] [mixed]",
                )

    @tag("mixed", "alerts")
    @task(3)
    def browse_alerts(self):
        """Simulate browsing alerts then viewing one."""
        resp = self.client.get("/fx/api/alerts", name="/fx/api/alerts [mixed]")
        if resp.status_code == 200:
            alerts = resp.json()
            if alerts:
                aid = random.choice(alerts)["id"]
                with self.client.get(
                    f"/fx/api/alerts/{aid}",
                    name="/fx/api/alerts/[id] [mixed]",
                    catch_response=True,
                ) as r:
                    if r.status_code in (200, 404):
                        r.success()

    @tag("mixed")
    @task(1)
    def refresh_and_check(self):
        """Simulate a rate refresh followed by checking the dashboard."""
        self.client.post("/fx/api/rates/refresh", name="/fx/api/rates/refresh [mixed]")
        self.client.get("/fx/api/dashboard/summary", name="/fx/api/dashboard/summary [after refresh]")
