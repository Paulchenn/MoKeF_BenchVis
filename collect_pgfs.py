import shutil
from pathlib import Path

def collect_pgfs(source_folder: Path, destination_folder: Path):
    """
    Sucht rekursiv nach PGF-Dateien und kopiert sie in einen Sammelordner.
    """
    # Erstelle den Sammelordner, falls er noch nicht existiert
    destination_folder.mkdir(parents=True, exist_ok=True)

    if not source_folder.exists() or not source_folder.is_dir():
        print(f"Fehler: Der Quellordner '{source_folder}' existiert nicht.")
        return

    # Suche rekursiv nach allen .pgf Dateien
    pgf_files = list(source_folder.rglob("*.pgf"))
    
    if not pgf_files:
        print(f"Keine PGF-Dateien im Ordner '{source_folder}' gefunden.")
        return

    print(f"{len(pgf_files)} PGF-Dateien gefunden. Starte Kopiervorgang...")

    for pgf_file in pgf_files:
        # Ermittle den relativen Pfad, um Namenskonflikte zu vermeiden
        rel_path = pgf_file.relative_to(source_folder)
        
        # Baue einen neuen Dateinamen zusammen: "unterordner1_unterordner2_dateiname.pgf"
        if len(rel_path.parts) > 1:
            prefix = "_".join(rel_path.parts[:-1])
            new_filename = pgf_file.name # f"{prefix}_{pgf_file.name}"
        else:
            new_filename = pgf_file.name
            
        dest_file = destination_folder / new_filename
        
        # Kopiere die Datei inklusive Metadaten
        shutil.copy2(pgf_file, dest_file)
        print(f"Kopiert: {pgf_file.name} -> {new_filename}")

    print(f"\nFertig! Alle Dateien wurden erfolgreich nach '{destination_folder.name}' kopiert.")

if __name__ == "__main__":
    # Definiere die Pfade relativ zu diesem Skript
    base_directory = Path(__file__).parent
    source_directory = base_directory / "z_2use"
    destination_directory = base_directory / "pgf"
    
    collect_pgfs(source_directory, destination_directory)