"""
agents/depot_agent.py

Agente de Depósito (Actor Model — AutoGen v0.4).
Gestiona inventario y autoriza cargas mediante paso de mensajes asíncronos.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from autogen_core import RoutedAgent, message_handler, MessageContext
from .messages import PickupRequest, PickupResponse

if TYPE_CHECKING:
    from core.entities import Depot


class DepotAgent(RoutedAgent):
    """
    Agente que representa un depósito logístico.
    Reactivo: responde a solicitudes de carga de los vehículos.
    """

    def __init__(self, depot: Depot) -> None:
        super().__init__("DepotAgent")
        self._depot = depot
        self.depot_id = depot.id

    @message_handler
    async def handle_pickup_request(
        self, 
        message: PickupRequest, 
        ctx: MessageContext
    ) -> None:
        """
        Manejador de solicitudes de carga.
        Descuenta el inventario y responde con los detalles de la carga autorizada.
        """
        # Lógica de dominio: retirar stock
        actual_withdrawn = self._depot.withdraw(message.amount)
        success = actual_withdrawn > 0
        
        # Enviar respuesta al vehículo emisor
        response = PickupResponse(
            success=success,
            amount=actual_withdrawn,
            stock_left=self._depot.inventory
        )
        
        if ctx.sender is not None:
            await self.send_message(response, recipient=ctx.sender)

    def is_empty(self) -> bool:
        return self._depot.inventory <= 0

    @property
    def pos(self):
        return self._depot.pos

    def to_dict(self) -> dict:
        return self._depot.to_dict()
