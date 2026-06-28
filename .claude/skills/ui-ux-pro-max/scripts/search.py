#!/usr/bin/env python3
"""UI/UX Pro Max - Design Intelligence Search Tool.

Searchable database of design recommendations across 11 domains:
product, style, color, typography, chart, ux, landing, google-fonts,
react, web, prompt.
"""

import argparse
import csv
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DOMAINS = {
    "product": "product.csv",
    "style": "style.csv",
    "color": "color.csv",
    "typography": "typography.csv",
    "chart": "chart.csv",
    "ux": "ux.csv",
    "landing": "landing.csv",
    "google-fonts": "google-fonts.csv",
    "react": "react.csv",
    "web": "web.csv",
    "prompt": "prompt.csv",
}

STACKS = {
    "react-native": "react.csv",
}


def load_csv(filename):
    path = DATA_DIR / filename
    if not path.exists():
        print(f"Warning: {path} not found", file=sys.stderr)
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def score_row(row, keywords):
    text = " ".join(str(v).lower() for v in row.values())
    score = 0
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in text:
            count = text.count(kw_lower)
            score += count
    return score


def search_rows(rows, query, max_results=10):
    keywords = query.strip().split()
    if not keywords:
        return rows[:max_results]
    scored = []
    for row in rows:
        s = score_row(row, keywords)
        if s > 0:
            scored.append((s, row))
    scored.sort(key=lambda x: -x[0])
    return [row for _, row in scored[:max_results]]


def box_line(label, value, width=72):
    content = f"  {label}: {value}"
    if len(content) > width - 2:
        content = content[: width - 5] + "..."
    return f"|{content:<{width - 2}}|"


def format_domain_ascii(domain, results):
    if not results:
        return f"No results found in domain '{domain}'."
    lines = []
    border = "+" + "-" * 72 + "+"
    lines.append(border)
    lines.append(f"|{'  Domain: ' + domain.upper():<72}|")
    lines.append(f"|{'  Results: ' + str(len(results)):<72}|")
    lines.append(border)
    for i, row in enumerate(results, 1):
        lines.append(f"|{f'  [{i}]':<72}|")
        for key, val in row.items():
            if val:
                lines.append(box_line(key, val))
        lines.append(border)
    return "\n".join(lines)


def format_domain_markdown(domain, results):
    if not results:
        return f"No results found in domain `{domain}`."
    lines = [f"## Domain: {domain.upper()}", f"**{len(results)} results**\n"]
    for i, row in enumerate(results, 1):
        lines.append(f"### Result {i}")
        for key, val in row.items():
            if val:
                lines.append(f"- **{key}**: {val}")
        lines.append("")
    return "\n".join(lines)


def pick_best(rows, query, fallback_index=0):
    results = search_rows(rows, query, max_results=1)
    if results:
        return results[0]
    return rows[fallback_index] if rows else {}


def _load_design_system_data(query):
    product = pick_best(load_csv(DOMAINS["product"]), query)
    style = pick_best(load_csv(DOMAINS["style"]), query)
    color = pick_best(load_csv(DOMAINS["color"]), query)
    typo = pick_best(load_csv(DOMAINS["typography"]), query)
    landing = pick_best(load_csv(DOMAINS["landing"]), query)
    return product, style, color, typo, landing


def generate_design_system(query, project_name=None, fmt="ascii"):
    data = _load_design_system_data(query)
    title = project_name or "Design System"
    if fmt == "markdown":
        return format_design_system_markdown(title, *data)
    return format_design_system_ascii(title, *data)


def format_design_system(query, project_name=None):
    data = _load_design_system_data(query)
    title = project_name or "Design System"
    return {
        "ascii": format_design_system_ascii(title, *data),
        "markdown": format_design_system_markdown(title, *data),
    }


def format_design_system_ascii(title, product, style, color, typo, landing):
    w = 74
    border = "+" + "=" * w + "+"
    sep = "+" + "-" * w + "+"
    lines = [border]
    lines.append(f"|{'  DESIGN SYSTEM: ' + title.upper():^{w}}|")
    lines.append(border)

    def section(header, data, keys):
        lines.append(f"|{'  ' + header:<{w}}|")
        lines.append(sep)
        for k in keys:
            v = data.get(k, "")
            if v:
                label = k.replace("_", " ").title()
                content = f"    {label}: {v}"
                if len(content) > w - 2:
                    content = content[: w - 5] + "..."
                lines.append(f"|{content:<{w}}|")
        lines.append(sep)

    section("PRODUCT MATCH", product,
            ["name", "category", "keywords", "recommended_style", "layout", "description"])
    section("STYLE", style,
            ["name", "keywords", "description", "background", "border_radius", "shadows", "effects"])
    section("COLOR PALETTE", color,
            ["name", "primary", "secondary", "accent", "background", "surface", "text", "description"])
    section("TYPOGRAPHY", typo,
            ["heading", "body", "scale", "line_height", "description", "pairing_type"])
    section("LANDING PAGE", landing,
            ["section", "layout", "cta", "description"])

    if style.get("anti_patterns"):
        lines.append(f"|{'  ANTI-PATTERNS':<{w}}|")
        lines.append(sep)
        lines.append(f"|{'    ' + style.get('anti_patterns', ''):<{w}}|")
        lines.append(border)

    return "\n".join(lines)


def format_design_system_markdown(title, product, style, color, typo, landing):
    lines = [f"# Design System: {title}\n"]

    def section(header, data, keys):
        lines.append(f"## {header}\n")
        for k in keys:
            v = data.get(k, "")
            if v:
                lines.append(f"- **{k.replace('_', ' ').title()}**: {v}")
        lines.append("")

    section("Product Match", product,
            ["name", "category", "keywords", "recommended_style", "layout", "description"])
    section("Style", style,
            ["name", "keywords", "description", "background", "border_radius", "shadows", "effects"])
    section("Color Palette", color,
            ["name", "primary", "secondary", "accent", "background", "surface", "text", "description"])
    section("Typography", typo,
            ["heading", "body", "scale", "line_height", "description", "pairing_type"])
    section("Landing Page", landing,
            ["section", "layout", "cta", "description"])

    if style.get("anti_patterns"):
        lines.append("## Anti-Patterns\n")
        lines.append(f"- {style['anti_patterns']}\n")

    return "\n".join(lines)


def persist_design_system(content, project_name, page=None):
    ds_dir = Path("design-system")
    ds_dir.mkdir(exist_ok=True)
    pages_dir = ds_dir / "pages"
    pages_dir.mkdir(exist_ok=True)

    if page:
        page_file = pages_dir / f"{page}.md"
        page_file.write_text(content, encoding="utf-8")
        print(f"Saved page override: {page_file}")
    else:
        master_file = ds_dir / "MASTER.md"
        master_file.write_text(content, encoding="utf-8")
        print(f"Saved master design system: {master_file}")


def main():
    parser = argparse.ArgumentParser(
        description="UI/UX Pro Max - Design Intelligence Search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", nargs="?", default="", help="Search keywords")
    parser.add_argument("--design-system", action="store_true",
                        help="Generate a complete design system recommendation")
    parser.add_argument("--domain", type=str, choices=list(DOMAINS.keys()),
                        help="Search a specific domain")
    parser.add_argument("--stack", type=str, choices=list(STACKS.keys()),
                        help="Search stack-specific guidelines")
    parser.add_argument("-p", "--project", type=str, default=None,
                        help="Project name for design system output")
    parser.add_argument("-n", "--max-results", type=int, default=10,
                        help="Maximum number of results (default: 10)")
    parser.add_argument("-f", "--format", type=str, choices=["ascii", "markdown"],
                        default="ascii", help="Output format (default: ascii)")
    parser.add_argument("--persist", action="store_true",
                        help="Save design system to design-system/ directory")
    parser.add_argument("--page", type=str, default=None,
                        help="Page name for page-specific override")

    args = parser.parse_args()

    if not args.query and not args.design_system:
        parser.print_help()
        sys.exit(1)

    if args.design_system:
        if args.persist:
            both = format_design_system(args.query, project_name=args.project)
            print(both[args.format])
            persist_design_system(both["markdown"], args.project or "Project", page=args.page)
        else:
            print(generate_design_system(args.query, project_name=args.project, fmt=args.format))
        return

    if args.domain:
        rows = load_csv(DOMAINS[args.domain])
        results = search_rows(rows, args.query, max_results=args.max_results)
        if args.format == "markdown":
            print(format_domain_markdown(args.domain, results))
        else:
            print(format_domain_ascii(args.domain, results))
        return

    if args.stack:
        csv_file = STACKS[args.stack]
        rows = load_csv(csv_file)
        results = search_rows(rows, args.query, max_results=args.max_results)
        if args.format == "markdown":
            print(format_domain_markdown(args.stack, results))
        else:
            print(format_domain_ascii(args.stack, results))
        return

    for domain, csv_file in DOMAINS.items():
        rows = load_csv(csv_file)
        results = search_rows(rows, args.query, max_results=3)
        if results:
            if args.format == "markdown":
                print(format_domain_markdown(domain, results))
            else:
                print(format_domain_ascii(domain, results))


if __name__ == "__main__":
    main()
