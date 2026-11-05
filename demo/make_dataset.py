"""Generate the demo dataset: a realistic synthetic customer-churn CSV.

Why synthetic: reproducible, no licence issues, no PII — and the analysis journey
is the same as with any real dataset. 700 rows, 11 columns, mild messiness.
"""
import random

random.seed(42)

COLUMNS = "customer_id,tenure_months,monthly_charges,total_charges,contract,internet_service,payment_method,support_tickets_90d,avg_speed_mbps,auto_pay,churn"
rows = [COLUMNS]
contracts = ["month-to-month", "one-year", "two-year"]
internet = ["dsl", "fiber", "none"]
payment = ["credit-card", "bank-transfer", "electronic-check", "mailed-check"]

for i in range(1, 701):
    contract = random.choices(contracts, weights=[0.5, 0.25, 0.25])[0]
    svc = random.choices(internet, weights=[0.35, 0.45, 0.2])[0]
    tenure = random.randint(1, 72)
    base = 24 + (12 if svc == "fiber" else 4 if svc == "dsl" else 0)
    monthly = round(base + tenure * 0.08 + random.uniform(-5, 15), 2)
    total = round(monthly * tenure * random.uniform(0.97, 1.03), 2)
    tickets = random.choices([0, 1, 2, 3, 4, 7], weights=[0.45, 0.2, 0.15, 0.1, 0.07, 0.03])[0]
    speed = {"dsl": random.randint(10, 45), "fiber": random.randint(90, 940), "none": 0}[svc]
    auto = random.random() < 0.45
    method = random.choice(payment)
    # churn drivers: month-to-month + high tickets + electronic check + low tenure
    risk = 0.05
    risk += 0.25 if contract == "month-to-month" else 0.02
    risk += 0.05 * tickets
    risk += 0.12 if method == "electronic-check" else 0
    risk += 0.15 if tenure < 12 else 0
    risk += 0.1 if svc == "fiber" and monthly > 90 else 0
    churn = int(random.random() < min(risk, 0.9))
    rows.append(f"c{i:04d},{tenure},{monthly},{total},{contract},{svc},{method},{tickets},{speed},{'yes' if auto else 'no'},{churn}")

with open("customer_churn_700.csv", "w") as f:
    f.write("\n".join(rows) + "\n")
print(f"wrote customer_churn_700.csv: {len(rows) - 1} rows")
