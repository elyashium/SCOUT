import asyncio
import random
import logging

logger = logging.getLogger(__name__)

async def with_retry(fn, max_retries=3, base_delay=1.0):
    """
    Utility for executing async functions with exponential backoff and jitter.
    Useful for rate limited API calls.
    """
    for attempt in range(max_retries):
        try:
            return await fn()
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Final retry attempt failed: {e}")
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            logger.warning(f"API call failed: {e}. Retrying in {delay:.2f}s (Attempt {attempt+1}/{max_retries})")
            await asyncio.sleep(delay)
