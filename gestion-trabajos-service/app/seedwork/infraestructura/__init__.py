"""Bloques genéricos de infraestructura."""

from .circuit_breaker import CircuitBreaker, CircuitoAbiertoError, EstadoCircuito

__all__ = ["CircuitBreaker", "CircuitoAbiertoError", "EstadoCircuito"]
