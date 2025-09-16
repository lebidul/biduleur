PT_PER_INCH = 72.0
MM_PER_INCH = 25.4

def mm_to_pt(mm: float) -> float:
    """Convertit les millimètres en points typographiques."""
    return mm * PT_PER_INCH / MM_PER_INCH