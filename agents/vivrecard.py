"""
VivreCard — Proactive Scheduler for MrAgent
Rewritten to use the new CronService, keeping the agent 'alive' and performing periodic tasks.

Created: 2026-03-02
"""

import asyncio
import threading

from utils.logger import get_logger
from tools.cron_tool import cron_service
from utils.cron.types import CronJob

logger = get_logger("agents.vivrecard")


class VivreCard(threading.Thread):
    """
    Background scheduler thread that executes tasks based on the CronService.
    Now supports actual agent cognitive loop triggers.
    """

    def __init__(self):
        super().__init__(daemon=True)
        self.running = False
        self.loop = None

    async def _handle_cron_job(self, job: CronJob) -> str | None:
        """
        Callback executed by the CronService when a job triggers.
        """
        from agents.core import AgentCore
        
        logger.info(f"VivreCard: Triggered job {job.id} ({job.name})")
        
        # Start a temporary AgentCore instance dedicated to running this task.
        # This keeps the background task entirely isolated from any active CLI/Web chat sessions.
        
        try:
            agent = AgentCore(model_mode="auto")
            
            # The payload message represents what the agent should do
            instruction = f"[Cron Job Triggered: {job.name}]\nTask to perform: {job.payload.message}"
            
            logger.debug(f"VivreCard: Injecting into AgentCore: {instruction}")
            
            # Use chat without streaming for background tasks
            response = agent.chat(instruction, stream=False)
            
            logger.info(f"VivreCard: Job {job.id} completed. Response preview: {response[:100]}...")
            return response
            
        except Exception as e:
            logger.error(f"VivreCard: Error executing scheduled agent task: {e}")
            return f"Error: {e}"

    def run(self):
        """Main scheduler loop."""
        self.running = True
        logger.info("VivreCard Scheduler (CronService backend) thread starting...")

        # Set up a new async event loop for this background thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Wire up the execution callback
        cron_service.on_job = self._handle_cron_job

        # Run the cron service
        self.loop.run_until_complete(self._run_cron_loop())

    async def _run_cron_loop(self):
        await cron_service.start()
        
        # Keep the loop alive
        while self.running:
            await asyncio.sleep(1)
            
        cron_service.stop()

    def stop(self):
        """Stop the scheduler."""
        self.running = False
        logger.info("VivreCard Scheduler stopping...")
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
