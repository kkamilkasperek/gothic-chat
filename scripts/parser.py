import json
import os
import re
from typing import Any

import mwparserfromhell


def clean_value(value: str, is_list: bool = False) -> Any:
    """
    Removes wiki markup. If is_list is True, attempts to split by comma or <br> and returns a list.
    """
    if not value:
        if is_list:
            return []
        return ""
    
    if is_list:
        # Replace <br> tags with commas before stripping code so they don't get lost
        value = re.sub(r'<br\s*/?>', ',', value, flags=re.IGNORECASE)
        
    # Parse value with mwparserfromhell to strip code
    parsed = mwparserfromhell.parse(value)
    
    # Extract values from known templates before stripping
    for t in parsed.filter_templates():
        t_name = str(t.name).strip().lower()
        if t_name in ["wartość", "cena"]:
            params = [str(p.value).strip() for p in t.params]
            if len(params) == 2:
                parsed.replace(t, f"{params[1]} {params[0]}")
            elif len(params) == 1:
                parsed.replace(t, params[0])
                
    cleaned = parsed.strip_code().strip()
    
    if is_list:
        # Split by comma
        items = re.split(r',', cleaned)
        items = [item.strip() for item in items if item.strip()]
        return items
    
    return cleaned

def process_wikicode_inline(wikicode: mwparserfromhell.wikicode.Wikicode) -> tuple[list[str], dict[str, str]]:
    """
    Modifies wikicode in-place to format <ref> tags, and extract categories/languages.
    Returns (categories_list, languages_dict).
    """
    # 1. Handle <ref> tags
    for tag in wikicode.filter_tags(matches=lambda t: t.tag.lower() == "ref"):
        if tag.contents:
            inner_text = tag.contents.strip_code().strip()
            if inner_text:
                try:
                    wikicode.replace(tag, f" ({inner_text})")
                except ValueError:
                    pass
        else:
            try:
                wikicode.remove(tag)
            except ValueError:
                pass

    # 2. Extract Categories, Languages and Remove Images
    categories = []
    languages = {}
    image_prefixes = ("plik:", "file:", "image:", "grafika:")
    
    # We must be careful replacing while iterating. filter_wikilinks returns a list.
    for link in wikicode.filter_wikilinks():
        title = str(link.title).strip()
        title_lower = title.lower()
        if title_lower.startswith("kategoria:"):
            cat_name = title[len("kategoria:"):].strip()
            if cat_name not in categories:
                categories.append(cat_name)
            try:
                wikicode.remove(link)
            except ValueError:
                pass
        elif re.match(r'^[a-z]{2,3}:', title, re.IGNORECASE):
            lang_code, lang_name = title.split(":", 1)
            languages[lang_code.lower()] = lang_name.strip()
            try:
                wikicode.remove(link)
            except ValueError:
                pass
        elif title_lower.startswith(image_prefixes):
            try:
                wikicode.remove(link)
            except ValueError:
                pass
                
    # 3. Format wikitables as inline CSV
    for tag in wikicode.filter_tags():
        if str(tag.tag).lower() == "table":
            headers = []
            rows = []
            current_row = []
            
            for node in tag.contents.filter_tags(recursive=False):
                tag_name = str(node.tag).lower()
                if tag_name == "tr":
                    if current_row:
                        rows.append(current_row)
                        current_row = []
                    tr_row = []
                    for cell in node.contents.filter_tags(recursive=False):
                        cell_tag = str(cell.tag).lower()
                        if cell_tag == "th":
                            headers.append(cell.contents.strip_code().strip())
                        elif cell_tag == "td":
                            tr_row.append(cell.contents.strip_code().strip())
                    if tr_row:
                        rows.append(tr_row)
                elif tag_name == "th":
                    headers.append(node.contents.strip_code().strip())
                elif tag_name == "td":
                    current_row.append(node.contents.strip_code().strip())
            
            if current_row:
                rows.append(current_row)
                
            # Filter out image columns
            num_cols = max(len(headers), max((len(r) for r in rows), default=0))
            cols_to_remove = set()
            image_header_names = {"obraz", "image", "grafika", "plik", "wygląd", "ikona", "ikonka"}
            
            for i in range(num_cols):
                is_image_header = i < len(headers) and headers[i].lower() in image_header_names
                
                is_all_empty = True
                has_any_row = False
                for row in rows:
                    if i < len(row):
                        has_any_row = True
                        if row[i] != "":
                            is_all_empty = False
                            break
                if not has_any_row:
                    is_all_empty = False
                
                if is_image_header or is_all_empty:
                    cols_to_remove.add(i)
                    
            if headers:
                headers = [h for i, h in enumerate(headers) if i not in cols_to_remove]
            
            filtered_rows = []
            for row in rows:
                filtered_row = [cell for i, cell in enumerate(row) if i not in cols_to_remove]
                if filtered_row:
                    filtered_rows.append(filtered_row)
            rows = filtered_rows
                
            # Construct MD text
            lines = ["\n"]
            
            if not headers and rows:
                headers = rows[0]
                rows = rows[1:]
                
            if headers:
                lines.append("| " + " | ".join(headers) + " |")
                lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                
            for row in rows:
                if headers:
                    row = row + [""] * max(0, len(headers) - len(row))
                lines.append("| " + " | ".join(row) + " |")
                
            lines.append("\n")
                
            md_text = "\n".join(lines)
            
            try:
                wikicode.replace(tag, md_text)
            except ValueError:
                pass
                
    return categories, languages

def parse_wikitext_to_dict(title: str, wikitext: str) -> dict:
    wikicode = mwparserfromhell.parse(wikitext)
    
    # Pre-process refs, categories, languages
    categories, languages = process_wikicode_inline(wikicode)
    
    # 1. Identify Tags, Type, and Infobox
    templates = wikicode.filter_templates()
    meta_templates = []
    infobox_data = {}
    record_type = "unknown"
    
    for template in templates:
        template_name = str(template.name).strip()
        
        # Check if this template is the main infobox (has named parameters with '=')
        is_infobox = any(param.showkey for param in template.params) if template.params else False
        
        if is_infobox and record_type == "unknown":
            # This is our main infobox
            record_type = template_name
            image_keys = {"podpis obrazu", "podpis", "obrazek"}
            for param in template.params:
                key = str(param.name).strip().lower()
                val = str(param.value).strip()
                if not val or key in image_keys:
                    continue
                
                is_list = key in ["posiadana broń", "posiadana zbroja"]
                infobox_data[key] = clean_value(val, is_list)
        elif record_type == "unknown":
            # This is a pre-infobox meta-template (e.g., Inne znaczenia, Niekanon)
            params_dict = {}
            for param in template.params:
                param_key = str(param.name).strip()
                param_val = str(param.value).strip()
                params_dict[param_key] = param_val
            
            meta_templates.append({
                "name": template_name,
                "params": params_dict
            })

    # 2. Extract Sections
    top_level_sections = []
    
    # Extract lead section (Wstęp)
    lead_nodes = []
    for node in wikicode.nodes:
        if isinstance(node, mwparserfromhell.nodes.heading.Heading):
            break
        lead_nodes.append(node)
        
    lead_wikicode = mwparserfromhell.wikicode.Wikicode(lead_nodes)
    cleaned_lead = lead_wikicode.strip_code().strip()
    
    if cleaned_lead:
        top_level_sections.append({
            "title": "Wstęp",
            "text": cleaned_lead,
            "subsections": []
        })

    stack = []

    # Extract other sections
    for section in wikicode.get_sections(levels=[2, 3, 4, 5, 6], include_lead=False, flat=True):
        headings = section.filter_headings()
        if headings:
            heading = headings[0]
            sec_title = heading.title.strip_code().strip()
            level = heading.level
            
            # Ignore "Przypisy"
            if sec_title.lower() == "przypisy":
                continue
                
            nodes_without_heading = [node for node in section.nodes if not isinstance(node, mwparserfromhell.nodes.heading.Heading)]
            sec_wikicode = mwparserfromhell.wikicode.Wikicode(nodes_without_heading)
            sec_text = sec_wikicode.strip_code().strip()
            
            new_sec = {
                "title": sec_title,
                "text": sec_text,
                "subsections": []
            }
            
            # Pop sections from stack that are deeper or at the same level
            while stack and stack[-1][0] >= level:
                stack.pop()
                
            if not stack:
                top_level_sections.append(new_sec)
            else:
                stack[-1][1]["subsections"].append(new_sec)
                
            stack.append((level, new_sec))

    def prune_empty(sections_list: list[dict]) -> list[dict]:
        result = []
        for s in sections_list:
            s["subsections"] = prune_empty(s["subsections"])
            if s["text"] or s["subsections"]:
                result.append(s)
        return result
        
    sections = prune_empty(top_level_sections)
    
    return {
        "title": title,
        "meta_templates": meta_templates,
        "type": record_type,
        "infobox": infobox_data,
        "categories": categories,
        "languages": languages,
        "sections": sections
    }

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    input_dir = os.path.join(project_root, "data", "raw_txt_examples")
    output_dir = os.path.join(project_root, "data", "parsed_json_examples")
    
    os.makedirs(output_dir, exist_ok=True)
    
    if not os.path.exists(input_dir):
        print(f"Input directory does not exist: {input_dir}")
        return

    for filename in os.listdir(input_dir):
        if filename.endswith(".txt"):
            title = filename[:-4]
            with open(os.path.join(input_dir, filename), "r", encoding="utf-8") as f:
                wikitext = f.read()
            
            result = parse_wikitext_to_dict(title, wikitext)
            
            with open(os.path.join(output_dir, f"{title}.json"), "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
