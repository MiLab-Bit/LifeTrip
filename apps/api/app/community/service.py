"""Community service — orchestration for route publishing + rating."""
from __future__ import annotations

import uuid
from typing import Any

from app.contracts import CommunityRoute, RouteEnvelope, RouteRating
from app.memory import store


def publish_route(session_id: str, route: RouteEnvelope,
                  tags: list[str], author_label: str = "匿名探索者") -> CommunityRoute:
    """Publish a completed route to the community feed."""
    route_id = str(uuid.uuid4())
    route_json = route.model_dump_json()
    store.publish_community_route(route_id, session_id, route_json, tags, author_label)

    return CommunityRoute(
        id=route_id,
        session_id=session_id,
        route=route,
        tags=tags,
        published_at=store._now(),
        author_label=author_label,
    )


def submit_rating(task_id: str, session_id: str, overall: int,
                  poi_ratings: dict[str, int], comment: str = "",
                  photos: list[str] | None = None) -> RouteRating:
    """Submit a route rating after completing a walk."""
    rating_id = str(uuid.uuid4())
    store.save_rating(
        rating_id, task_id, session_id, overall,
        poi_ratings, comment, photos or [],
    )
    # If this task was from a community route, update aggregate
    return RouteRating(
        task_id=task_id,
        session_id=session_id,
        overall=overall,
        poi_ratings=poi_ratings,
        comment=comment,
        photos=photos or [],
        created_at=store._now(),
    )


def list_routes(limit: int = 20, offset: int = 0) -> list[CommunityRoute]:
    """List community-published routes."""
    rows = store.list_community_routes(limit, offset)
    routes: list[CommunityRoute] = []
    for row in rows:
        try:
            route = RouteEnvelope.model_validate_json(row["route_json"])
            avg = row["rating_sum"] / row["rating_count"] if row["rating_count"] else 0.0
            routes.append(CommunityRoute(
                id=row["id"],
                session_id=row["session_id"],
                route=route,
                rating=round(avg, 1),
                rating_count=row["rating_count"],
                walk_count=row["walk_count"],
                tags=__import__("json").loads(row["tags_json"]),
                published_at=row["published_at"],
                author_label=row["author_label"],
            ))
        except Exception:  # noqa: BLE001
            continue
    return routes


def rate_route(route_id: str, rating: int) -> dict[str, Any] | None:
    """Rate a community route (1-5 stars)."""
    return store.rate_community_route(route_id, rating)
