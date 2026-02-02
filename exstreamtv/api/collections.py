"""Collections API endpoints - Async version"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..api.schemas import CollectionCreate, CollectionResponse
from ..database import Collection, CollectionItem, MediaItem, Schedule, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["Collections"])


def _extract_olympics_key(name: str | None) -> str | None:
    if not name:
        return None
    import re

    m = re.match(r"^(?:mn\s+)?(\d{4}\s+Winter\s+Olympics)", name, re.IGNORECASE)
    if not m:
        return None
    return " ".join(m.group(1).split()).strip()


def _extract_day_number(name: str | None) -> int:
    if not name:
        return 0
    import re

    m = re.search(r"Day\s*(\d{1,2})", name, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _extract_base_olympics_name(name: str | None) -> str | None:
    """Extract base Olympics name (e.g., '1980 Winter Olympics' from '1980 Winter Olympics - Day 1')"""
    if not name:
        return None
    import re

    # Match patterns like "1980 Winter Olympics - Day 1" or "MN 1980 Winter Olympics - Day 1"
    match = re.match(
        r"^(?:mn\s+)?(\d{4}\s+Winter\s+Olympics)(?:\s*-\s*Day\s*\d+)?", name, re.IGNORECASE
    )
    if match:
        return match.group(1).strip()
    return None


@router.get("", response_model=list[CollectionResponse])
async def get_all_collections(db: AsyncSession = Depends(get_db)) -> list[CollectionResponse]:
    """Get all collections, including consolidated virtual Winter Olympics groups.

    Args:
        db: Database session

    Returns:
        list[CollectionResponse]: List of all collections
    """
    # Query all collections with eager loading of items
    stmt = select(Collection).options(selectinload(Collection.items))
    result = await db.execute(stmt)
    orm_collections: list[Collection] = result.scalars().all()
    logger.info(f"Found {len(orm_collections)} collections in database")

    # Log collection types for debugging
    for col in orm_collections:
        collection_type_value = (
            col.collection_type.value
            if hasattr(col.collection_type, "value")
            else str(col.collection_type)
        )
        logger.debug(
            f"Collection: id={col.id}, name={col.name}, collection_type={collection_type_value}, search_query={col.search_query}"
        )

    # Group potential Olympics day collections
    olympics_groups: dict[str, dict] = {}
    passthrough: list[Collection] = []

    for col in orm_collections:
        key = _extract_olympics_key(col.name)
        if not key:
            passthrough.append(col)
            continue
        group = olympics_groups.get(key)
        if not group:
            group = {
                "key": key,
                "collections": [],
                "items": [],
                "earliest_created": col.created_at,
                "latest_updated": col.updated_at,
            }
            olympics_groups[key] = group

        group["collections"].append(col)
        if col.created_at and (
            group["earliest_created"] is None or col.created_at < group["earliest_created"]
        ):
            group["earliest_created"] = col.created_at
        if col.updated_at and (
            group["latest_updated"] is None or col.updated_at > group["latest_updated"]
        ):
            group["latest_updated"] = col.updated_at

        day_num = _extract_day_number(col.name)
        for item in col.items or []:
            group["items"].append(
                {
                    "item": item,
                    "day": day_num,
                    "source": col.name,
                }
            )

    consolidated: list[CollectionResponse] = []
    for key, group in olympics_groups.items():
        if len(group["collections"]) <= 1:
            # Not actually multiple day collections; pass through the single ORM collection
            passthrough.append(group["collections"][0])
            continue

        # Sort items by day then original order
        sorted_items = sorted(
            group["items"], key=lambda x: (x["day"], getattr(x["item"], "order", 0))
        )

        # Build pydantic CollectionItemResponse list from ORM items but with new sequential order
        consolidated_items = []
        for idx, wrapped in enumerate(sorted_items):
            itm: CollectionItem = wrapped["item"]
            # Ensure media_item relationship is loaded
            _ = itm.media_item
            consolidated_items.append(
                CollectionItem(
                    id=itm.id,
                    collection_id=0,  # virtual
                    media_item_id=itm.media_item_id,
                    order=idx,
                )
            )

        # Convert the temp CollectionItem ORM objects to Pydantic via response model
        items_response = []
        for citem in consolidated_items:
            # Attach media_item for serialization
            media_stmt = select(MediaItem).where(MediaItem.id == citem.media_item_id)
            media_result = await db.execute(media_stmt)
            citem.media_item = media_result.scalar_one_or_none()
            items_response.append(citem)

        virtual = Collection(
            id=0,
            name=key,
            description=f"{len(group['collections'])} day collections consolidated into a single view",
            created_at=group["earliest_created"],
            updated_at=group["latest_updated"],
        )
        virtual.items = items_response  # type: ignore

        # Create pydantic response with virtual flags
        resp = CollectionResponse(
            id=virtual.id,
            name=virtual.name,
            description=virtual.description,
            created_at=virtual.created_at,
            updated_at=virtual.updated_at,
            items=[
                # Convert ORM CollectionItem to Pydantic by leveraging Config.from_attributes
                # FastAPI will handle conversion, but we pre-materialize media_item
                {
                    "id": i.id,
                    "media_item_id": i.media_item_id,
                    "order": i.order,
                    "media_item": i.media_item,
                }
                for i in items_response
            ],
            is_virtual=True,
            source_collections=[c.name for c in group["collections"]],
        )
        consolidated.append(resp)

    # Combine consolidated virtual groups with passthrough real collections
    final_list: list[CollectionResponse] = consolidated + orm_collections_to_responses(passthrough)
    final_list.sort(key=lambda c: c.name or "")
    return final_list


def orm_collections_to_responses(cols: list[Collection]) -> list[CollectionResponse]:
    import logging

    logger = logging.getLogger(__name__)
    responses: list[CollectionResponse] = []
    for col in cols:
        # Ensure media_item is loaded for each item
        for it in col.items or []:
            _ = it.media_item

        # Log collection type for debugging
        collection_type_value = (
            col.collection_type.value
            if hasattr(col.collection_type, "value")
            else str(col.collection_type)
        )
        logger.debug(
            f"Serializing collection: id={col.id}, name={col.name}, collection_type={collection_type_value}"
        )

        # FastAPI/Pydantic will automatically convert ORM to response model
        # The enum should be serialized to its string value automatically
        responses.append(col)
    return responses


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(collection_id: int, db: AsyncSession = Depends(get_db)) -> CollectionResponse:
    """Get collection by ID.

    Args:
        collection_id: Collection ID
        db: Database session

    Returns:
        CollectionResponse: Collection details

    Raises:
        HTTPException: If collection not found
    """
    stmt = select(Collection).where(Collection.id == collection_id).options(
        selectinload(Collection.items)
    )
    result = await db.execute(stmt)
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    collection: CollectionCreate, db: AsyncSession = Depends(get_db)
) -> CollectionResponse:
    """Create a new collection.

    Args:
        collection: Collection creation data
        db: Database session

    Returns:
        CollectionResponse: Created collection

    Raises:
        HTTPException: If collection name already exists
    """
    # Check if name already exists
    stmt = select(Collection).where(Collection.name == collection.name)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Collection name already exists")

    # Log the incoming collection data
    logger.info(
        f"Creating collection: name={collection.name}, collection_type={collection.collection_type}, search_query={collection.search_query}"
    )

    # Convert collection_type string to enum if needed
    collection_dict = collection.model_dump()
    if collection_dict.get("collection_type"):
        # Ensure collection_type is lowercase to match enum values
        collection_type_str = collection_dict["collection_type"].lower()
        from ..database.models import CollectionTypeEnum

        try:
            # Convert string to enum
            collection_dict["collection_type"] = CollectionTypeEnum(collection_type_str)
        except ValueError:
            logger.warning(f"Invalid collection_type '{collection_type_str}', defaulting to MANUAL")
            collection_dict["collection_type"] = CollectionTypeEnum.MANUAL

    db_collection = Collection(**collection_dict)
    db.add(db_collection)
    await db.commit()
    await db.refresh(db_collection)

    # Log the created collection
    collection_type_value = (
        db_collection.collection_type.value
        if hasattr(db_collection.collection_type, "value")
        else str(db_collection.collection_type)
    )
    logger.info(
        f"Created collection: id={db_collection.id}, name={db_collection.name}, collection_type={db_collection.collection_type}, collection_type_value={collection_type_value}"
    )

    return db_collection


@router.post("/{collection_id}/items/{media_id}", status_code=status.HTTP_201_CREATED)
async def add_item_to_collection(collection_id: int, media_id: int, db: AsyncSession = Depends(get_db)):
    """Add media item to collection"""
    stmt = select(Collection).where(Collection.id == collection_id)
    result = await db.execute(stmt)
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    stmt = select(MediaItem).where(MediaItem.id == media_id)
    result = await db.execute(stmt)
    media_item = result.scalar_one_or_none()
    if not media_item:
        raise HTTPException(status_code=404, detail="Media item not found")

    # Check if already in collection
    stmt = select(CollectionItem).where(
        CollectionItem.collection_id == collection_id, 
        CollectionItem.media_item_id == media_id
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Item already in collection")

    # Get max order
    stmt = select(func.count(CollectionItem.id)).where(
        CollectionItem.collection_id == collection_id
    )
    result = await db.execute(stmt)
    max_order = result.scalar() or 0

    collection_item = CollectionItem(
        collection_id=collection_id, media_item_id=media_id, order=max_order
    )
    db.add(collection_item)
    await db.commit()
    return {"message": "Item added to collection"}


@router.delete("/{collection_id}/items/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item_from_collection(collection_id: int, media_id: int, db: AsyncSession = Depends(get_db)):
    """Remove media item from collection"""
    stmt = select(CollectionItem).where(
        CollectionItem.collection_id == collection_id, 
        CollectionItem.media_item_id == media_id
    )
    result = await db.execute(stmt)
    collection_item = result.scalar_one_or_none()
    if not collection_item:
        raise HTTPException(status_code=404, detail="Item not found in collection")

    await db.delete(collection_item)
    await db.commit()


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(collection_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a collection"""
    stmt = select(Collection).where(Collection.id == collection_id)
    result = await db.execute(stmt)
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    await db.delete(collection)
    await db.commit()


@router.post("/consolidate", status_code=status.HTTP_200_OK)
async def consolidate_collections(db: AsyncSession = Depends(get_db)):
    """
    Consolidate single-item collections that belong to the same channel.
    Groups collections by name pattern (e.g., "1980 Winter Olympics - Day 1", "1980 Winter Olympics - Day 2")
    and merges them into a single consolidated collection.
    """
    # Get all collections with their item counts
    stmt = (
        select(Collection, func.count(CollectionItem.id).label("item_count"))
        .outerjoin(CollectionItem)
        .group_by(Collection.id)
    )
    result = await db.execute(stmt)
    collections_with_counts = result.all()

    # Find single-item collections
    single_item_collections = [col for col, count in collections_with_counts if count == 1]

    if not single_item_collections:
        return {
            "message": "No single-item collections found to consolidate",
            "consolidated": 0,
            "groups": [],
        }

    # Group collections by name pattern (e.g., "1980 Winter Olympics - Day 1", "1980 Winter Olympics - Day 2")
    name_pattern_groups = {}
    for collection in single_item_collections:
        # Extract base name (e.g., "1980 Winter Olympics" from "1980 Winter Olympics - Day 1")
        base_name = _extract_base_olympics_name(collection.name)
        if base_name:
            if base_name not in name_pattern_groups:
                name_pattern_groups[base_name] = []
            name_pattern_groups[base_name].append(collection)

    consolidated_count = 0
    consolidated_groups = []

    # Process name pattern groups
    for base_name, collections in name_pattern_groups.items():
        if len(collections) <= 1:
            continue

        # Get all items from these collections, sorted by day number
        all_items = []
        for collection in collections:
            items_stmt = select(CollectionItem).where(CollectionItem.collection_id == collection.id)
            items_result = await db.execute(items_stmt)
            items = items_result.scalars().all()
            for item in items:
                day_num = _extract_day_number(collection.name)
                all_items.append({"item": item, "day": day_num, "collection_name": collection.name})

        # Sort by day number
        all_items.sort(key=lambda x: (x["day"], x["item"].order))

        # Check if consolidated collection already exists
        existing_stmt = select(Collection).where(Collection.name == base_name)
        existing_result = await db.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        if existing:
            # Add items to existing collection
            target_collection = existing
            max_order_stmt = select(func.max(CollectionItem.order)).where(
                CollectionItem.collection_id == existing.id
            )
            max_order_result = await db.execute(max_order_stmt)
            max_order = max_order_result.scalar() or 0
        else:
            # Create new consolidated collection
            target_collection = Collection(
                name=base_name, description=f"Consolidated from {len(collections)} day collections"
            )
            db.add(target_collection)
            await db.flush()  # Get the ID
            max_order = 0

        # Move items to consolidated collection
        for idx, wrapped_item in enumerate(all_items):
            item = wrapped_item["item"]
            new_item = CollectionItem(
                collection_id=target_collection.id,
                media_item_id=item.media_item_id,
                order=max_order + idx,
            )
            db.add(new_item)

        # Update schedules to point to consolidated collection
        for collection in collections:
            schedules_stmt = select(Schedule).where(Schedule.collection_id == collection.id)
            schedules_result = await db.execute(schedules_stmt)
            schedules = schedules_result.scalars().all()
            for schedule in schedules:
                schedule.collection_id = target_collection.id

        # Delete old collections
        for collection in collections:
            await db.delete(collection)

        consolidated_count += len(collections)
        consolidated_groups.append(
            {
                "base_name": base_name,
                "merged_collections": [c.name for c in collections],
                "items_count": len(all_items),
            }
        )

    await db.commit()

    return {
        "message": f"Consolidated {consolidated_count} collections into {len(consolidated_groups)} groups",
        "consolidated": consolidated_count,
        "groups": consolidated_groups,
    }


# ============================================================================
# Smart Collection Endpoints
# ============================================================================


@router.post("/smart", status_code=status.HTTP_201_CREATED)
async def create_smart_collection(
    name: str,
    search_query: str,
    description: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Create a smart collection based on a search query.
    
    Smart collections automatically populate based on search criteria.
    
    Args:
        name: Collection name
        search_query: Search query to find matching media
        description: Optional description
        
    Returns:
        Created smart collection
    """
    from ..database.models import CollectionTypeEnum
    from sqlalchemy import or_
    
    # Check if name already exists
    stmt = select(Collection).where(Collection.name == name)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Collection name already exists")
    
    # Create the smart collection
    db_collection = Collection(
        name=name,
        description=description or f"Smart collection: {search_query}",
        collection_type=CollectionTypeEnum.SMART,
        search_query=search_query,
    )
    db.add(db_collection)
    await db.commit()
    await db.refresh(db_collection)
    
    # Populate the collection based on search query
    # Search in media items by title
    stmt = select(MediaItem).where(
        or_(
            MediaItem.title.ilike(f"%{search_query}%"),
            MediaItem.show_title.ilike(f"%{search_query}%"),
            MediaItem.description.ilike(f"%{search_query}%")
        )
    )
    result = await db.execute(stmt)
    matching_items = result.scalars().all()
    
    for idx, item in enumerate(matching_items):
        collection_item = CollectionItem(
            collection_id=db_collection.id,
            media_item_id=item.id,
            order=idx,
        )
        db.add(collection_item)
    
    await db.commit()
    
    logger.info(f"Created smart collection '{name}' with {len(matching_items)} items")
    
    return {
        "id": db_collection.id,
        "name": db_collection.name,
        "collection_type": "smart",
        "search_query": search_query,
        "item_count": len(matching_items),
    }


@router.post("/smart/{collection_id}/refresh")
async def refresh_smart_collection(collection_id: int, db: AsyncSession = Depends(get_db)):
    """Refresh a smart collection by re-running its search query.
    
    Args:
        collection_id: Smart collection ID
        
    Returns:
        Refresh result with item counts
    """
    from ..database.models import CollectionTypeEnum
    from sqlalchemy import or_, delete
    
    stmt = select(Collection).where(Collection.id == collection_id)
    result = await db.execute(stmt)
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    # Check it's a smart collection
    if not hasattr(collection, 'collection_type') or collection.collection_type != CollectionTypeEnum.SMART:
        raise HTTPException(status_code=400, detail="Collection is not a smart collection")
    
    if not collection.search_query:
        raise HTTPException(status_code=400, detail="Smart collection has no search query")
    
    # Get current item count
    old_count_stmt = select(func.count(CollectionItem.id)).where(
        CollectionItem.collection_id == collection_id
    )
    old_count_result = await db.execute(old_count_stmt)
    old_count = old_count_result.scalar() or 0
    
    # Clear existing items
    delete_stmt = delete(CollectionItem).where(
        CollectionItem.collection_id == collection_id
    )
    await db.execute(delete_stmt)
    
    # Re-run search
    search_query = collection.search_query
    search_stmt = select(MediaItem).where(
        or_(
            MediaItem.title.ilike(f"%{search_query}%"),
            MediaItem.show_title.ilike(f"%{search_query}%"),
            MediaItem.description.ilike(f"%{search_query}%")
        )
    )
    search_result = await db.execute(search_stmt)
    matching_items = search_result.scalars().all()
    
    # Add matching items
    for idx, item in enumerate(matching_items):
        collection_item = CollectionItem(
            collection_id=collection_id,
            media_item_id=item.id,
            order=idx,
        )
        db.add(collection_item)
    
    await db.commit()
    
    logger.info(f"Refreshed smart collection {collection_id}: {old_count} -> {len(matching_items)} items")
    
    return {
        "collection_id": collection_id,
        "previous_count": old_count,
        "new_count": len(matching_items),
        "message": "Smart collection refreshed successfully",
    }


# ============================================================================
# Multi-Collection Endpoints
# ============================================================================


@router.get("/multi")
async def get_all_multi_collections(db: AsyncSession = Depends(get_db)):
    """Get all multi-collections.
    
    Returns:
        List of multi-collections with collection counts.
    """
    from ..database.models.media import MultiCollection, MultiCollectionLink
    
    stmt = select(MultiCollection)
    mc_result = await db.execute(stmt)
    multi_collections = mc_result.scalars().all()
    
    result = []
    for mc in multi_collections:
        link_count_stmt = select(func.count(MultiCollectionLink.id)).where(
            MultiCollectionLink.multi_collection_id == mc.id
        )
        link_count_result = await db.execute(link_count_stmt)
        link_count = link_count_result.scalar() or 0
        
        result.append({
            "id": mc.id,
            "name": mc.name,
            "description": mc.description,
            "collection_count": link_count,
            "created_at": mc.created_at,
            "updated_at": mc.updated_at,
        })
    
    return result


@router.post("/multi", status_code=status.HTTP_201_CREATED)
async def create_multi_collection(
    name: str,
    description: str | None = None,
    collection_ids: list[int] | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Create a multi-collection.
    
    Args:
        name: Multi-collection name
        description: Optional description
        collection_ids: Optional initial collection IDs to include
        
    Returns:
        Created multi-collection
    """
    from ..database.models.media import MultiCollection, MultiCollectionLink
    
    mc = MultiCollection(
        name=name,
        description=description,
    )
    db.add(mc)
    await db.flush()  # Get the ID
    
    # Add initial collections if provided
    if collection_ids:
        for idx, coll_id in enumerate(collection_ids):
            # Verify collection exists
            coll_stmt = select(Collection).where(Collection.id == coll_id)
            coll_result = await db.execute(coll_stmt)
            collection = coll_result.scalar_one_or_none()
            if collection:
                link = MultiCollectionLink(
                    multi_collection_id=mc.id,
                    collection_id=coll_id,
                    position=idx,
                )
                db.add(link)
    
    await db.commit()
    await db.refresh(mc)
    
    logger.info(f"Created multi-collection: {mc.name}")
    
    return {
        "id": mc.id,
        "name": mc.name,
        "description": mc.description,
        "collection_count": len(collection_ids) if collection_ids else 0,
    }


@router.get("/multi/{multi_id}")
async def get_multi_collection(multi_id: int, db: AsyncSession = Depends(get_db)):
    """Get a multi-collection with its collections.
    
    Args:
        multi_id: Multi-collection ID
        
    Returns:
        Multi-collection with linked collections
    """
    from ..database.models.media import MultiCollection, MultiCollectionLink
    
    mc_stmt = select(MultiCollection).where(MultiCollection.id == multi_id)
    mc_result = await db.execute(mc_stmt)
    mc = mc_result.scalar_one_or_none()
    if not mc:
        raise HTTPException(status_code=404, detail="Multi-collection not found")
    
    # Get linked collections
    links_stmt = select(MultiCollectionLink).where(
        MultiCollectionLink.multi_collection_id == multi_id
    ).order_by(MultiCollectionLink.position)
    links_result = await db.execute(links_stmt)
    links = links_result.scalars().all()
    
    collections = []
    for link in links:
        coll_stmt = select(Collection).where(Collection.id == link.collection_id)
        coll_result = await db.execute(coll_stmt)
        collection = coll_result.scalar_one_or_none()
        if collection:
            collections.append({
                "id": collection.id,
                "name": collection.name,
                "position": link.position,
                "link_id": link.id,
            })
    
    return {
        "id": mc.id,
        "name": mc.name,
        "description": mc.description,
        "collections": collections,
        "created_at": mc.created_at,
        "updated_at": mc.updated_at,
    }


@router.put("/multi/{multi_id}")
async def update_multi_collection(
    multi_id: int,
    name: str | None = None,
    description: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Update a multi-collection.
    
    Args:
        multi_id: Multi-collection ID
        name: New name
        description: New description
        
    Returns:
        Updated multi-collection
    """
    from ..database.models.media import MultiCollection
    
    mc_stmt = select(MultiCollection).where(MultiCollection.id == multi_id)
    mc_result = await db.execute(mc_stmt)
    mc = mc_result.scalar_one_or_none()
    if not mc:
        raise HTTPException(status_code=404, detail="Multi-collection not found")
    
    if name is not None:
        mc.name = name
    if description is not None:
        mc.description = description
    
    await db.commit()
    await db.refresh(mc)
    
    return {
        "id": mc.id,
        "name": mc.name,
        "description": mc.description,
    }


@router.delete("/multi/{multi_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_multi_collection(multi_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a multi-collection.
    
    Args:
        multi_id: Multi-collection ID
    """
    from ..database.models.media import MultiCollection
    
    mc_stmt = select(MultiCollection).where(MultiCollection.id == multi_id)
    mc_result = await db.execute(mc_stmt)
    mc = mc_result.scalar_one_or_none()
    if not mc:
        raise HTTPException(status_code=404, detail="Multi-collection not found")
    
    await db.delete(mc)
    await db.commit()


@router.post("/multi/{multi_id}/collections/{collection_id}", status_code=status.HTTP_201_CREATED)
async def add_collection_to_multi(multi_id: int, collection_id: int, db: AsyncSession = Depends(get_db)):
    """Add a collection to a multi-collection.
    
    Args:
        multi_id: Multi-collection ID
        collection_id: Collection ID to add
        
    Returns:
        Success message
    """
    from ..database.models.media import MultiCollection, MultiCollectionLink
    
    mc_stmt = select(MultiCollection).where(MultiCollection.id == multi_id)
    mc_result = await db.execute(mc_stmt)
    mc = mc_result.scalar_one_or_none()
    if not mc:
        raise HTTPException(status_code=404, detail="Multi-collection not found")
    
    coll_stmt = select(Collection).where(Collection.id == collection_id)
    coll_result = await db.execute(coll_stmt)
    collection = coll_result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    # Check if already linked
    existing_stmt = select(MultiCollectionLink).where(
        MultiCollectionLink.multi_collection_id == multi_id,
        MultiCollectionLink.collection_id == collection_id
    )
    existing_result = await db.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Collection already in multi-collection")
    
    # Get max position
    max_pos_stmt = select(func.count(MultiCollectionLink.id)).where(
        MultiCollectionLink.multi_collection_id == multi_id
    )
    max_pos_result = await db.execute(max_pos_stmt)
    max_pos = max_pos_result.scalar() or 0
    
    link = MultiCollectionLink(
        multi_collection_id=multi_id,
        collection_id=collection_id,
        position=max_pos,
    )
    db.add(link)
    await db.commit()
    
    return {"message": "Collection added to multi-collection"}


@router.delete("/multi/{multi_id}/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_collection_from_multi(multi_id: int, collection_id: int, db: AsyncSession = Depends(get_db)):
    """Remove a collection from a multi-collection.
    
    Args:
        multi_id: Multi-collection ID
        collection_id: Collection ID to remove
    """
    from ..database.models.media import MultiCollectionLink
    
    link_stmt = select(MultiCollectionLink).where(
        MultiCollectionLink.multi_collection_id == multi_id,
        MultiCollectionLink.collection_id == collection_id
    )
    link_result = await db.execute(link_stmt)
    link = link_result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(status_code=404, detail="Collection not in multi-collection")
    
    await db.delete(link)
    await db.commit()
