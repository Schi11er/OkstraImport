"""
OKSTRA XML Analyse-Tool
Analysiert die XML-Datei und erstellt eine Statistik über die enthaltenen UML-Elemente.
"""

import xml.etree.ElementTree as ET
from collections import Counter
import matplotlib.pyplot as plt
from pathlib import Path


def analyze_okstra_xml(xml_file):
    """
    Analysiert die OKSTRA XML-Datei und zählt verschiedene UML-Element-Typen.
    
    Args:
        xml_file: Pfad zur XML-Datei
        
    Returns:
        dict: Dictionary mit den Zählungen für jeden Element-Typ
    """
    # Namespaces definieren
    namespaces = {
        'uml': 'http://schema.omg.org/spec/UML/2.1',
        'xmi': 'http://schema.omg.org/spec/XMI/2.1'
    }
    
    # XML-Datei parsen
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # Zähler initialisieren
    counts = {
        'uml:Package': 0,
        'uml:Class': 0,
        'uml:Property (ohne association)': 0,
        'uml:Property (mit association)': 0,
        'uml:Generalization': 0,
        'uml:Association': 0
    }
    
    # Alternative: Rekursiv durch alle Elemente iterieren
    def count_elements(element):
        # Prüfen auf xmi:type Attribut
        xmi_type = element.get('{http://schema.omg.org/spec/XMI/2.1}type', '')
        
        if xmi_type == 'uml:Package':
            counts['uml:Package'] += 1
        elif xmi_type == 'uml:Class':
            counts['uml:Class'] += 1
        elif xmi_type == 'uml:Property':
            # Prüfen ob association-Attribut vorhanden ist
            if 'association' in element.attrib:
                counts['uml:Property (mit association)'] += 1
            else:
                counts['uml:Property (ohne association)'] += 1
        elif xmi_type == 'uml:Generalization':
            counts['uml:Generalization'] += 1
        elif xmi_type == 'uml:Association':
            counts['uml:Association'] += 1
        
        # Rekursiv durch Kindelemente
        for child in element:
            count_elements(child)
    
    # Rekursive Zählung starten
    count_elements(root)
    
    return counts


def create_pie_chart(counts, output_file='okstra_analysis_pie.png'):
    """
    Erstellt ein Tortendiagramm mit den prozentualen Anteilen.
    
    Args:
        counts: Dictionary mit den Zählungen
        output_file: Dateiname für das PNG
    """
    # Daten vorbereiten - nur Elemente mit Werten > 0
    labels = []
    values = []
    for label, value in counts.items():
        if value > 0:
            labels.append(label)
            values.append(value)
    
    # Prüfen ob überhaupt Daten vorhanden sind
    if not values or sum(values) == 0:
        print("Warnung: Keine Daten zum Erstellen eines Diagramms vorhanden!")
        return
    
    total = sum(values)
    
    # Farben definieren
    colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#ff99cc', '#c2c2f0']
    
    # Diagramm erstellen
    fig, ax = plt.subplots(figsize=(12, 8))
    wedges, texts, autotexts = ax.pie(
        values, 
        labels=labels, 
        autopct='%1.1f%%',
        startangle=90,
        colors=colors[:len(values)],
        textprops={'fontsize': 10}
    )
    
    # Titel hinzufügen
    ax.set_title('OKSTRA XML Elementverteilung', fontsize=16, fontweight='bold', pad=20)
    
    # Legende hinzufügen mit absoluten Zahlen
    legend_labels = [f'{label}: {value:,}' for label, value in zip(labels, values)]
    ax.legend(legend_labels, loc='center left', bbox_to_anchor=(1, 0, 0.5, 1), fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Tortendiagramm wurde erstellt: {output_file}")


def create_markdown_report(counts, image_file='okstra_analysis_pie.png', output_file='okstra_analysis.md'):
    """
    Erstellt einen Markdown-Report mit Tabelle und eingebettetem Diagramm.
    
    Args:
        counts: Dictionary mit den Zählungen
        image_file: Dateiname des Tortendiagramms
        output_file: Dateiname für die Markdown-Datei
    """
    total = sum(counts.values())
    
    markdown_content = f"""# OKSTRA XML Analyse

## Zusammenfassung

Diese Analyse zeigt die Verteilung der UML-Elemente in der Datei `okstra_short.xml`.

**Gesamtanzahl der Elemente:** {total:,}

## Detaillierte Statistik

| Element-Typ | Anzahl | Prozentanteil |
|------------|--------|---------------|
"""
    
    # Tabelle füllen
    for element_type, count in counts.items():
        percentage = (count / total * 100) if total > 0 else 0
        markdown_content += f"| {element_type} | {count:,} | {percentage:.2f}% |\n"
    
    # Diagramm einbetten
    markdown_content += f"""
## Visualisierung

![OKSTRA XML Elementverteilung]({image_file})

---

*Generiert am: {Path(__file__).name} - OKSTRA Analyse-Tool*
"""
    
    # Markdown-Datei schreiben
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    print(f"Markdown-Report wurde erstellt: {output_file}")


def main():
    """Hauptfunktion"""
    # Pfad zur XML-Datei
    xml_file = Path(__file__).parent / 'resources' / 'okstra_short.xml'
    
    print("=" * 60)
    print("OKSTRA XML Analyse")
    print("=" * 60)
    print(f"\nAnalysiere Datei: {xml_file}")
    print("Bitte warten...\n")
    
    # XML analysieren
    counts = analyze_okstra_xml(xml_file)
    
    # Ergebnisse in der Konsole ausgeben
    print("\nErgebnisse:")
    print("-" * 60)
    total = sum(counts.values())
    for element_type, count in counts.items():
        percentage = (count / total * 100) if total > 0 else 0
        print(f"{element_type:40s}: {count:8,} ({percentage:6.2f}%)")
    print("-" * 60)
    print(f"{'Gesamt':40s}: {total:8,} (100.00%)")
    print()
    
    # Tortendiagramm erstellen
    pie_chart_file = Path(__file__).parent / 'okstra_analysis_pie.png'
    create_pie_chart(counts, pie_chart_file)
    
    # Markdown-Report erstellen
    markdown_file = Path(__file__).parent / 'okstra_analysis.md'
    create_markdown_report(counts, pie_chart_file.name, markdown_file)
    
    print("\n" + "=" * 60)
    print("Analyse abgeschlossen!")
    print("=" * 60)


if __name__ == '__main__':
    main()
