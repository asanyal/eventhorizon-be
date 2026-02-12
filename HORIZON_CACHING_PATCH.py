"""
HORIZON CACHING OPTIMIZATION PATCH

Add this code to main.py to enable caching for horizons endpoint
This is the FASTEST way to fix the 15-20 second delay

INSTRUCTIONS:
1. Add the cache variables after line 50 (after calendar_cache)
2. Replace the /get-horizon endpoint with the optimized version below
"""

# ========== ADD THIS AFTER LINE 50 in main.py (after calendar_cache) ==========

# In-memory cache for Horizon API responses
# Format: {cache_key: (response_data, expiry_timestamp)}
horizon_cache: Dict[str, tuple[List[Any], float]] = {}
HORIZON_CACHE_TTL_SECONDS = 300  # Cache for 5 minutes (adjust as needed)

def get_horizon_cache_key(horizon_date: Optional[str]) -> str:
    """Generate a cache key for horizon queries"""
    return horizon_date if horizon_date else "all_horizons"

def get_cached_horizons(horizon_date: Optional[str]) -> Optional[List[Any]]:
    """Get cached horizons if available and not expired"""
    cache_key = get_horizon_cache_key(horizon_date)
    if cache_key in horizon_cache:
        cached_data, expiry = horizon_cache[cache_key]
        if datetime.datetime.now().timestamp() < expiry:
            return cached_data
        else:
            # Remove expired entry
            del horizon_cache[cache_key]
    return None

def cache_horizons(horizon_date: Optional[str], horizons: List[Any]):
    """Cache horizons with TTL"""
    cache_key = get_horizon_cache_key(horizon_date)
    expiry = datetime.datetime.now().timestamp() + HORIZON_CACHE_TTL_SECONDS
    horizon_cache[cache_key] = (horizons, expiry)

def invalidate_horizon_cache():
    """Clear all horizon cache (call after create/update/delete operations)"""
    global horizon_cache
    horizon_cache.clear()


# ========== REPLACE /get-horizon ENDPOINT WITH THIS ==========

@app.get("/get-horizon", response_model=List[HorizonResponse])
async def get_horizons(
    horizon_date: Optional[str] = Query(default=None, description="Filter by horizon date (YYYY-MM-DD format)"),
    skip_cache: bool = Query(default=False, description="Skip cache and fetch fresh data")
):
    """
    Get all horizon items, optionally filtered by horizon date (with caching)

    Args:
        horizon_date: Optional date filter (YYYY-MM-DD format)
        skip_cache: Force refresh from database (default: false)

    Returns:
        List of horizon items sorted by creation date (newest first)
    """
    import time
    import logging
    logger = logging.getLogger(__name__)

    try:
        endpoint_start = time.time()
        logger.info(f"🔵 [API] GET /get-horizon called with horizon_date={horizon_date}, skip_cache={skip_cache}")

        # Check cache first (unless skip_cache=true)
        if not skip_cache:
            cached_result = get_cached_horizons(horizon_date)
            if cached_result is not None:
                cache_time = (time.time() - endpoint_start) * 1000
                logger.info(f"⚡ [API] Cache HIT! Returned {len(cached_result)} items in {cache_time:.2f}ms")
                return cached_result

        # Cache miss or skip_cache=true, fetch from database
        logger.info(f"💾 [API] Cache MISS, fetching from database...")
        repo_start = time.time()
        result = await horizon_repo.get_all_horizons(horizon_date=horizon_date)
        repo_time = (time.time() - repo_start) * 1000
        logger.info(f"⏱️  [API] Repository call: {repo_time:.2f}ms")

        # Cache the result
        cache_horizons(horizon_date, result)
        logger.info(f"💾 [API] Result cached for {HORIZON_CACHE_TTL_SECONDS}s")

        total_time = (time.time() - endpoint_start) * 1000
        logger.info(f"⏱️  [API] TOTAL endpoint time: {total_time:.2f}ms, returned {len(result)} items")

        return result

    except Exception as e:
        logger.error(f"❌ [API] Failed to retrieve horizons: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve horizons: {str(e)}")


# ========== UPDATE CREATE/UPDATE/DELETE ENDPOINTS TO INVALIDATE CACHE ==========

# Add this line at the end of these functions:
# invalidate_horizon_cache()

# Examples:

@app.post("/add-horizon", response_model=HorizonResponse)
async def add_horizon(
    horizon_data: HorizonCreate,
    type: str = Query(default="none", description="Horizon type", max_length=100),
    horizon_date: Optional[str] = Query(default=None, description="Optional date for the horizon item (YYYY-MM-DD format)")
):
    # ... existing code ...
    result = await horizon_repo.create_horizon(horizon_data)
    invalidate_horizon_cache()  # ADD THIS LINE
    return result


@app.delete("/delete-horizon-by-title")
async def delete_horizon_by_title(title: str = Query(..., description="Title of the horizon(s) to delete")):
    # ... existing code ...
    deleted_count = await horizon_repo.delete_horizon_by_title(title)
    invalidate_horizon_cache()  # ADD THIS LINE
    # ... rest of code ...


@app.delete("/delete-horizon/{horizon_id}")
async def delete_horizon(horizon_id: str):
    # ... existing code ...
    success = await horizon_repo.delete_horizon(horizon_id)
    invalidate_horizon_cache()  # ADD THIS LINE
    # ... rest of code ...


@app.put("/edit-horizon", response_model=List[HorizonResponse])
async def edit_horizon(edit_data: HorizonEdit):
    # ... existing code ...
    updated_horizons = await horizon_repo.edit_horizon_by_criteria(edit_data)
    invalidate_horizon_cache()  # ADD THIS LINE
    return updated_horizons


# ========== EXPECTED RESULTS ==========

"""
BEFORE CACHING:
- First request: 15-20 seconds
- Subsequent requests: 15-20 seconds (no improvement)

AFTER CACHING:
- First request: 15-20 seconds (cache miss - fetches from DB)
- Subsequent requests: 50-200ms (cache hit - instant!)
- Cache auto-expires after 5 minutes
- Manual refresh available with ?skip_cache=true

This should solve 90% of the performance problem for read operations!
"""
