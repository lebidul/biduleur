import os
import pickle
import shutil

def upload_file_to_local(file_path, local_target_directory, file_name=None):
    """
    « Upload » local : copie le fichier vers un dossier local.
    
    :param file_path: Chemin du fichier source
    :param local_target_directory: Dossier cible où le copier
    :param file_name: Nom final du fichier (par défaut, conserve le nom source)
    :return: Chemin absolu du fichier copié
    """
    # Si aucun nom n’est fourni, garder le nom original
    if not file_name:
        file_name = os.path.basename(file_path)
    
    # Créer le dossier cible s’il n’existe pas
    os.makedirs(local_target_directory, exist_ok=True)
    
    # Chemin final
    target_path = os.path.join(local_target_directory, file_name)
    
    # Copier le fichier
    shutil.copy2(file_path, target_path)
    
    print(f"✅ Fichier « {file_name} » copié dans « {local_target_directory} »")
    return os.path.abspath(target_path)
