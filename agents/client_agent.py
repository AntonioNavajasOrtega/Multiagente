"""
agents/client_agent.py

Agente Cliente (Actor Model — AutoGen v0.4).
Anuncia demanda y confirma recepciones asíncronas.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from autogen_core import RoutedAgent, message_handler, MessageContext
from .messages import DeliveryMessage, DeliveryAck, DemandAnnouncement

if TYPE_CHECKING:
    from core.entities import Client


class ClientAgent(RoutedAgent):
    """
    Agente que representa un punto de demanda (cliente).
    Reactivo: confirma entregas.
    Proactivo: al inicio anuncia su demanda.
    """

    def __init__(self, client: Client) -> None:
        super().__init__("ClientAgent")
        self._cli = client
        self.client_id = client.id

    @message_handler
    async def handle_delivery(
        self, 
        message: DeliveryMessage, 
        ctx: MessageContext
    ) -> None:
        """
        Manejador de recepción de mercancía.
        Actualiza el estado de demanda del cliente y responde confirmación.
        """
        actual_received = self._cli.receive(message.depot_id, message.amount)
        success = actual_received > 0
        if success:
            print(f"  [MSG] {self.client_id} <- {message.vehicle_id}: Entrega recibida (+{actual_received})")
        
        response = DeliveryAck(
            success=success,
            delivered=actual_received,
            demand_left=self._cli.pending_demand()
        )
        
        if ctx.sender is not None:
            await self.send_message(response, recipient=ctx.sender)

    def demand_announcement(self) -> DemandAnnouncement:
        """Helper para que el motor inicialice la demanda."""
        return DemandAnnouncement(
            client_id=self.client_id,
            demand=self._cli.demand
        )

    def is_satisfied(self) -> bool:
        return self._cli.is_satisfied()

    def has_demand_from(self, depot_id: str) -> bool:
        return self._cli.demand.get(depot_id, 0) > 0

    def demand_message(self) -> str:
        items = [f"{d}: {v}" for d, v in self._cli.demand.items() if v > 0]
        return ", ".join(items) if items else "satisfecha"

    @property
    def pos(self):
        return self._cli.pos

    def to_dict(self) -> dict:
        return self._cli.to_dict()
