import os

import boto3
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.rag.ingestion import DEFAULT_MODEL, create_embedding


def retrieve_relevant_chunks(
    db: Session,
    query: str,
    model_id: str = DEFAULT_MODEL,
    limit: int = 5,
    max_distance: float = 0.65,
) -> list[dict[str, str]]:
    """Embed a query and return the closest knowledge chunks by cosine distance."""
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not region or not access_key_id or not secret_access_key:
        raise RuntimeError("AWS credentials are required for knowledge retrieval")

    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
    )
    embedding = create_embedding(client, query, model_id)
    embedding_value = "[" + ",".join(map(str, embedding)) + "]"

    rows = db.execute(
        text(
            """
            SELECT document_name, content, metadata,
                   embedding <=> CAST(:embedding AS vector) AS distance
            FROM knowledge_chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """
        ),
        {"embedding": embedding_value, "limit": limit},
    ).mappings().all()

    relevant_rows = [
        {
            "document_name": row["document_name"],
            "content": row["content"],
            "metadata": row["metadata"],
        }
        for row in rows
        if row["distance"] <= max_distance
    ]

    print(f"Retrieved {len(relevant_rows)} chunks for query: {query!r}")
    if not relevant_rows:
        print("No RAG chunks matched the query within the configured distance threshold.")
    else:
        for index, chunk in enumerate(relevant_rows, start=1):
            print(
                f"\n--- RAG Chunk {index} | {chunk['document_name']} ---\n"
                f"{chunk['content']}"
            )

    return relevant_rows