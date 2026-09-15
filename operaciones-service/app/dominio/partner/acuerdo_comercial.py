from dataclasses import dataclass
from decimal import Decimal

from app.dominio.errores import (
    AcuerdoInvalidoError,
    CondicionNoPactadaError,
    DatosDePartnerInvalidosError,
    TopeFueraDelAcuerdoError,
)
from app.seedwork.dominio import ValueObject

from .condicion_comercial import CondicionComercial
from .condiciones_aplicables import CondicionesAplicables
from .enums import TipoCondicion


@dataclass(frozen=True)
class AcuerdoComercial(ValueObject):
    """Condiciones pactadas con un partner durante su onboarding o renegociación.

    Aquí viven las reglas comerciales de cada partner: topes por plan o por orden, SLA por
    nivel de prioridad y red de proveedores homologados. Los adaptadores de integración solo
    traducen formatos; qué tope o qué SLA aplica a una solicitud lo decide este objeto.
    """

    condiciones: tuple[CondicionComercial, ...]
    red_de_proveedores: frozenset[str] | None = None

    def __post_init__(self) -> None:
        condiciones = tuple(self.condiciones)
        vistas: set[tuple[TipoCondicion, str]] = set()
        for condicion in condiciones:
            llave = (condicion.tipo, condicion.clave)
            if llave in vistas:
                raise AcuerdoInvalidoError(
                    f"Condición repetida en el acuerdo: {condicion.tipo.value} {condicion.clave}"
                )
            vistas.add(llave)
        if not any(condicion.tipo is TipoCondicion.SLA for condicion in condiciones):
            raise AcuerdoInvalidoError("El acuerdo debe pactar al menos un SLA")
        if self.red_de_proveedores is not None:
            red = frozenset(
                proveedor.strip()
                for proveedor in self.red_de_proveedores
                if proveedor and proveedor.strip()
            )
            if not red:
                raise AcuerdoInvalidoError("La red de proveedores del acuerdo no puede estar vacía")
            object.__setattr__(self, "red_de_proveedores", red)
        object.__setattr__(self, "condiciones", condiciones)

    def resolver(
        self,
        clave_sla: str,
        clave_tope: str | None = None,
        tope_solicitado: Decimal | None = None,
    ) -> CondicionesAplicables:
        """Convierte los niveles que menciona una solicitud en condiciones concretas.

        - El SLA sale de la condición pactada para `clave_sla`.
        - El tope sale de la condición pactada para `clave_tope`. Si el partner además
          autoriza un tope en la propia solicitud, se usa ese, siempre que no supere lo
          pactado.
        """

        sla = self._condicion(TipoCondicion.SLA, clave_sla)
        if tope_solicitado is not None and tope_solicitado <= 0:
            raise DatosDePartnerInvalidosError("El tope autorizado en la solicitud debe ser positivo")

        monto_maximo = tope_solicitado
        if clave_tope is not None:
            pactado = self._condicion(TipoCondicion.TOPE, clave_tope)
            if tope_solicitado is not None and tope_solicitado > pactado.valor:
                raise TopeFueraDelAcuerdoError(
                    f"El tope autorizado ({tope_solicitado}) supera el pactado para "
                    f"{pactado.clave} ({pactado.valor})"
                )
            monto_maximo = tope_solicitado if tope_solicitado is not None else pactado.valor

        return CondicionesAplicables(
            monto_maximo=monto_maximo,
            proveedores_permitidos=self.red_de_proveedores,
            sla_horas=int(sla.valor),
        )

    def _condicion(self, tipo: TipoCondicion, clave: str | None) -> CondicionComercial:
        normalizada = (clave or "").strip().upper()
        for condicion in self.condiciones:
            if condicion.tipo is tipo and condicion.clave == normalizada:
                return condicion
        descripcion = "un tope" if tipo is TipoCondicion.TOPE else "un SLA"
        raise CondicionNoPactadaError(f"El acuerdo no pacta {descripcion} para '{normalizada}'")
