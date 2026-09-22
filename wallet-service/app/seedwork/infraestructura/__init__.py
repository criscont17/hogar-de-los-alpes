"""Bloques genéricos de la capa de infraestructura.

Abstracciones transversales que no pertenecen al negocio de las billeteras y que
cualquier adaptador puede reutilizar.
"""

from .reintentos import PoliticaDeReintentos

__all__ = ["PoliticaDeReintentos"]
