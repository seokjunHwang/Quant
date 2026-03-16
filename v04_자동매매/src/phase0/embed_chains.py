"""
Phase 0: 로직체인을 벡터화하여 ChromaDB에 저장.

Embedding: sentence-transformers (all-MiniLM-L6-v2) — 로컬, 무료
Vector DB: ChromaDB — 로컬, 무료
"""

import json
import logging
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from src.phase0.schema import LogicChain
from src.utils.config import DATA_DIR

logger = logging.getLogger(__name__)

CHAINS_DIR = DATA_DIR / "logic_chains"
CHROMA_DIR = DATA_DIR / "chromadb"
COLLECTION_NAME = "logic_chains"

# Local embedding model (free, ~80MB)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def get_chroma_client() -> chromadb.PersistentClient:
    """ChromaDB 클라이언트 (persistent, 로컬 파일)."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection(client: chromadb.PersistentClient | None = None):
    """로직체인 컬렉션 가져오기 (없으면 생성)."""
    if client is None:
        client = get_chroma_client()

    ef = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def load_chains_from_json(path: Path | None = None) -> list[LogicChain]:
    """JSON 파일에서 로직체인 로드."""
    if path is None:
        path = CHAINS_DIR / "all_chains.json"

    if not path.exists():
        logger.error(f"Chain file not found: {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return [LogicChain.from_dict(item) for item in raw]


def embed_and_store(chains: list[LogicChain] | None = None) -> int:
    """
    로직체인을 벡터화하여 ChromaDB에 저장.

    Returns:
        저장된 체인 수
    """
    if chains is None:
        chains = load_chains_from_json()

    if not chains:
        logger.warning("No chains to embed")
        return 0

    collection = get_collection()

    # Prepare batch data
    ids = [c.chain_id for c in chains]
    documents = [c.to_embedding_text() for c in chains]
    metadatas = [
        {
            "category": c.category,
            "event": c.event,
            "causal_path": c.causal_path,
            "intensity": c.intensity,
            "time_horizon": c.time_horizon,
            "reaction_speed": c.reaction_speed,
            "beneficiary_sectors": json.dumps(c.beneficiary_sectors, ensure_ascii=False),
            "victim_sectors": json.dumps(c.victim_sectors, ensure_ascii=False),
            "pre_signals": json.dumps(c.pre_signals, ensure_ascii=False),
            "historical_accuracy": c.historical_accuracy or 0.0,
            "source": c.source,
        }
        for c in chains
    ]

    # Upsert in batches of 100
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        collection.upsert(
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end],
        )
        logger.info(f"Upserted batch {i//batch_size + 1}: {end - i} chains")

    total = collection.count()
    logger.info(f"ChromaDB now contains {total} chains")
    return total


def search_chains(
    query: str,
    n_results: int = 5,
    reaction_speed: str | None = "즉각반응",
    category: str | None = None,
) -> list[dict]:
    """
    벡터 유사도 기반 로직체인 검색.

    Args:
        query: 검색 텍스트 (예: "국채수익률 하락, 달러인덱스 약세, 금 선물 급증")
        n_results: 반환할 결과 수
        reaction_speed: 필터 (단타 우선 = "즉각반응")
        category: 카테고리 필터 (optional)

    Returns:
        매칭된 체인 리스트 (유사도 점수 포함)
    """
    collection = get_collection()

    where_filter = {}
    if reaction_speed:
        where_filter["reaction_speed"] = reaction_speed
    if category:
        where_filter["category"] = category

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where_filter if where_filter else None,
    )

    matched = []
    if results and results["ids"]:
        for i, chain_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0.0

            # Parse JSON fields back
            beneficiary = json.loads(meta.get("beneficiary_sectors", "[]"))
            victim = json.loads(meta.get("victim_sectors", "[]"))
            pre_signals = json.loads(meta.get("pre_signals", "[]"))

            matched.append({
                "chain_id": chain_id,
                "event": meta.get("event", ""),
                "causal_path": meta.get("causal_path", ""),
                "beneficiary_sectors": beneficiary,
                "victim_sectors": victim,
                "pre_signals": pre_signals,
                "intensity": meta.get("intensity", ""),
                "reaction_speed": meta.get("reaction_speed", ""),
                "similarity": round(1 - distance, 4),  # cosine distance → similarity
                "historical_accuracy": meta.get("historical_accuracy", 0.0),
            })

    return matched


def add_new_chain(chain: LogicChain) -> None:
    """신규 로직체인 1개를 DB에 추가. (Step 2 매칭 실패 시 사용)"""
    collection = get_collection()
    collection.upsert(
        ids=[chain.chain_id],
        documents=[chain.to_embedding_text()],
        metadatas=[{
            "category": chain.category,
            "event": chain.event,
            "causal_path": chain.causal_path,
            "intensity": chain.intensity,
            "time_horizon": chain.time_horizon,
            "reaction_speed": chain.reaction_speed,
            "beneficiary_sectors": json.dumps(chain.beneficiary_sectors, ensure_ascii=False),
            "victim_sectors": json.dumps(chain.victim_sectors, ensure_ascii=False),
            "pre_signals": json.dumps(chain.pre_signals, ensure_ascii=False),
            "historical_accuracy": chain.historical_accuracy or 0.0,
            "source": chain.source,
        }],
    )
    logger.info(f"Added new chain: {chain.chain_id} - {chain.event}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Load from JSON and store in ChromaDB
    chains = load_chains_from_json()
    if chains:
        embed_and_store(chains)

        # Test search
        print("\n--- Test Search: '국채수익률 하락 달러 약세' ---")
        results = search_chains("국채수익률 하락, 달러인덱스 약세, 금 선물 거래량 급증")
        for r in results:
            print(f"  [{r['similarity']:.3f}] {r['event']} → {r['causal_path']}")
    else:
        print("No chains found. Run generate_chains.py first.")
