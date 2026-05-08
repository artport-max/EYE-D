import os
import time

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest


class DBTester:
    """Vector DB 저장 및 검색 검증 도구."""

    def __init__(self, client=None):
        self.client = client

    def connect(self, host=None, port=None, prefer_grpc=False, **kwargs):
        host = host or os.getenv('QDRANT_HOST', 'localhost')
        port = port or int(os.getenv('QDRANT_PORT', '6333'))
        self.client = QdrantClient(host=host, port=port, prefer_grpc=prefer_grpc)
        return True

    def collection_exists(self, collection_name):
        if self.client is None:
            raise RuntimeError('DB client is not connected')
        try:
            self.client.get_collection(collection_name=collection_name)
            return True
        except Exception:
            return False

    def validate_insert(self, collection_name, records, vector_size=128):
        if self.client is None:
            self.connect()

        if not self.collection_exists(collection_name):
            self.client.recreate_collection(
                collection_name=collection_name,
                vectors_config=rest.VectorParams(size=vector_size, distance=rest.Distance.COSINE),
            )

        points = []
        for idx, record in enumerate(records):
            point_id = record.get('id', idx)
            point_vector = record['vector']
            payload = record.get('payload', {})
            points.append(rest.PointStruct(id=point_id, vector=point_vector, payload=payload))

        self.client.upsert(collection_name=collection_name, points=points)
        return True

    def validate_search(self, collection_name, query_vector, top_k=10):
        if self.client is None:
            self.connect()

        if not self.collection_exists(collection_name):
            raise RuntimeError(f'collection {collection_name} does not exist')

        start_time = time.time()
        search_result = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            with_payload=False,
        )
        latency_ms = (time.time() - start_time) * 1000

        hits = [
            {
                'id': hit.id,
                'score': float(hit.score) if hasattr(hit, 'score') else None,
            }
            for hit in search_result
        ]

        return {
            'hits': hits,
            'latency_ms': latency_ms,
            'top_k': top_k,
            'hit_count': len(hits),
        }

    def validate_index(self, collection_name):
        if self.client is None:
            self.connect()
        return self.collection_exists(collection_name)
