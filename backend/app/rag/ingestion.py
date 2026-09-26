import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_FILE)

from app.db.database import SessionLocal


DEFAULT_DOCUMENTS_DIR = Path(__file__).resolve().parents[1] / "data" / "documents"
DEFAULT_MODEL = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSIONS = 1024


def split_text(content: str, chunk_size: int = 1000, chunk_overlap: int = 150) -> list[str]:
	"""Split text on word boundaries while preserving a small overlap."""
	if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
		raise ValueError("chunk_size must be positive and overlap must be smaller than chunk_size")

	words = content.split()
	chunks: list[str] = []
	current_words: list[str] = []
	current_length = 0
	overlap_words: list[str] = []

	for word in words:
		added_length = len(word) + (1 if current_words else 0)
		if current_words and current_length + added_length > chunk_size:
			chunks.append(" ".join(current_words))
			overlap_length = 0
			overlap_words = []
			for previous_word in reversed(current_words):
				word_length = len(previous_word) + (1 if overlap_words else 0)
				if overlap_length + word_length > chunk_overlap:
					break
				overlap_words.insert(0, previous_word)
				overlap_length += word_length
			current_words = overlap_words
			current_length = len(" ".join(current_words))

		current_words.append(word)
		current_length += added_length

	if current_words:
		chunks.append(" ".join(current_words))
	return chunks


def create_embedding(client, content: str, model_id: str) -> list[float]:
	response = client.invoke_model(
		modelId=model_id,
		body=json.dumps(
			{
				"inputText": content,
				"dimensions": EMBEDDING_DIMENSIONS,
				"normalize": True,
			}
		),
		contentType="application/json",
		accept="application/json",
	)
	embedding = json.loads(response["body"].read())["embedding"]
	if len(embedding) != EMBEDDING_DIMENSIONS:
		raise ValueError(
			f"Bedrock returned {len(embedding)} dimensions; expected {EMBEDDING_DIMENSIONS}"
		)
	return embedding


def ingest_documents(
	documents_dir: Path,
	model_id: str = DEFAULT_MODEL,
	chunk_size: int = 1000,
	chunk_overlap: int = 150,
	document_name: str | None = None,
) -> int:
	import boto3

	if document_name:
		document_path = documents_dir / document_name
		if document_path.suffix != ".md" or not document_path.is_file():
			raise FileNotFoundError(f"Markdown document not found: {document_path}")
		document_paths = [document_path]
	else:
		document_paths = sorted(documents_dir.glob("*.md"))
	if not document_paths:
		raise FileNotFoundError(f"No markdown files found in {documents_dir}")

	region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
	access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
	secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
	placeholders = {
		"your_aws_region",
		"your_aws_access_key_id",
		"your_aws_secret_access_key",
	}
	if (
		not region
		or not access_key_id
		or not secret_access_key
		or region in placeholders
		or access_key_id in placeholders
		or secret_access_key in placeholders
	):
		raise RuntimeError(
			"AWS_REGION, AWS_ACCESS_KEY_ID, and AWS_SECRET_ACCESS_KEY must be set in "
			f"{ENV_FILE}"
		)

	client = boto3.client(
		"bedrock-runtime",
		region_name=region,
		aws_access_key_id=access_key_id,
		aws_secret_access_key=secret_access_key,
	)
	records: list[dict] = []

	for document_path in document_paths:
		content = document_path.read_text(encoding="utf-8")
		chunks = split_text(content, chunk_size, chunk_overlap)
		for chunk_index, chunk in enumerate(chunks):
			records.append(
				{
					"document_name": document_path.name,
					"content": chunk,
					"embedding": create_embedding(client, chunk, model_id),
					"metadata": {
						"source": str(document_path),
						"chunk_index": chunk_index,
						"total_chunks": len(chunks),
					},
				}
			)

	with SessionLocal.begin() as db:
		for document_path in document_paths:
			db.execute(
				text("DELETE FROM knowledge_chunks WHERE document_name = :document_name"),
				{"document_name": document_path.name},
			)

		insert_query = text(
			"""
			INSERT INTO knowledge_chunks (document_name, content, embedding, metadata)
			VALUES (:document_name, :content, CAST(:embedding AS vector), CAST(:metadata AS jsonb))
			"""
		)
		db.execute(
			insert_query,
			[
				{
					"document_name": record["document_name"],
					"content": record["content"],
					"embedding": "[" + ",".join(map(str, record["embedding"])) + "]",
					"metadata": json.dumps(record["metadata"]),
				}
				for record in records
			],
		)

	return len(records)


def main() -> None:
	parser = argparse.ArgumentParser(description="Embed support documents into pgvector.")
	parser.add_argument(
		"--documents-dir",
		type=Path,
		default=Path(os.environ.get("DOCUMENTS_DIR", DEFAULT_DOCUMENTS_DIR)),
	)
	parser.add_argument(
		"--model-id",
		default=os.environ.get("BEDROCK_EMBEDDING_MODEL", DEFAULT_MODEL),
	)
	parser.add_argument(
		"--document",
		help="Process only this Markdown filename from the documents directory.",
	)
	parser.add_argument("--chunk-size", type=int, default=int(os.environ.get("CHUNK_SIZE", "800")))
	parser.add_argument(
		"--chunk-overlap", type=int, default=int(os.environ.get("CHUNK_OVERLAP", "150"))
	)
	args = parser.parse_args()
	count = ingest_documents(
		args.documents_dir,
		args.model_id,
		args.chunk_size,
		args.chunk_overlap,
		args.document,
	)
	print(f"Inserted {count} knowledge chunks from {args.documents_dir}")


if __name__ == "__main__":
	main()
