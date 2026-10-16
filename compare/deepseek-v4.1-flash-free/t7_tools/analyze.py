#!/usr/bin/env python3
"""sales.csv を集計して report.md を生成する。

不正行の条件（集計から除外）:
  - quantity または unit_price が空
  - 数値に変換できない
  - 0 以下
"""
import csv
from collections import defaultdict

CSV_PATH = "sales.csv"
OUT_PATH = "report.md"


def parse_positive(value):
    """正の整数として解釈できれば int を返す。それ以外は None。"""
    if value is None:
        return None
    s = value.strip()
    if s == "":
        return None
    try:
        n = int(s)
    except ValueError:
        return None
    if n <= 0:
        return None
    return n


def main():
    region_total = defaultdict(int)
    product_total = defaultdict(int)
    month_total = defaultdict(int)
    excluded = 0
    total_rows = 0

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            qty = parse_positive(row.get("quantity"))
            price = parse_positive(row.get("unit_price"))
            if qty is None or price is None:
                excluded += 1
                continue

            sales = qty * price
            region = row["region"]
            product = row["product"]
            month = row["date"][:7]  # YYYY-MM

            region_total[region] += sales
            product_total[product] += sales
            month_total[month] += sales

    # 地域別（売上降順）
    regions = sorted(region_total.items(), key=lambda kv: kv[1], reverse=True)
    # 商品別 上位3（売上降順）
    products = sorted(product_total.items(), key=lambda kv: kv[1], reverse=True)[:3]
    # 月別（古い順）
    months = sorted(month_total.items())

    lines = []
    lines.append("## 地域別売上")
    lines.append("")
    lines.append("| 地域 | 売上合計(円) |")
    lines.append("| --- | --- |")
    for region, total in regions:
        lines.append(f"| {region} | {total} |")
    lines.append("")
    lines.append("## 商品別売上上位3")
    lines.append("")
    lines.append("| 商品 | 売上合計(円) |")
    lines.append("| --- | --- |")
    for product, total in products:
        lines.append(f"| {product} | {total} |")
    lines.append("")
    lines.append("## 月別売上")
    lines.append("")
    lines.append("| 月 | 売上合計(円) |")
    lines.append("| --- | --- |")
    for month, total in months:
        lines.append(f"| {month} | {total} |")
    lines.append("")
    lines.append("## 除外行")
    lines.append("")
    lines.append(f"除外した行数: {excluded}")
    lines.append("")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"total data rows: {total_rows}")
    print(f"excluded rows: {excluded}")
    print(f"valid rows: {total_rows - excluded}")


if __name__ == "__main__":
    main()
