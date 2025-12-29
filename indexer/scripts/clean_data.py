"""
Nettoyage des donnees aberrantes dans la base.

Script de maintenance pour:
- Nettoyer les prix aberrants (numeros de telephone parses comme prix)
- Dedupliquer lieu_ref (variantes de casse)
- Identifier les artistes suspects (erreurs de parsing)
- Ajouter la colonne nom_normalise a lieu_ref
"""

import sqlite3
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'


def clean_prix_aberrants(conn: sqlite3.Connection) -> int:
    """
    Nettoie les prix aberrants (> 200 EUR).

    Causes identifiees:
    - Numeros de telephone parses comme prix (ex: 243977494)
    - "3000 e" mal interprete
    - Erreurs de parsing diverses

    Returns:
        Nombre d'evenements nettoyes
    """
    cur = conn.cursor()

    # Identifier les prix aberrants
    cur.execute("""
        SELECT id, bidul_numero, prix_min, prix_max, tarif_raw
        FROM evenement
        WHERE prix_min > 200 OR prix_max > 500
    """)
    aberrants = cur.fetchall()
    logger.info(f"Trouve {len(aberrants)} evenements avec prix aberrants")

    if not aberrants:
        return 0

    # Nettoyer
    cur.execute("""
        UPDATE evenement
        SET prix_min = NULL,
            prix_max = NULL,
            review_notes = COALESCE(review_notes || ' | ', '') ||
                           'Prix aberrant nettoye: ' || COALESCE(tarif_raw, 'N/A'),
            needs_review = TRUE
        WHERE prix_min > 200 OR prix_max > 500
    """)

    count = cur.rowcount
    conn.commit()
    logger.info(f"Nettoye {count} prix aberrants")

    return count


def deduplicate_lieu_ref(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """
    Fusionne les doublons dans lieu_ref (variantes de casse).
    Garde l'entree la plus utilisee, cree des aliases pour les autres.

    Returns:
        Liste de tuples (variante, canonique) pour les aliases a creer
    """
    cur = conn.cursor()

    # Trouver les groupes de doublons (meme nom, casse differente)
    cur.execute("""
        SELECT LOWER(nom) as nom_lower, GROUP_CONCAT(id) as ids
        FROM lieu_ref
        GROUP BY LOWER(nom)
        HAVING COUNT(*) > 1
    """)

    duplicates = cur.fetchall()
    logger.info(f"Trouve {len(duplicates)} groupes de doublons dans lieu_ref")

    if not duplicates:
        return []

    aliases_to_create = []

    for nom_lower, ids_str in duplicates:
        ids = [int(x) for x in ids_str.split(',')]

        # Compter l'utilisation de chaque id
        usage = {}
        noms = {}
        for id_ in ids:
            cur.execute("SELECT COUNT(*) FROM evenement WHERE lieu_ref_id = ?", (id_,))
            usage[id_] = cur.fetchone()[0]
            cur.execute("SELECT nom FROM lieu_ref WHERE id = ?", (id_,))
            result = cur.fetchone()
            noms[id_] = result[0] if result else None

        # Garder le plus utilise
        keep_id = max(ids, key=lambda x: usage[x])
        merge_ids = [x for x in ids if x != keep_id]
        keep_nom = noms[keep_id]

        logger.info(f"  Fusion '{nom_lower}': garder [{keep_id}] '{keep_nom}' ({usage[keep_id]}x)")

        for merge_id in merge_ids:
            merge_nom = noms[merge_id]
            if merge_nom is None:
                continue
            logger.info(f"    - Fusionner [{merge_id}] '{merge_nom}' ({usage[merge_id]}x)")

            # Migrer les FK
            cur.execute("""
                UPDATE evenement SET lieu_ref_id = ? WHERE lieu_ref_id = ?
            """, (keep_id, merge_id))

            # Stocker l'alias a creer (sera ecrit dans le CSV)
            if merge_nom != keep_nom:
                aliases_to_create.append((merge_nom, keep_nom))

            # Supprimer l'entree fusionnee
            cur.execute("DELETE FROM lieu_ref WHERE id = ?", (merge_id,))

    conn.commit()
    logger.info(f"Fusionne {len(duplicates)} groupes de doublons")

    return aliases_to_create


def clean_artistes_suspects(conn: sqlite3.Connection) -> int:
    """
    Identifie et marque les artistes suspects (erreurs de parsing).
    Ne supprime pas, marque pour review.

    Returns:
        Nombre d'evenements marques
    """
    cur = conn.cursor()

    # Patterns suspects
    patterns = [
        ('%Le Mans%', 'Contient "Le Mans"'),
        ('%20h%', 'Contient heure'),
        ('%21h%', 'Contient heure'),
        ('%22h%', 'Contient heure'),
        ('%EUR%', 'Contient prix'),
        ('%gratuit%', 'Contient "gratuit"'),
        ('%resa%', 'Contient "resa"'),
    ]

    total_suspects = 0
    for pattern, reason in patterns:
        cur.execute("""
            SELECT COUNT(*) FROM contenu_evenement
            WHERE artiste LIKE ? AND artiste NOT LIKE 'LA %' AND artiste NOT LIKE 'Le %'
        """, (pattern,))
        count = cur.fetchone()[0]
        if count > 0:
            logger.info(f"  {count} artistes suspects: {reason}")
            total_suspects += count

    # Marquer les evenements concernes pour review
    cur.execute("""
        UPDATE evenement
        SET needs_review = TRUE,
            review_notes = COALESCE(review_notes || ' | ', '') || 'Artiste suspect'
        WHERE id IN (
            SELECT DISTINCT evenement_id FROM contenu_evenement
            WHERE artiste LIKE '%Le Mans%'
               OR artiste LIKE '%20h%'
               OR artiste LIKE '%21h%'
               OR artiste LIKE '%EUR%'
        )
    """)

    count = cur.rowcount
    conn.commit()
    logger.info(f"Marque {count} evenements avec artistes suspects")

    return count


def add_nom_normalise_column(conn: sqlite3.Connection) -> bool:
    """
    Ajoute la colonne nom_normalise a lieu_ref si elle n'existe pas.

    Returns:
        True si la colonne a ete ajoutee, False si elle existait deja
    """
    cur = conn.cursor()

    # Verifier si la colonne existe
    cur.execute("PRAGMA table_info(lieu_ref)")
    columns = [col[1] for col in cur.fetchall()]

    if 'nom_normalise' not in columns:
        cur.execute("ALTER TABLE lieu_ref ADD COLUMN nom_normalise TEXT")
        conn.commit()
        logger.info("Colonne nom_normalise ajoutee a lieu_ref")
        return True
    else:
        logger.info("Colonne nom_normalise existe deja")
        return False


def add_needs_review_column(conn: sqlite3.Connection) -> bool:
    """
    Ajoute la colonne needs_review a evenement si elle n'existe pas.

    Returns:
        True si la colonne a ete ajoutee, False si elle existait deja
    """
    cur = conn.cursor()

    # Verifier si la colonne existe
    cur.execute("PRAGMA table_info(evenement)")
    columns = [col[1] for col in cur.fetchall()]

    if 'needs_review' not in columns:
        cur.execute("ALTER TABLE evenement ADD COLUMN needs_review BOOLEAN DEFAULT FALSE")
        conn.commit()
        logger.info("Colonne needs_review ajoutee a evenement")
        return True
    else:
        logger.info("Colonne needs_review existe deja")
        return False


def show_stats(conn: sqlite3.Connection):
    """Affiche les statistiques apres nettoyage."""
    cur = conn.cursor()

    print("\n" + "=" * 50)
    print("STATISTIQUES APRES NETTOYAGE")
    print("=" * 50)

    cur.execute("SELECT COUNT(*) FROM evenement")
    total = cur.fetchone()[0]
    print(f"Evenements total: {total:,}")

    cur.execute("SELECT COUNT(*) FROM evenement WHERE needs_review = TRUE OR needs_review = 1")
    needs_review = cur.fetchone()[0]
    print(f"A reviewer: {needs_review:,}")

    cur.execute("SELECT COUNT(*) FROM evenement WHERE lieu_ref_id IS NOT NULL")
    n_lieu = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM evenement WHERE lieu_raw IS NOT NULL")
    n_lieu_raw = cur.fetchone()[0]
    if n_lieu_raw > 0:
        print(f"Lieux normalises: {n_lieu:,}/{n_lieu_raw:,} ({n_lieu/n_lieu_raw*100:.1f}%)")
    else:
        print(f"Lieux normalises: {n_lieu:,}")

    cur.execute("SELECT COUNT(*) FROM lieu_ref")
    print(f"Lieux dans referentiel: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(DISTINCT artiste) FROM contenu_evenement WHERE artiste IS NOT NULL")
    print(f"Artistes distincts: {cur.fetchone()[0]:,}")


def main():
    """Point d'entree principal."""
    logger.info("=" * 50)
    logger.info("NETTOYAGE DE LA BASE DE DONNEES")
    logger.info("=" * 50)

    if not DB_PATH.exists():
        logger.error(f"Base non trouvee: {DB_PATH}")
        return 1

    conn = sqlite3.connect(str(DB_PATH))

    try:
        logger.info("\n1. Ajout colonnes manquantes...")
        add_nom_normalise_column(conn)
        add_needs_review_column(conn)

        logger.info("\n2. Nettoyage des prix aberrants...")
        clean_prix_aberrants(conn)

        logger.info("\n3. Deduplication de lieu_ref...")
        aliases = deduplicate_lieu_ref(conn)
        if aliases:
            logger.info(f"   Aliases a ajouter dans lieu_alias.csv:")
            for variante, canonique in aliases[:10]:
                logger.info(f"     '{variante}' -> '{canonique}'")
            if len(aliases) > 10:
                logger.info(f"     ... et {len(aliases)-10} autres")

        logger.info("\n4. Identification des artistes suspects...")
        clean_artistes_suspects(conn)

        show_stats(conn)

    finally:
        conn.close()

    logger.info("\nNettoyage termine")
    return 0


if __name__ == '__main__':
    exit(main())
