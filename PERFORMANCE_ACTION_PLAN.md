# 🚀 Performance Optimization Action Plan

## 🔴 Problem
- **Localhost**: Fast response (~50-200ms)
- **Replit**: 15-20 seconds for Horizons API
- **Root Cause**: Network latency + no caching + full collection scan

---

## ✅ STEP 1: Deploy Diagnostics (5 minutes)

**What to do:**
1. Current diagnostic code has been added to:
   - `horizon_repository.py` (performance timing)
   - `main.py` (endpoint timing + MongoDB diagnostics)
   - `mongodb_diagnostics.py` (connection diagnostics)

2. Deploy to Replit and check logs on startup:
   ```
   Look for these lines:
   ⏱️  Ping: XXXms
   ⏱️  Full collection scan: XXXms
   ⏱️  Query 10 horizons: XXXms
   ```

3. Make a request to `/get-horizon` and check logs:
   ```
   ⏱️  [Horizon] MongoDB fetch: XXXms
   ⏱️  [Horizon] TOTAL get_all_horizons: XXXms
   ⏱️  [API] TOTAL endpoint time: XXXms
   ```

**What you'll learn:**
- If `Ping > 100ms` → Network latency is the problem
- If `MongoDB fetch > 5000ms` → Database query is slow
- If `Total endpoint > Total repository` → Serialization overhead

---

## ⚡ STEP 2: Apply Quick Fix - CACHING (10 minutes)

**Impact:** Should reduce 15-20s → 50-200ms for repeated requests

**Files to modify:**

### 2A. Add cache variables to `main.py` (after line 50)
```python
# Add after calendar_cache definition:
horizon_cache: Dict[str, tuple[List[Any], float]] = {}
HORIZON_CACHE_TTL_SECONDS = 300  # 5 minutes

def get_horizon_cache_key(horizon_date: Optional[str]) -> str:
    return horizon_date if horizon_date else "all_horizons"

def get_cached_horizons(horizon_date: Optional[str]) -> Optional[List[Any]]:
    cache_key = get_horizon_cache_key(horizon_date)
    if cache_key in horizon_cache:
        cached_data, expiry = horizon_cache[cache_key]
        if datetime.datetime.now().timestamp() < expiry:
            return cached_data
        else:
            del horizon_cache[cache_key]
    return None

def cache_horizons(horizon_date: Optional[str], horizons: List[Any]):
    cache_key = get_horizon_cache_key(horizon_date)
    expiry = datetime.datetime.now().timestamp() + HORIZON_CACHE_TTL_SECONDS
    horizon_cache[cache_key] = (horizons, expiry)

def invalidate_horizon_cache():
    global horizon_cache
    horizon_cache.clear()
```

### 2B. Update `/get-horizon` endpoint (around line 750)
Replace the endpoint with:
```python
@app.get("/get-horizon", response_model=List[HorizonResponse])
async def get_horizons(
    horizon_date: Optional[str] = Query(default=None, description="Filter by horizon date (YYYY-MM-DD format)")
):
    import time
    import logging
    logger = logging.getLogger(__name__)

    try:
        endpoint_start = time.time()
        logger.info(f"🔵 [API] GET /get-horizon called")

        # Check cache first
        cached_result = get_cached_horizons(horizon_date)
        if cached_result is not None:
            cache_time = (time.time() - endpoint_start) * 1000
            logger.info(f"⚡ Cache HIT! {cache_time:.2f}ms")
            return cached_result

        # Cache miss - fetch from database
        logger.info(f"💾 Cache MISS - fetching from DB")
        result = await horizon_repo.get_all_horizons(horizon_date=horizon_date)

        # Cache the result
        cache_horizons(horizon_date, result)

        total_time = (time.time() - endpoint_start) * 1000
        logger.info(f"⏱️  TOTAL: {total_time:.2f}ms, {len(result)} items")
        return result

    except Exception as e:
        logger.error(f"❌ Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve horizons: {str(e)}")
```

### 2C. Invalidate cache on mutations
Add `invalidate_horizon_cache()` to:
- `POST /add-horizon` (after `horizon_repo.create_horizon()`)
- `DELETE /delete-horizon/{horizon_id}` (after `horizon_repo.delete_horizon()`)
- `DELETE /delete-horizon-by-title` (after `horizon_repo.delete_horizon_by_title()`)
- `PUT /edit-horizon` (after `horizon_repo.edit_horizon_by_criteria()`)

Example:
```python
@app.post("/add-horizon", response_model=HorizonResponse)
async def add_horizon(...):
    result = await horizon_repo.create_horizon(horizon_data)
    invalidate_horizon_cache()  # ADD THIS LINE
    return result
```

---

## 🔧 STEP 3: If Still Slow - Add Pagination (15 minutes)

**When to do this:** If diagnostics show you're returning 100+ horizons

### 3A. Update repository method signature
In `horizon_repository.py`, modify `get_all_horizons`:
```python
async def get_all_horizons(
    self,
    horizon_date: Optional[str] = None,
    limit: int = 100,
    skip: int = 0
) -> List[HorizonResponse]:
    # ... existing code ...
    cursor = self.collection.find(query).sort("created_at", -1).limit(limit).skip(skip)
    # ... rest of code ...
```

### 3B. Update API endpoint
```python
@app.get("/get-horizon", response_model=List[HorizonResponse])
async def get_horizons(
    horizon_date: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0)
):
    # Update cache key to include limit/skip
    # Update repository call to pass limit/skip
    return await horizon_repo.get_all_horizons(horizon_date, limit, skip)
```

---

## 🌍 STEP 4: If Network Latency > 100ms - Fix MongoDB Region (30 minutes)

### Check Current Setup
1. **Find Replit Region:**
   - Deploy logs usually show region (e.g., "us-east-1")
   - Or: Add this to startup:
     ```python
     import socket
     print(f"Server hostname: {socket.gethostname()}")
     ```

2. **Find MongoDB Region:**
   - Log into MongoDB Atlas
   - Go to your cluster
   - Check "Configuration" → shows region (e.g., "US East (N. Virginia)")

### If Mismatched:
1. **Option A - Migrate MongoDB Cluster:**
   - Create new cluster in same region as Replit
   - Use MongoDB Atlas migration tools
   - Update connection string

2. **Option B - Use MongoDB Multi-Region:**
   - Upgrade to M10+ cluster
   - Add read replicas in Replit's region
   - Use read preference "nearest"

---

## 📊 Expected Results

### After Diagnostics Only:
- Know exactly where the bottleneck is
- Can make informed decisions

### After Caching:
- **First request:** Still 15-20s (cache miss)
- **Subsequent requests:** 50-200ms (cache hit)
- **User experience:** Much better for most users

### After Caching + Pagination:
- **First request:** 5-10s (smaller dataset)
- **Subsequent requests:** 50-200ms
- **Data transfer:** Reduced by 50-90%

### After Caching + Region Fix:
- **First request:** 500ms-2s
- **Subsequent requests:** 50-200ms
- **Best overall solution**

---

## 🎯 Recommended Path

1. ✅ **Today:** Deploy diagnostics → identify root cause (5 min)
2. ✅ **Today:** Add caching → immediate relief (10 min)
3. ⏳ **If needed:** Add pagination → reduce data transfer (15 min)
4. ⏳ **If needed:** Fix MongoDB region → long-term solution (30+ min)

---

## 🐛 Troubleshooting

### Cache not working?
```python
# Check cache status - add this endpoint:
@app.get("/cache-status")
async def cache_status():
    return {
        "horizon_cache_size": len(horizon_cache),
        "calendar_cache_size": len(calendar_cache),
        "horizon_ttl": HORIZON_CACHE_TTL_SECONDS
    }
```

### Still slow after caching?
- Check logs for "Cache HIT" vs "Cache MISS"
- Verify TTL is reasonable (300s = 5 minutes)
- Check if frontend is adding random query params

### Network latency > 200ms?
- MongoDB region is wrong - need to migrate
- Or: Add Redis/Memcached for distributed caching
- Or: Consider using MongoDB local read replicas

---

## 📝 Files Reference

- `PERFORMANCE_FIXES.md` - Detailed explanation of all fixes
- `HORIZON_CACHING_PATCH.py` - Copy-paste caching code
- `horizon_repository_optimized.py` - Pagination-enabled repository
- `mongodb_diagnostics.py` - Connection diagnostics
- `performance_diagnostics.py` - Generic performance utilities

---

## 💡 Pro Tips

1. **Start with caching** - Easiest and fastest win
2. **Monitor cache hit rate** - Should be >80% for good performance
3. **Adjust TTL based on data change frequency**:
   - Horizons rarely change? → 600s (10 min)
   - Horizons change frequently? → 60s (1 min)
4. **Use `?skip_cache=true`** for testing/debugging
5. **Clear cache on data mutations** - Prevent stale data

---

## 🎉 Success Metrics

After implementing fixes, you should see:
- ✅ Ping < 50ms (good) or < 100ms (acceptable)
- ✅ Cache hit rate > 80%
- ✅ 90% of requests < 500ms
- ✅ Only first request slow (cache miss)
- ✅ Logs showing "Cache HIT" messages
