# Performance Optimization Guide

## Problem
Horizons API takes 15-20 seconds on Replit but fast on localhost.

## Root Causes (Likely)

### 1. **Network Latency (Most Likely)**
- Replit servers may be geographically far from MongoDB Atlas cluster
- Each MongoDB query adds network round-trip time
- Localhost has near-zero latency to MongoDB

### 2. **No Pagination**
- `/get-horizon` returns ALL horizons in one query
- Large result sets = more network transfer time
- More serialization overhead

### 3. **No Caching**
- Every request hits MongoDB
- Horizons don't change frequently but are fetched repeatedly

### 4. **Connection Pool Issues**
- Despite warmup, connections may timeout between requests
- New connections = DNS resolution + TCP handshake + TLS negotiation

## Solutions Implemented

### ✅ Diagnostics Added
- `mongodb_diagnostics.py` - Run on startup to measure:
  - Ping latency
  - Query performance
  - Network assessment
- Performance logging in `horizon_repository.py` and API endpoint

### 🔧 Quick Fixes (Apply These)

#### Fix 1: Add Response Caching (Like Calendar Events)
```python
# In main.py, add horizon cache
horizon_cache: Dict[str, tuple[List[HorizonResponse], float]] = {}
HORIZON_CACHE_TTL_SECONDS = 300  # 5 minutes

def get_cached_horizons(horizon_date: Optional[str]) -> Optional[List[HorizonResponse]]:
    cache_key = horizon_date or "all"
    if cache_key in horizon_cache:
        cached_data, expiry = horizon_cache[cache_key]
        if datetime.datetime.now().timestamp() < expiry:
            return cached_data
        else:
            del horizon_cache[cache_key]
    return None

def cache_horizons(horizon_date: Optional[str], horizons: List[HorizonResponse]):
    cache_key = horizon_date or "all"
    expiry = datetime.datetime.now().timestamp() + HORIZON_CACHE_TTL_SECONDS
    horizon_cache[cache_key] = (horizons, expiry)
```

#### Fix 2: Add Pagination
```python
@app.get("/get-horizon", response_model=List[HorizonResponse])
async def get_horizons(
    horizon_date: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0)
):
    # Add limit/skip to repository call
    return await horizon_repo.get_all_horizons(horizon_date, limit, skip)
```

#### Fix 3: Use Projection (Return Only Needed Fields)
If frontend doesn't need all fields, use MongoDB projection:
```python
cursor = self.collection.find(
    query,
    {"title": 1, "horizon_date": 1, "type": 1, "created_at": 1}  # Exclude large fields
).sort("created_at", -1)
```

#### Fix 4: Increase Connection Pool
```python
# In database.py
self.client = MongoClient(
    mongodb_url,
    maxPoolSize=100,  # Increase from 50
    minPoolSize=20,   # Increase from 10
    maxIdleTimeMS=60000,  # Increase idle timeout
)
```

#### Fix 5: Move MongoDB Cluster Closer to Replit
- Check Replit region (likely US East or West)
- Check MongoDB Atlas cluster region
- If mismatched, migrate MongoDB cluster to same region

## Testing

### 1. Run Diagnostics
Deploy to Replit and check logs for:
```
⏱️  Ping: XXXms
⏱️  Full collection scan: XXXms
```

### 2. Expected Results
- **Good**: Ping < 50ms, Query < 100ms
- **Moderate**: Ping 50-100ms, Query 100-300ms
- **Bad**: Ping > 100ms, Query > 500ms

### 3. If Network Latency is High (>100ms)
- **Solution A**: Move MongoDB cluster to same region as Replit
- **Solution B**: Implement aggressive caching (5-10 min TTL)
- **Solution C**: Add Redis cache layer

### 4. If Query is Slow but Ping is Fast
- Check indexes: `db.horizon.getIndexes()`
- Run explain plan: `db.horizon.find({}).sort({created_at: -1}).explain()`
- Ensure indexes are being used

## Recommended Implementation Order

1. **FIRST**: Deploy with diagnostics and check logs (identifies root cause)
2. **SECOND**: Add caching (quickest win, works regardless of cause)
3. **THIRD**: Add pagination (reduces data transfer)
4. **FOURTH**: If still slow, migrate MongoDB cluster region
5. **FIFTH**: Consider Redis/Memcached for multi-server caching

## Expected Improvements

- **Caching**: 15-20s → ~100-200ms (for cached requests)
- **Pagination**: Reduces data transfer by 50-90%
- **Region Fix**: 15-20s → 1-3s
- **Combined**: Should be < 500ms for most requests
