from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.posts.schemas import PostCreate, PostUpdate, PostResponse, PostWithBlocks
from app.database import supabase
from app.dependencies import require_role, assert_project_ownership

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("/{project_id}/admin/all", response_model=list[PostResponse])
def get_all_posts_admin(
    project_id: str,
    user: dict[str, Any] = Depends(require_role("owner", "editor", "viewer")),
) -> list[dict[str, Any]]:
    assert_project_ownership(user, project_id)
    result = (
        supabase.table("posts")
        .select("*")
        .eq("project_id", project_id)
        .order("order")
        .execute()
    )
    return result.data


@router.get("/{project_id}/{slug}", response_model=PostWithBlocks)
def get_post_by_slug(project_id: str, slug: str) -> dict[str, Any]:
    post_result = (
        supabase.table("posts")
        .select("*")
        .eq("project_id", project_id)
        .eq("slug", slug)
        .eq("visible", True)
        .execute()
    )
    if not post_result.data:
        raise HTTPException(status_code=404, detail="Post no encontrado")

    post = post_result.data[0]
    blocks_result = (
        supabase.table("blocks")
        .select("*")
        .eq("post_id", post["id"])
        .eq("visible", True)
        .order("order")
        .execute()
    )
    post["blocks"] = blocks_result.data
    return post


@router.get("/{project_id}", response_model=list[PostResponse])
def get_posts(project_id: str) -> list[dict[str, Any]]:
    result = (
        supabase.table("posts")
        .select("*")
        .eq("project_id", project_id)
        .eq("visible", True)
        .order("order")
        .execute()
    )
    return result.data


@router.post("/{project_id}", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    project_id: str,
    body: PostCreate,
    user: dict[str, Any] = Depends(require_role("owner", "editor")),
) -> dict[str, Any]:
    assert_project_ownership(user, project_id)
    data: dict[str, Any] = {
        "project_id": project_id,
        "slug": body.slug,
        "title": body.title,
        "order": body.order,
        "visible": body.visible,
    }
    result = supabase.table("posts").insert(data).execute()
    return result.data[0]


@router.put("/{project_id}/{post_id}", response_model=PostResponse)
def update_post(
    project_id: str,
    post_id: str,
    body: PostUpdate,
    user: dict[str, Any] = Depends(require_role("owner", "editor")),
) -> dict[str, Any]:
    assert_project_ownership(user, project_id)
    existing = (
        supabase.table("posts")
        .select("id")
        .eq("id", post_id)
        .eq("project_id", project_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Post no encontrado")

    updates = body.model_dump(exclude_none=True)
    result = (
        supabase.table("posts")
        .update(updates)
        .eq("id", post_id)
        .execute()
    )
    return result.data[0]


@router.delete("/{project_id}/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    project_id: str,
    post_id: str,
    user: dict[str, Any] = Depends(require_role("owner")),
) -> None:
    assert_project_ownership(user, project_id)
    existing = (
        supabase.table("posts")
        .select("id")
        .eq("id", post_id)
        .eq("project_id", project_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Post no encontrado")

    supabase.table("posts").delete().eq("id", post_id).execute()
