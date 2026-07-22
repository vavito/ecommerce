from app.shared.slug import slugify


def test_slugify_normalizes_accents_spaces_and_symbols() -> None:
    assert slugify("  Cafeteira Elétrica & Compacta  ") == (
        "cafeteira-eletrica-compacta"
    )
