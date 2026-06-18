from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter

from apps.api.app.db.connection import get_connection

router = APIRouter(tags=["graph"])


@router.get("/people-graph")
def people_graph() -> dict[str, Any]:
    with get_connection() as conn:
        nodes = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                SELECT
                  id,
                  node_type,
                  entity_id,
                  label,
                  primary_category,
                  centrality,
                  community,
                  x,
                  y,
                  source_refs,
                  confidence_score,
                  payload
                FROM entity_graph_node
                WHERE jsonb_array_length(source_refs) > 0
                ORDER BY node_type ASC, label ASC
                """
            ).fetchall(),
        )
        edges = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                SELECT
                  id,
                  source_node_id,
                  target_node_id,
                  edge_type,
                  weight,
                  source_refs,
                  confidence_score,
                  payload
                FROM entity_graph_edge
                WHERE jsonb_array_length(source_refs) > 0
                ORDER BY edge_type ASC, id ASC
                """
            ).fetchall(),
        )
    return {
        "nodes": [_node_item(row) for row in nodes],
        "edges": [_edge_item(row) for row in edges],
        "meta": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "layout": (
                "DB seed positions plus Sigma.js graphology ForceAtlas2 worker "
                "on the client."
            ),
        },
    }


def _node_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "node_type": row["node_type"],
        "entity_id": row["entity_id"],
        "label": row["label"],
        "primary_category": row["primary_category"],
        "centrality": float(row["centrality"]),
        "community": row["community"],
        "x": float(row["x"]) if row["x"] is not None else None,
        "y": float(row["y"]) if row["y"] is not None else None,
        "source_refs": row["source_refs"],
        "confidence_score": float(row["confidence_score"]),
        "payload": row["payload"],
    }


def _edge_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source": row["source_node_id"],
        "target": row["target_node_id"],
        "edge_type": row["edge_type"],
        "weight": float(row["weight"]),
        "source_refs": row["source_refs"],
        "confidence_score": float(row["confidence_score"]),
        "payload": row["payload"],
    }
