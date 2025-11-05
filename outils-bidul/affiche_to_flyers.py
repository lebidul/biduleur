from PIL import Image


def affiche_to_flyers(input_path, output_path, dpi=300):
    """
    Transforme une affiche A4 en planche de 4 flyers A6
    """
    # Dimensions en pixels (A4 et A6 à 300 dpi)
    a4_width = int(210 * dpi / 25.4)  # 2480px
    a4_height = int(297 * dpi / 25.4)  # 3508px
    a6_width = int(105 * dpi / 25.4)  # 1240px
    a6_height = int(148.5 * dpi / 25.4)  # 1754px

    # Ouvrir et redimensionner en A6
    img = Image.open(input_path)
    flyer = img.resize((a6_width, a6_height), Image.Resampling.LANCZOS)

    # Créer planche A4
    planche = Image.new('RGB', (a4_width, a4_height), 'white')

    # Placer les 4 flyers
    positions = [
        (0, 0),  # Haut gauche
        (a6_width, 0),  # Haut droit
        (0, a6_height),  # Bas gauche
        (a6_width, a6_height)  # Bas droit
    ]

    for pos in positions:
        planche.paste(flyer, pos)

    # Sauvegarder
    planche.save(output_path, dpi=(dpi, dpi))
    print(f"✓ Planche créée : {output_path}")


# Utilisation
affiche_to_flyers("affiche.v1.1.png", "flyers_a6.png")