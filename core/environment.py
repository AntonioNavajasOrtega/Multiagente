"""
core/environment.py
Representa el grid NxM con tipos de celda, costes de movimiento
y serialización/deserialización JSON.
"""
from __future__ import annotations
from typing import List, Tuple, Optional
import json

CELL_FREE = "."
CELL_OBSTACLE = "#"
CELL_DEPOT = "D"
CELL_CLIENT = "C"
CELL_TRAFFIC = "T"

PASSABLE = {CELL_FREE, CELL_DEPOT, CELL_CLIENT, CELL_TRAFFIC}

# 8 direcciones: (drow, dcol)
DIRECTIONS = [
    (-1,  0),  # N
    ( 1,  0),  # S
    ( 0,  1),  # E
    ( 0, -1),  # O
    (-1,  1),  # NE
    (-1, -1),  # NO
    ( 1,  1),  # SE
    ( 1, -1),  # SO
]


class Grid:
    """
    Grid bidimensional NxM.
    cells[row][col] es el tipo de celda (str).
    traffic_penalty: multiplicador de coste para celdas T.
    """

    def __init__(self, rows: int, cols: int, traffic_penalty: float = 2.0):
        self.rows = rows
        self.cols = cols
        self.traffic_penalty = traffic_penalty
        self.cells: List[List[str]] = [
            [CELL_FREE for _ in range(cols)] for _ in range(rows)
        ]

    # ------------------------------------------------------------------
    # Consulta del grid
    # ------------------------------------------------------------------

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols

    def cell_type(self, pos: Tuple[int, int]) -> str:
        return self.cells[pos[0]][pos[1]]

    def is_passable(self, pos: Tuple[int, int]) -> bool:
        r, c = pos
        return self.in_bounds(r, c) and self.cells[r][c] in PASSABLE

    def move_cost(self, pos: Tuple[int, int], vehicle_cost: float) -> float:
        """Coste de moverse A la celda `pos` con un vehículo de coste base dado."""
        ct = self.cell_type(pos)
        if ct == CELL_TRAFFIC:
            return vehicle_cost * self.traffic_penalty
        return vehicle_cost

    def set_cell(self, row: int, col: int, cell_type: str) -> None:
        self.cells[row][col] = cell_type

    def neighbors(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Vecinos transitables en las 8 direcciones."""
        r, c = pos
        result = []
        for dr, dc in DIRECTIONS:
            nb = (r + dr, c + dc)
            if self.is_passable(nb):
                result.append(nb)
        return result

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "rows": self.rows,
            "cols": self.cols,
            "traffic_penalty": self.traffic_penalty,
            "cells": self.cells,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Grid":
        g = cls(
            rows=d["rows"],
            cols=d["cols"],
            traffic_penalty=d.get("traffic_penalty", 2.0),
        )
        g.cells = [list(row) for row in d["cells"]]
        return g

    # ------------------------------------------------------------------
    # Representación ASCII para debug
    # ------------------------------------------------------------------

    def to_ascii(self, vehicle_positions: Optional[dict] = None) -> str:
        """Genera representación ASCII. vehicle_positions = {(r,c): vehicle_id}"""
        vp = vehicle_positions or {}
        lines = []
        header = "    " + " ".join(f"{c:2}" for c in range(self.cols))
        lines.append(header)
        lines.append("   +" + "---" * self.cols + "+")
        for r in range(self.rows):
            row_chars = []
            for c in range(self.cols):
                pos = (r, c)
                if pos in vp:
                    row_chars.append("V ")
                else:
                    row_chars.append(self.cells[r][c] + " ")
            lines.append(f"{r:2} | {''.join(row_chars)}|")
        lines.append("   +" + "---" * self.cols + "+")
        return "\n".join(lines)
