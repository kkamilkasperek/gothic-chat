import pytest

from scripts.parser import clean_value, parse_wikitext_to_dict


def test_clean_value_string():
    val = "[[Gniew Innosa]] to silny miecz"
    assert clean_value(val) == "Gniew Innosa to silny miecz"

def test_clean_value_list_comma():
    val = "[[Gniew Innosa]], [[Miecz]]"
    assert clean_value(val, is_list=True) == ["Gniew Innosa", "Miecz"]

def test_clean_value_list_br():
    val = "[[Gniew Innosa]]<br/>[[Miecz]]<br>Topór"
    assert clean_value(val, is_list=True) == ["Gniew Innosa", "Miecz", "Topór"]

def test_parse_wikitext_to_dict_basic():
    wikitext = """{{Inne znaczenia|postaci z [[Gothic 3]]|Ben (Mroczne Tajemnice)|postać z Mrocznych Tajemnic}}
{{Niekanon}}
{{Postać
 |Imię                 = Gomez
 |Poziom               = 100
 |Posiadana broń       = [[Gniew Innosa]]
 |Posiadana zbroja     = Pancerz Gomeza, [[Lekka zbroja]]
}}
'''Gomez''' to szef Starego Obozu<ref name="a">Z gry</ref>. I już<ref name="a"/>.

== Przed akcją gry ==
Już jako więzień zebrał wokół siebie ludzi.

== Przypisy ==
<references />

[[Kategoria:Magnaci]]
[[Kategoria:Postacie z Gothic]]
[[en:Gomez]]
[[ru:Гомез]]
"""
    result = parse_wikitext_to_dict("Gomez", wikitext)
    
    assert result["title"] == "Gomez"
    
    # Check meta_templates
    assert len(result["meta_templates"]) == 2
    assert result["meta_templates"][0]["name"] == "Inne znaczenia"
    assert result["meta_templates"][0]["params"]["1"] == "postaci z [[Gothic 3]]"
    
    assert result["type"] == "Postać"
    
    # Check lowercase infobox keys
    assert result["infobox"]["imię"] == "Gomez"
    assert result["infobox"]["poziom"] == "100"
    assert result["infobox"]["posiadana broń"] == ["Gniew Innosa"]
    assert result["infobox"]["posiadana zbroja"] == ["Pancerz Gomeza", "Lekka zbroja"]
    
    # Check sections (Przypisy should be ignored)
    assert len(result["sections"]) == 2
    
    assert result["sections"][0]["title"] == "Wstęp"
    # Refs should be formatted as (Z gry) and empty refs stripped
    assert result["sections"][0]["text"] == "Gomez to szef Starego Obozu (Z gry). I już."
    
    assert result["sections"][1]["title"] == "Przed akcją gry"
    assert result["sections"][1]["text"] == "Już jako więzień zebrał wokół siebie ludzi."
    
    # Check categories
    assert "Magnaci" in result["categories"]
    assert "Postacie z Gothic" in result["categories"]
    
    # Check languages
    assert result["languages"]["en"] == "Gomez"
    assert result["languages"]["ru"] == "Гомез"

def test_parse_wikitext_empty_sections():
    wikitext = """{{Postać
 |Imię = Bezimienny
}}
Wstęp.

== ==
== Pusta ==

== Z tekstem ==
Jakiś tekst.
"""
    result = parse_wikitext_to_dict("Bezi", wikitext)
    assert len(result["sections"]) == 2
    assert result["sections"][0]["title"] == "Wstęp"
    assert result["sections"][1]["title"] == "Z tekstem"
    assert result["sections"][1]["text"] == "Jakiś tekst."

def test_parse_wikitext_no_tags_no_lead():
    wikitext = """{{Przedmiot
 |Nazwa = Jabłko
}}
== Zastosowanie ==
Zjedzenie daje HP.
"""
    result = parse_wikitext_to_dict("Jabłko", wikitext)
    assert result["meta_templates"] == []
    assert result["type"] == "Przedmiot"
    assert len(result["sections"]) == 1
    assert result["sections"][0]["title"] == "Zastosowanie"

def test_clean_value_templates():
    assert clean_value("{{Wartość|ruda|55}}") == "55 ruda"
    assert clean_value("{{Wartość|złoto|6}}") == "6 złoto"
    assert clean_value("{{Cena|złoto|250}}") == "250 złoto"
    assert clean_value("{{Wartość|Brak}}") == "Brak"

def test_clean_value_list_with_templates():
    val = "[[Gniew Innosa]]<br>{{Wartość|ruda|10}}, {{Cena|złoto|5}}"
    assert clean_value(val, is_list=True) == ["Gniew Innosa", "10 ruda", "5 złoto"]

def test_parse_wikitext_section_links():
    wikitext = """{{Postać
 |Imię = Test
}}
== [[Zadania]] ==
Zadanie 1.
=== [[Występowanie|Gdzie znaleźć]] ===
W Khorinis.
"""
    result = parse_wikitext_to_dict("Test", wikitext)
    assert len(result["sections"]) == 1
    assert result["sections"][0]["title"] == "Zadania"
    assert result["sections"][0]["text"] == "Zadanie 1."
    assert len(result["sections"][0]["subsections"]) == 1
    assert result["sections"][0]["subsections"][0]["title"] == "Gdzie znaleźć"
    assert result["sections"][0]["subsections"][0]["text"] == "W Khorinis."

def test_parse_wikitext_nested_sections():
    wikitext = """
== Poziom 2 ==
tekst 2
=== Poziom 3 ===
tekst 3
==== Poziom 4 ====
tekst 4
=== Poziom 3 B ===
tekst 3 B
== Inny 2 ==
tekst inny 2
"""
    result = parse_wikitext_to_dict("Nested", wikitext)
    assert len(result["sections"]) == 2
    
    sec1 = result["sections"][0]
    assert sec1["title"] == "Poziom 2"
    assert sec1["text"] == "tekst 2"
    assert len(sec1["subsections"]) == 2
    
    sec1_sub1 = sec1["subsections"][0]
    assert sec1_sub1["title"] == "Poziom 3"
    assert sec1_sub1["text"] == "tekst 3"
    assert len(sec1_sub1["subsections"]) == 1
    
    sec1_sub1_sub1 = sec1_sub1["subsections"][0]
    assert sec1_sub1_sub1["title"] == "Poziom 4"
    assert sec1_sub1_sub1["text"] == "tekst 4"
    
    sec1_sub2 = sec1["subsections"][1]
    assert sec1_sub2["title"] == "Poziom 3 B"
    assert sec1_sub2["text"] == "tekst 3 B"
    
    sec2 = result["sections"][1]
    assert sec2["title"] == "Inny 2"
    assert sec2["text"] == "tekst inny 2"
    assert len(sec2["subsections"]) == 0

def test_parse_wikitext_prune_empty_sections():
    wikitext = """
== Pusta ==
=== Pusta 3 ===
==== Pusta 4 ====
== Z tekstem ==
=== Z tekstem 3 ===
Tekst
"""
    result = parse_wikitext_to_dict("Empty", wikitext)
    # The first top-level section ("Pusta") and its subsections have NO TEXT AT ALL.
    # So they should be pruned completely.
    # The second top-level section has a subsection with text, so it's kept.
    assert len(result["sections"]) == 1
    assert result["sections"][0]["title"] == "Z tekstem"
    assert result["sections"][0]["text"] == ""
    assert len(result["sections"][0]["subsections"]) == 1
    assert result["sections"][0]["subsections"][0]["title"] == "Z tekstem 3"
    assert result["sections"][0]["subsections"][0]["text"] == "Tekst"


def test_parse_wikitext_multiple_infoboxes():
    wikitext = """{{Broń
 |Nazwa = Maczuga
 |Obrażenia = 23
}}
{{Broń
 |Nazwa = Inna Maczuga
 |Obrażenia = 10
}}
Opis maczugi.
"""
    result = parse_wikitext_to_dict("Maczuga", wikitext)
    assert result["type"] == "Broń"
    assert result["infobox"]["nazwa"] == "Maczuga"
    assert result["infobox"]["obrażenia"] == "23"
    assert len(result["sections"]) == 1
    assert result["sections"][0]["text"] == "Opis maczugi."

def test_parse_wikitext_references():
    wikitext = """{{Przedmiot
 |Nazwa = Artefakt
}}
To jest potężny artefakt<ref name="a">Według Xardasa.</ref>.
Niektórzy w to wątpią<ref name="a"/>.
Koniec tekstu<ref>Wzmianka w grze</ref>.
"""
    result = parse_wikitext_to_dict("Artefakt", wikitext)
    assert result["sections"][0]["text"] == "To jest potężny artefakt (Według Xardasa.).\nNiektórzy w to wątpią.\nKoniec tekstu (Wzmianka w grze)."

def test_parse_wikitext_categories_and_languages():
    wikitext = """{{Przedmiot
 |Nazwa = Magiczny miecz
}}
Opis miecza.

[[Kategoria:Broń jednoręczna z Gothic]]
[[Kategoria:Artefakty]]
[[en:Magic sword]]
[[ru:Магический меч]]
[[de:Magisches Schwert]]
"""
    result = parse_wikitext_to_dict("Miecz", wikitext)
    assert result["categories"] == ["Broń jednoręczna z Gothic", "Artefakty"]
    assert result["languages"]["en"] == "Magic sword"
    assert result["languages"]["ru"] == "Магический меч"
    assert result["languages"]["de"] == "Magisches Schwert"
    assert "Kategoria" not in result["sections"][0]["text"]
    assert "Magic sword" not in result["sections"][0]["text"]

def test_parse_wikitext_table_with_headers():
    wikitext = """{{Przedmiot
 |Nazwa = Tabela z nagłówkami
}}
Wstęp.
<table class="wikitable">
<tr>
<th>Broń</th>
<th>Obrażenia</th>
</tr>
<tr>
<td>Miecz</td>
<td>40</td>
</tr>
<tr>
<td>Topór</td>
<td>50</td>
</tr>
</table>
"""
    result = parse_wikitext_to_dict("Tabela 1", wikitext)
    text = result["sections"][0]["text"]
    assert "| Broń | Obrażenia |" in text
    assert "| --- | --- |" in text
    assert "| Miecz | 40 |" in text
    assert "| Topór | 50 |" in text

def test_parse_wikitext_table_without_headers():
    wikitext = """{{Przedmiot
 |Nazwa = Tabela bez nagłówków
}}
Wstęp.
<table>
<tr>
<td>Miecz</td>
<td>40</td>
</tr>
<tr>
<td>Topór</td>
<td>50</td>
</tr>
</table>
"""
    result = parse_wikitext_to_dict("Tabela 2", wikitext)
    text = result["sections"][0]["text"]
    assert "| Miecz | 40 |" in text
    assert "| --- | --- |" in text
    assert "| Topór | 50 |" in text
    assert "| Broń | Obrażenia |" not in text

def test_parse_wikitext_inline_images_removed():
    wikitext = """{{Przedmiot
 |Nazwa = Artefakt
}}
To jest opis przedmiotu.
[[Plik:test.png|310px|center|Wnętrze chaty]]
To jest drugie zdanie.
"""
    result = parse_wikitext_to_dict("Artefakt", wikitext)
    text = result["sections"][0]["text"]
    assert "Wnętrze chaty" not in text
    assert "310px" not in text
    assert text == "To jest opis przedmiotu.\n\nTo jest drugie zdanie."

def test_parse_wikitext_table_image_header_removed():
    wikitext = """{{Przedmiot
 |Nazwa = Artefakt
}}
<table class="wikitable">
<tr>
<th>Obraz</th>
<th>Broń</th>
<th>Obrażenia</th>
</tr>
<tr>
<td>[[Plik:miecz.png]]</td>
<td>Miecz</td>
<td>40</td>
</tr>
</table>
"""
    result = parse_wikitext_to_dict("Artefakt", wikitext)
    text = result["sections"][0]["text"]
    assert "| Broń | Obrażenia |" in text
    assert "| --- | --- |" in text
    assert "| Miecz | 40 |" in text
    assert "Obraz" not in text
    assert "miecz" not in text

def test_parse_wikitext_table_empty_column_removed():
    wikitext = """{{Przedmiot
 |Nazwa = Artefakt
}}
<table>
<tr>
<td>[[Plik:miecz.png]]</td>
<td>Miecz</td>
<td>40</td>
</tr>
<tr>
<td>[[Plik:topor.png]]</td>
<td>Topór</td>
<td>50</td>
</tr>
</table>
"""
    result = parse_wikitext_to_dict("Artefakt", wikitext)
    text = result["sections"][0]["text"]
    assert "| Miecz | 40 |" in text
    assert "| --- | --- |" in text
    assert "| Topór | 50 |" in text
    assert "miecz" not in text

def test_parse_wikitext_infobox_image_keys_ignored():
    wikitext = """{{Przedmiot
 |Nazwa = Artefakt
 |Obraz = artefakt.png
 |Podpis obrazu = To jest artefakt
 |Grafika = inna.jpg
 |Cena = 100
}}
"""
    result = parse_wikitext_to_dict("Artefakt", wikitext)
    assert result["infobox"].get("nazwa") == "Artefakt"
    assert result["infobox"].get("cena") == "100"
    assert result["infobox"].get("obraz") == "artefakt.png"
    assert result["infobox"].get("grafika") == "inna.jpg"
    assert "podpis obrazu" not in result["infobox"]
