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
    assert len(result["sections"]) == 2
    assert result["sections"][0]["title"] == "Zadania"
    assert result["sections"][0]["text"] == "Zadanie 1."
    assert result["sections"][1]["title"] == "Gdzie znaleźć"
    assert result["sections"][1]["text"] == "W Khorinis."

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
    assert "TABLE" in text
    assert "END_TABLE" in text
    assert "Broń, Obrażenia" in text
    assert "Miecz, 40" in text
    assert "Topór, 50" in text

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
    assert "TABLE" in text
    assert "END_TABLE" in text
    assert "Miecz, 40" in text
    assert "Topór, 50" in text
    assert "Broń, Obrażenia" not in text
