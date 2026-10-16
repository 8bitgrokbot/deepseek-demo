import csv
from collections import defaultdict

FILE = "sales.csv"

region_sales = defaultdict(int)
product_sales = defaultdict(int)
month_sales = defaultdict(int)
excluded = 0

with open(FILE, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            qty = int(row["quantity"])
            price = int(row["unit_price"])
        except (TypeError, ValueError):
            excluded += 1
            continue
        if qty <= 0 or price <= 0:
            excluded += 1
            continue
        sales = qty * price
        region_sales[row["region"]] += sales
        product_sales[row["product"]] += sales
        month = row["date"][:7]
        month_sales[month] += sales

def fmt(n):
    return str(n)  # カンマなし整数

regions = sorted(region_sales.items(), key=lambda x: -x[1])
products = sorted(product_sales.items(), key=lambda x: -x[1])[:3]
months = sorted(month_sales.items())

lines = []
lines.append("## 地域別売上")
lines.append("")
lines.append("| 地域 | 売上合計(円) |")
lines.append("| --- | --- |")
for r, s in regions:
    lines.append(f"| {r} | {fmt(s)} |")
lines.append("")
lines.append("## 商品別売上上位3")
lines.append("")
lines.append("| 商品 | 売上合計(円) |")
lines.append("| --- | --- |")
for p, s in products:
    lines.append(f"| {p} | {fmt(s)} |")
lines.append("")
lines.append("## 月別売上")
lines.append("")
lines.append("| 月 | 売上合計(円) |")
lines.append("| --- | --- |")
for m, s in months:
    lines.append(f"| {m} | {fmt(s)} |")
lines.append("")
lines.append("## 除外行")
lines.append("")
lines.append(f"除外した行数: {excluded}")
lines.append("")

with open("report.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("regions:", regions)
print("products_top3:", products)
print("months:", months)
print("excluded:", excluded)
