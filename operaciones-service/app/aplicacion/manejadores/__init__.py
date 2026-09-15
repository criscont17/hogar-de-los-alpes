"""Handlers suscritos al bus de eventos de dominio."""

from .auditar_evento_de_dominio import AuditarEventoDeDominioHandler

__all__ = ["AuditarEventoDeDominioHandler"]
