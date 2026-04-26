from lifeprism.config import settings
from lifeprism.repository import QueryOptions,map_cache_repository
app = "msedge"
title = "火山引擎控制台"
result,_ = map_cache_repository.query_single_purpose_map_cache(QueryOptions(filters = {"app": app},fields=["category_id"]))
print(result)