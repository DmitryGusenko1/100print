"""Replaceable retrieval providers; embeddings require an explicit compatible model."""
from typing import Protocol

class RetrievalProvider(Protocol):
    def search(self, cur, query: str, limit: int = 20): ...

class FullTextProvider:
    def search(self, cur, query, limit=20):
        from app.project_memory import fulltext_search
        return fulltext_search(cur,query,max(1,min(limit,100)))

class VectorProvider:
    def __init__(self, embed, model):
        self.embed, self.model = embed, model

    def search(self, cur, query, limit=20):
        import math
        cur.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector') AS available")
        if not cur.fetchone()['available']: return FullTextProvider().search(cur,query,limit)
        vector=self.embed(query)
        if not vector or any(not math.isfinite(v) for v in vector): raise ValueError('Invalid embedding')
        # Savepoint preserves caller transaction on unsupported vector casts/dimensions.
        cur.execute('SAVEPOINT vector_retrieval')
        try:
            cur.execute('''SELECT m.*,1-(e.embedding::vector <=> %s::vector) AS relevance
                FROM memory_embeddings e JOIN project_memory m ON m.id=e.memory_id
                WHERE e.model=%s AND cardinality(e.embedding)=%s
                ORDER BY e.embedding::vector <=> %s::vector LIMIT %s''',
                (str(vector),self.model,len(vector),str(vector),max(1,min(limit,100))))
            rows=[dict(r) for r in cur.fetchall()]
        except Exception:
            cur.execute('ROLLBACK TO SAVEPOINT vector_retrieval')
            rows=[]
        finally:
            cur.execute('RELEASE SAVEPOINT vector_retrieval')
        return rows or FullTextProvider().search(cur,query,limit)


def search(cur,query,limit=20,provider=None):
    provider=provider or HybridConceptProvider()
    rows=provider.search(cur,query,limit)
    cur.execute('INSERT INTO retrieval_observations(provider,hits) VALUES (%s,%s)',(type(provider).__name__,len(rows)))
    return rows

CONCEPT_MODEL='business-concepts-v1'

def concept_embedding(query):
    from app.project_memory import CONCEPTS, concepts
    selected=concepts(query)
    return [float(key in selected) for key in CONCEPTS]

class HybridConceptProvider:
    """Local multilingual concept embeddings, not neural model embeddings."""
    def search(self,cur,query,limit=20):
        exact=FullTextProvider().search(cur,query,limit)
        if not any(concept_embedding(query)): return exact
        semantic=VectorProvider(concept_embedding,CONCEPT_MODEL).search(cur,query,limit)
        seen={str(row['id']) for row in exact}
        return (exact+[row for row in semantic if str(row['id']) not in seen and row.get('relevance',0)>0])[:max(1,min(limit,100))]


def index_memory(cur,memory_id,text):
    vector=concept_embedding(text)
    if any(vector):
        cur.execute('''INSERT INTO memory_embeddings VALUES (%s,%s,%s)
            ON CONFLICT(memory_id,model) DO UPDATE SET embedding=excluded.embedding''',
            (memory_id,CONCEPT_MODEL,vector))
