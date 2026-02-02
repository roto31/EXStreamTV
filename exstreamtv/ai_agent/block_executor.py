"""
Block Schedule Executor for AI Channel Creation

Converts AI-generated ScheduleBlock configurations from BuildPlan
into persistent database Block, BlockGroup, and BlockItem entities.

This bridges the gap between the AI channel creation system and
the ErsatzTV-style block scheduling database model.
"""

import logging
from dataclasses import dataclass, field
from datetime import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from exstreamtv.ai_agent.build_plan_generator import BuildPlan, ScheduleBlock, PlayoutMode
from exstreamtv.database.models.schedule import Block, BlockGroup, BlockItem

logger = logging.getLogger(__name__)


# Day-of-week bitmask values (matches database model)
DAY_BITS = {
    "sunday": 1,
    "monday": 2,
    "tuesday": 4,
    "wednesday": 8,
    "thursday": 16,
    "friday": 32,
    "saturday": 64,
}


@dataclass
class BlockInfo:
    """Information about a created block."""
    
    id: int
    name: str
    start_time: time
    duration_minutes: int
    days_of_week: int
    item_count: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "duration_minutes": self.duration_minutes,
            "days_of_week": self.days_of_week,
            "item_count": self.item_count,
        }


@dataclass
class BlockExecutionResult:
    """Result of block schedule execution."""
    
    group_id: int
    group_name: str
    blocks: list[BlockInfo] = field(default_factory=list)
    items_created: int = 0
    
    @property
    def block_count(self) -> int:
        return len(self.blocks)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "group_name": self.group_name,
            "blocks": [b.to_dict() for b in self.blocks],
            "block_count": self.block_count,
            "items_created": self.items_created,
        }


class BlockScheduleExecutor:
    """
    Executes AI-generated block schedules into the database.
    
    Takes ScheduleBlock configurations from a BuildPlan and creates:
    - BlockGroup (container for all blocks)
    - Block entities (time-based programming blocks)
    - BlockItem entities (links blocks to collections)
    """
    
    def __init__(self):
        """Initialize the block schedule executor."""
        logger.info("BlockScheduleExecutor initialized")
    
    async def execute(
        self,
        plan: BuildPlan,
        channel_name: str,
        collection_map: dict[str, int],
        db: AsyncSession,
    ) -> BlockExecutionResult:
        """
        Execute the block schedule from a build plan.
        
        Args:
            plan: The BuildPlan containing schedule configuration
            channel_name: Name of the channel (used for group naming)
            collection_map: Mapping of collection names to database IDs
            db: Database session
            
        Returns:
            BlockExecutionResult with created entities
        """
        if not plan.schedule or not plan.schedule.blocks:
            logger.warning("No schedule blocks in plan, skipping block creation")
            group = await self._create_block_group(f"{channel_name} Blocks", db)
            return BlockExecutionResult(
                group_id=group.id,
                group_name=group.name,
                blocks=[],
                items_created=0,
            )
        
        group_name = f"{channel_name} Schedule Blocks"
        group = await self._create_block_group(group_name, db)
        
        logger.info(f"Created BlockGroup '{group_name}' (id={group.id})")
        
        created_blocks: list[BlockInfo] = []
        total_items = 0
        
        for schedule_block in plan.schedule.blocks:
            try:
                db_block = await self._create_block(
                    schedule_block=schedule_block,
                    group_id=group.id,
                    db=db,
                )
                
                items_count = await self._create_block_items(
                    block=db_block,
                    schedule_block=schedule_block,
                    collection_map=collection_map,
                    db=db,
                )
                
                total_items += items_count
                
                created_blocks.append(BlockInfo(
                    id=db_block.id,
                    name=db_block.name,
                    start_time=db_block.start_time,
                    duration_minutes=db_block.duration_minutes,
                    days_of_week=db_block.days_of_week,
                    item_count=items_count,
                ))
                
                logger.info(
                    f"Created Block '{db_block.name}' at {db_block.start_time} "
                    f"({db_block.duration_minutes}min, {items_count} items)"
                )
                
            except Exception as e:
                logger.exception(f"Error creating block '{schedule_block.name}': {e}")
        
        return BlockExecutionResult(
            group_id=group.id,
            group_name=group.name,
            blocks=created_blocks,
            items_created=total_items,
        )
    
    async def _create_block_group(self, name: str, db: AsyncSession) -> BlockGroup:
        """Create a BlockGroup in the database."""
        group = BlockGroup(name=name)
        db.add(group)
        await db.flush()
        return group
    
    async def _create_block(
        self,
        schedule_block: ScheduleBlock,
        group_id: int,
        db: AsyncSession,
    ) -> Block:
        """Create a Block entity from an AI ScheduleBlock."""
        start_time = self._parse_time(schedule_block.start_time)
        days_bitmask = self._days_to_bitmask(schedule_block.days_of_week)
        
        block = Block(
            name=schedule_block.name,
            group_id=group_id,
            start_time=start_time,
            duration_minutes=schedule_block.duration_minutes,
            days_of_week=days_bitmask,
        )
        
        db.add(block)
        await db.flush()
        return block
    
    async def _create_block_items(
        self,
        block: Block,
        schedule_block: ScheduleBlock,
        collection_map: dict[str, int],
        db: AsyncSession,
    ) -> int:
        """Create BlockItem entities linking a block to collections."""
        collection_name = schedule_block.collection_name
        
        if not collection_name:
            logger.debug(f"Block '{block.name}' has no collection assigned")
            return 0
        
        collection_id = collection_map.get(collection_name)
        
        if collection_id is None:
            logger.warning(
                f"Collection '{collection_name}' not found for block '{block.name}'"
            )
            return 0
        
        playback_order = self._get_playback_order(schedule_block.playout_mode)
        
        block_item = BlockItem(
            block_id=block.id,
            position=1,
            collection_type="collection",
            collection_id=collection_id,
            playback_order=playback_order,
            include_in_guide=True,
        )
        
        db.add(block_item)
        await db.flush()
        
        logger.debug(f"Created BlockItem for block '{block.name}' -> collection {collection_id}")
        return 1
    
    def _parse_time(self, time_str: str) -> time:
        """Parse HH:MM time string to time object."""
        try:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            return time(hour=hour, minute=minute)
        except (ValueError, IndexError) as e:
            logger.warning(f"Invalid time format '{time_str}': {e}")
            return time(hour=0, minute=0)
    
    def _days_to_bitmask(self, days: list[str]) -> int:
        """Convert list of day names to bitmask."""
        if not days:
            return 127
        
        bitmask = 0
        for day in days:
            bitmask |= DAY_BITS.get(day.lower().strip(), 0)
        
        return bitmask if bitmask > 0 else 127
    
    def _get_playback_order(self, playout_mode: PlayoutMode | str) -> str:
        """Get playback order string from playout mode."""
        if isinstance(playout_mode, PlayoutMode):
            mode_str = playout_mode.value
        else:
            mode_str = str(playout_mode).lower()
        
        order_map = {
            "flood": "chronological",
            "continuous": "chronological",
            "shuffle": "shuffled",
            "random": "random",
            "loop": "chronological",
        }
        
        return order_map.get(mode_str, "chronological")
    
    @staticmethod
    def bitmask_to_days(bitmask: int) -> list[str]:
        """Convert bitmask back to list of day names."""
        return [day for day, bit in DAY_BITS.items() if bitmask & bit]
