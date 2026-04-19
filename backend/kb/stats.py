from kb.repository import AbstractKBRepository, KBStats


def calculate_stats(repo: AbstractKBRepository) -> KBStats:
    return repo.get_stats()
