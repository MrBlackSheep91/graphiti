import asyncio
import traceback
from functools import partial

from fastapi import APIRouter, status
from graphiti_core.nodes import EpisodeType  # type: ignore
from graphiti_core.utils.maintenance.graph_data_operations import clear_data  # type: ignore

from graph_service.dto import AddEntityNodeRequest, AddMessagesRequest, Message, Result
from graph_service.zep_graphiti import ZepGraphitiDep


class AsyncWorker:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.task = None
        self.jobs_processed = 0
        self.jobs_failed = 0

    async def worker(self):
        print("AsyncWorker: Worker loop started, waiting for jobs...")
        while True:
            try:
                job = await self.queue.get()
                queue_size = self.queue.qsize()
                print(f'AsyncWorker: Processing job #{self.jobs_processed + 1} (queue size: {queue_size})')
                
                try:
                    await job()
                    self.jobs_processed += 1
                    print(f'AsyncWorker: Job completed successfully! Total processed: {self.jobs_processed}')
                except Exception as e:
                    self.jobs_failed += 1
                    print(f'AsyncWorker ERROR: Job failed with exception: {type(e).__name__}: {e}')
                    print(f'AsyncWorker ERROR: Traceback: {traceback.format_exc()}')
                    print(f'AsyncWorker: Total failed: {self.jobs_failed}')
                
            except asyncio.CancelledError:
                print("AsyncWorker: Worker cancelled, shutting down...")
                break

    async def start(self):
        print("AsyncWorker: Starting worker task...")
        self.task = asyncio.create_task(self.worker())
        print("AsyncWorker: Worker task created")

    async def stop(self):
        print(f"AsyncWorker: Stopping... Processed: {self.jobs_processed}, Failed: {self.jobs_failed}")
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        remaining = 0
        while not self.queue.empty():
            self.queue.get_nowait()
            remaining += 1
        print(f"AsyncWorker: Stopped. Cleared {remaining} remaining jobs from queue.")


async_worker = AsyncWorker()


# FIX: Router lifespan removed - it doesn't execute when router is included in main app
# The async_worker is now started/stopped in main.py lifespan instead

router = APIRouter()  # No lifespan - handled by main app


@router.post('/messages', status_code=status.HTTP_202_ACCEPTED)
async def add_messages(
    request: AddMessagesRequest,
    graphiti: ZepGraphitiDep,
):
    async def add_messages_task(m: Message):
        print(f"add_messages_task: Starting for uuid={m.uuid}, group={request.group_id}")
        await graphiti.add_episode(
            uuid=m.uuid,
            group_id=request.group_id,
            name=m.name,
            episode_body=f'{m.role or ""}({m.role_type}): {m.content}',
            reference_time=m.timestamp,
            source=EpisodeType.message,
            source_description=m.source_description,
        )
        print(f"add_messages_task: Completed for uuid={m.uuid}")

    for m in request.messages:
        await async_worker.queue.put(partial(add_messages_task, m))
    
    print(f"add_messages: Queued {len(request.messages)} messages for group={request.group_id}")
    return Result(message='Messages added to processing queue', success=True)


@router.post('/entity-node', status_code=status.HTTP_201_CREATED)
async def add_entity_node(
    request: AddEntityNodeRequest,
    graphiti: ZepGraphitiDep,
):
    node = await graphiti.save_entity_node(
        uuid=request.uuid,
        group_id=request.group_id,
        name=request.name,
        summary=request.summary,
    )
    return node


@router.delete('/entity-edge/{uuid}', status_code=status.HTTP_200_OK)
async def delete_entity_edge(uuid: str, graphiti: ZepGraphitiDep):
    await graphiti.delete_entity_edge(uuid)
    return Result(message='Entity Edge deleted', success=True)


@router.delete('/group/{group_id}', status_code=status.HTTP_200_OK)
async def delete_group(group_id: str, graphiti: ZepGraphitiDep):
    await graphiti.delete_group(group_id)
    return Result(message='Group deleted', success=True)


@router.delete('/episode/{uuid}', status_code=status.HTTP_200_OK)
async def delete_episode(uuid: str, graphiti: ZepGraphitiDep):
    await graphiti.delete_episodic_node(uuid)
    return Result(message='Episode deleted', success=True)


@router.post('/clear', status_code=status.HTTP_200_OK)
async def clear(
    graphiti: ZepGraphitiDep,
):
    await clear_data(graphiti.driver)
    await graphiti.build_indices_and_constraints()
    return Result(message='Graph cleared', success=True)
