#!/usr/bin/env python3
"""Create a Jekyll recipe draft from a page with Schema.org Recipe JSON-LD."""

import argparse
import html
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import unicodedata
from urllib.parse import quote, urldefrag, urljoin, urlsplit

DOCS = Path(__file__).resolve().parents[1] / "docs"
CATEGORIES = ("Meals", "Baking", "Veg", "Breakfast", "Sides", "Snacks", "Mom")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_json = False
        self.blocks = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type", "").lower().strip() == "application/ld+json":
            self.in_json = True
            self.blocks.append([])
        elif tag in {"br", "p", "div", "li"}:
            self.text.append(" ")

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_json = False
        elif tag in {"p", "div", "li"}:
            self.text.append(" ")

    def handle_data(self, data):
        if self.in_json:
            self.blocks[-1].append(data)
        else:
            self.text.append(data)


def public_host(url):
    if "\\" in url or any(character.isspace() or ord(character) < 32 for character in url):
        raise ValueError("The recipe URL contains invalid characters.")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.netloc.endswith(":"):
        raise ValueError("Enter a public HTTPS recipe URL.")
    if parsed.username is not None or parsed.password is not None or parsed.port not in (None, 443):
        raise ValueError("Recipe URLs must use HTTPS on the default port without credentials.")
    hostname = parsed.hostname
    if not re.fullmatch(r"[a-zA-Z0-9.-]+", hostname) or "." not in hostname:
        raise ValueError("Enter a public recipe website hostname.")
    addresses = {entry[4][0] for entry in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(address).is_global or
                            ipaddress.ip_address(address).is_multicast for address in addresses):
        raise ValueError("The recipe hostname must resolve to public addresses.")
    return hostname, sorted(addresses, key=lambda address: (":" in address, address))


def fetch_page(url):
    url = urldefrag(url).url
    for _ in range(6):
        hostname, addresses = public_host(url)
        pinned = ",".join(f"[{address}]" if ":" in address else address for address in addresses)
        result = subprocess.run(
            ["curl", "--disable", "--silent", "--show-error", "--noproxy", "*",
             "--proto", "=https", "--resolve", f"{hostname}:443:{pinned}",
             "--connect-timeout", "6", "--max-time", "12", "--max-filesize", "5000000",
             "--globoff", "--user-agent", "RecipeCookbookImporter/1.0",
             "--write-out", "\n%{http_code}\n%{redirect_url}", "--url", url],
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise ValueError("Could not download the recipe page. Check the URL or try another source.")
        body, status, redirect = result.stdout.rsplit(b"\n", 2)
        if status in (b"301", b"302", b"303", b"307", b"308") and redirect:
            url = urldefrag(urljoin(url, redirect.decode("utf-8"))).url
            continue
        if status != b"200":
            raise ValueError(f"The recipe website returned HTTP {status.decode('ascii')}.")
        return body.decode("utf-8-sig", errors="replace"), url
    raise ValueError("The recipe URL redirected too many times.")


def plain_text(value):
    if not isinstance(value, str):
        return ""
    parser = PageParser()
    parser.feed(value)
    parser.close()
    return " ".join(html.unescape("".join(parser.text)).split())


def schema_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from schema_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from schema_nodes(child)


def has_type(node, name):
    types = node.get("@type", [])
    if isinstance(types, str):
        types = [types]
    return isinstance(types, list) and any(
        isinstance(item, str) and item.rsplit("/", 1)[-1] == name for item in types
    )


def instruction_lines(value):
    if isinstance(value, list):
        for item in value:
            yield from instruction_lines(item)
    elif isinstance(value, dict):
        if has_type(value, "HowToSection") or "itemListElement" in value:
            heading = plain_text(value.get("name"))
            steps = list(instruction_lines(value.get("itemListElement")))
            if steps and heading:
                yield heading, True
            yield from steps
        else:
            yield from instruction_lines(value.get("text") or value.get("item") or value.get("name"))
    elif text := plain_text(value):
        yield text, False


def extract_recipe(page):
    parser = PageParser()
    parser.feed(page)
    parser.close()
    for block in parser.blocks:
        try:
            data = json.loads("".join(block))
            for node in schema_nodes(data):
                if not has_type(node, "Recipe"):
                    continue
                title = plain_text(node.get("name"))
                description = plain_text(node.get("description"))
                ingredients = node.get("recipeIngredient")
                if isinstance(ingredients, str):
                    ingredients = ingredients.splitlines()
                if not isinstance(ingredients, list):
                    continue
                ingredients = [text for item in ingredients if (text := plain_text(item))]
                instruction_data = node.get("recipeInstructions")
                if isinstance(instruction_data, str):
                    instruction_data = instruction_data.splitlines()
                instructions = list(instruction_lines(instruction_data))
                if title and ingredients and any(not heading for _, heading in instructions):
                    return title, description, ingredients, instructions
        except (json.JSONDecodeError, RecursionError):
            continue
    raise ValueError("No complete Schema.org Recipe was found. Try a different recipe URL.")


def markdown_text(text):
    # Prevent external text from becoming Markdown, HTML, or Liquid markup.
    return re.sub(r"[!#&()*+<>\[\]\\_`{|}~-]", lambda match: f"&#{ord(match[0])};", text)


def slugify(value):
    ascii_name = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:100].rstrip("-")


def render_recipe(recipe, category, source_url):
    title, description, ingredients, instructions = recipe
    header = ["---", "layout: recipe", f"title: {json.dumps(title, ensure_ascii=False)}",
              f"categories: [{category}]"]
    if description:
        header.append(f"description: {json.dumps(description, ensure_ascii=False)}")
    for_source = quote(source_url, safe=":/?#[]@!$&'()*+,;=%.-_~").replace("(", "%28").replace(")", "%29")
    header.append(f"source_url: {json.dumps(for_source)}")
    lines = header + ["---", "", "## Ingredients", ""]
    lines.extend(f"- {markdown_text(ingredient)}" for ingredient in ingredients)
    lines.extend(["{: .ingredients }", "", "## Instructions", ""])
    step = 1
    for text, heading in instructions:
        if heading:
            lines.extend([f"### {markdown_text(text)}", ""])
            step = 1
        else:
            lines.extend([f"{step}. {markdown_text(text)}", ""])
            step += 1
    lines.append(f"[Original recipe]({for_source})")
    return "\n".join(lines) + "\n"


def write_recipe(recipe, category, source_url):
    slug = slugify(recipe[0])
    if not slug:
        raise ValueError("The recipe title could not be converted to a URL.")
    collection = DOCS / "_recipes"
    if any(slugify(path.stem) == slug for path in (*collection.iterdir(), *DOCS.iterdir())):
        raise ValueError(f"A recipe or page with the URL /{slug}/ already exists.")
    destination = collection / f"{slug}.md"
    with destination.open("x", encoding="utf-8") as output:
        output.write(render_recipe(recipe, category, source_url))
    return destination.relative_to(DOCS.parent)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Public HTTPS recipe URL")
    parser.add_argument("--category", choices=CATEGORIES, default="Meals")
    args = parser.parse_args()
    try:
        page, source_url = fetch_page(args.url)
        print(write_recipe(extract_recipe(page), args.category, source_url))
    except (ValueError, OSError) as error:
        parser.exit(1, f"Import failed: {error}\n")


if __name__ == "__main__":
    main()
