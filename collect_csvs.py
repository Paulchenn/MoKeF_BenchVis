import shutil
from pathlib import Path

def collect_csvs(source_folder: Path, destination_folder: Path):
    """
    Sucht rekursiv nach CSV-Dateien und kopiert sie in einen Sammelordner.
    """
    # Erstelle den Sammelordner, falls er noch nicht existiert
    destination_folder.mkdir(parents=True, exist_ok=True)

    if not source_folder.exists() or not source_folder.is_dir():
        print(f"Fehler: Der Quellordner '{source_folder}' existiert nicht.")
        return

    # Suche rekursiv nach allen .csv Dateien (.rglob macht genau das)
    csv_files = list(source_folder.rglob("*.csv"))
    
    if not csv_files:
        print(f"Keine CSV-Dateien im Ordner '{source_folder}' gefunden.")
        return

    print(f"{len(csv_files)} CSV-Dateien gefunden. Starte Kopiervorgang...")

    for csv_file in csv_files:
        # Ermittle den relativen Pfad, um Namenskonflikte zu vermeiden
        rel_path = csv_file.relative_to(source_folder)
        
        # Baue einen neuen Dateinamen zusammen: "unterordner1_unterordner2_dateiname.csv"
        if len(rel_path.parts) > 1:
            prefix = "_".join(rel_path.parts[:-1])
            new_filename = f"{prefix}_{csv_file.name}"
        else:
            new_filename = csv_file.name
            
        dest_file = destination_folder / new_filename
        
        # Kopiere die Datei inklusive Metadaten (shutil.copy2 behält Zeitstempel bei)
        shutil.copy2(csv_file, dest_file)
        print(f"Kopiert: {csv_file.name} -> {new_filename}")

    print(f"\nFertig! Alle Dateien wurden erfolgreich nach '{destination_folder.name}' kopiert.")

if __name__ == "__main__":
    # Definiere die Pfade relativ zu diesem Skript
    base_directory = Path(__file__).parent
    source_directory = base_directory / "2plot"
    destination_directory = base_directory / "collected_csvs"
    
    collect_csvs(source_directory, destination_directory)