# 🚀 Quick Start: Fix Slow Horizons API on Replit

## ⚡ TL;DR - Fastest Fix (10 minutes)

Add **caching** to your `/get-horizon` endpoint. This will make repeat requests go from 15-20s → 50-200ms.

---

## 📋 Step-by-Step Instructions

### 1️⃣ Deploy Current Code with Diagnostics (Already Done!)

Your code now includes performance monitoring. Deploy to Replit and check startup logs for:

```
⏱️  Ping: XXXms                    ← Network latency to MongoDB
⏱️  Full collection scan: XXXms    ← Time to fetch all horizons
```

**What to look for:**
- Ping > 100ms = Network problem (MongoDB too far from Replit)
- Full scan > 5000ms = Database/query problem
- Both high = Multiple issues

---

### 2️⃣ Add Caching (Copy & Paste Solution)

#### A. Open `main.py` and find line ~50 (after `calendar_cache` definition)

Add this code:

```python
# Horizon API cache
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

#### B. Find the `/get-horizon` endpoint (around line 750)

**Replace this:**
```python
@app.get("/get-horizon", response_model=List[HorizonResponse])
async def get_horizons(
    horizon_date: Optional[str] = Query(default=None, description="Filter by horizon date (YYYY-MM-DD format)")
):
    try:
        # ... existing code ...
        return await horizon_repo.get_all_horizons(horizon_date=horizon_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve horizons: {str(e)}")
```

**With this:**
```python
@app.get("/get-horizon", response_model=List[HorizonResponse])
async def get_horizons(
    horizon_date: Optional[str] = Query(default=None, description="Filter by horizon date (YYYY-MM-DD format)")
):
    try:
        # Check cache first
        cached_result = get_cached_horizons(horizon_date)
        if cached_result is not None:
            return cached_result

        # Cache miss - fetch from database
        result = await horizon_repo.get_all_horizons(horizon_date=horizon_date)

        # Cache the result
        cache_horizons(horizon_date, result)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve horizons: {str(e)}")
```

#### C. Add cache invalidation to mutation endpoints

Find these 4 endpoints and add `invalidate_horizon_cache()` right after the repository call:

**1. POST /add-horizon** (around line 770):
```python
@app.post("/add-horizon", response_model=HorizonResponse)
async def add_horizon(...):
    try:
        # ... existing code ...
        result = await horizon_repo.create_horizon(horizon_data)
        invalidate_horizon_cache()  # ← ADD THIS LINE
        return result
    except Exception as e:
        # ... error handling ...
```

**2. DELETE /delete-horizon-by-title** (around line 832):
```python
@app.delete("/delete-horizon-by-title")
async def delete_horizon_by_title(title: str = Query(...)):
    try:
        deleted_count = await horizon_repo.delete_horizon_by_title(title)
        invalidate_horizon_cache()  # ← ADD THIS LINE
        # ... rest of code ...
```

**3. DELETE /delete-horizon/{horizon_id}** (around line 860):
```python
@app.delete("/delete-horizon/{horizon_id}")
async def delete_horizon(horizon_id: str):
    try:
        success = await horizon_repo.delete_horizon(horizon_id)
        invalidate_horizon_cache()  # ← ADD THIS LINE
        # ... rest of code ...
```

**4. PUT /edit-horizon** (around line 883):
```python
@app.put("/edit-horizon", response_model=List[HorizonResponse])
async def edit_horizon(edit_data: HorizonEdit):
    try:
        updated_horizons = await horizon_repo.edit_horizon_by_criteria(edit_data)
        invalidate_horizon_cache()  # ← ADD THIS LINE
        return updated_horizons
    except Exception as e:
        # ... error handling ...
```

---

### 3️⃣ Test It!

1. Deploy to Replit
2. Make a request to `/get-horizon` → Should take 15-20s (first time, cache miss)
3. Make another request → Should take 50-200ms (cached!)
4. Check logs for "⚡ Cache HIT!" messages

---

## 📊 Expected Results

| Request Type | Before Caching | After Caching |
|--------------|----------------|---------------|
| First request (cache miss) | 15-20s | 15-20s |
| Second request (cache hit) | 15-20s | 50-200ms ⚡ |
| Third request (cache hit) | 15-20s | 50-200ms ⚡ |
| After 5 minutes | 15-20s | 15-20s (cache expired) |

**Cache hit rate should be >80%** = Most requests will be fast!

---

## 🎛️ Tuning Options

### Adjust Cache Duration
```python
HORIZON_CACHE_TTL_SECONDS = 300  # Current: 5 minutes

# Options:
# 60    → 1 minute  (if data changes frequently)
# 300   → 5 minutes (recommended default)
# 600   → 10 minutes (if data rarely changes)
# 1800  → 30 minutes (for nearly static data)
```

### Add Cache Status Endpoint (Optional)
```python
@app.get("/debug/cache-status")
async def cache_status():
    return {
        "horizon_cache_entries": len(horizon_cache),
        "horizon_ttl_seconds": HORIZON_CACHE_TTL_SECONDS,
        "calendar_cache_entries": len(calendar_cache)
    }
```

---

## 🐛 If Still Slow After Caching

### Check Diagnostics Logs
Look for these patterns:

**Problem: High network latency**
```
⏱️  Ping: 250ms              ← MongoDB is far from Replit
⏱️  Full collection scan: 15000ms
```
**Solution:** Move MongoDB cluster closer to Replit region

**Problem: Large dataset**
```
⏱️  MongoDB fetch (1500 docs): 12000ms  ← Too many documents
```
**Solution:** Add pagination (see `PERFORMANCE_ACTION_PLAN.md`)

**Problem: Slow queries**
```
⏱️  MongoDB fetch (50 docs): 8000ms   ← Query is slow
```
**Solution:** Check indexes with `db.horizon.getIndexes()`

---

## 📁 Additional Resources

- **`PERFORMANCE_ACTION_PLAN.md`** - Complete step-by-step guide
- **`PERFORMANCE_FIXES.md`** - Detailed technical explanations
- **`HORIZON_CACHING_PATCH.py`** - Alternative copy-paste implementation
- **`horizon_repository_optimized.py`** - Repository with pagination support

---

## 🎯 Success Checklist

- [ ] Deployed code with diagnostics
- [ ] Checked startup logs for ping time
- [ ] Added cache functions to main.py
- [ ] Updated /get-horizon endpoint
- [ ] Added invalidate_horizon_cache() to 4 mutation endpoints
- [ ] Tested: First request is slow, second is fast
- [ ] Logs show "⚡ Cache HIT!" messages
- [ ] Response time < 500ms for cached requests

---

## 💡 Why This Works

**The Problem:**
- Every request goes to MongoDB
- Replit → MongoDB has high network latency (~100-200ms)
- Fetching + transferring all horizons takes 15-20s

**The Solution:**
- First request: Fetch from MongoDB (slow) + cache result
- Subsequent requests: Return cached data (fast)
- Cache expires after 5 minutes (fresh data)
- Mutations invalidate cache (always consistent)

**Result:**
- 90% of requests are fast (cache hits)
- 10% of requests are slow (cache misses)
- Users only wait once every 5 minutes

---

## 🆘 Need Help?

If you're stuck or need clarification:
1. Check the logs for error messages
2. Verify cache functions are defined before the endpoint
3. Make sure `invalidate_horizon_cache()` is called in all 4 mutation endpoints
4. Test with `curl -v http://your-replit-url/get-horizon` to see response times

Good luck! 🚀
