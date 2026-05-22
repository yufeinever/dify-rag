from __future__ import annotations

import time
import os
from threading import Lock
from typing import Any, Optional, Tuple, Union
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer


EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
RERANK_MODEL = "BAAI/bge-reranker-base"
SERVICE_KEY = os.getenv("LOCAL_MODELS_API_KEY", "local-dify-models")
CACHE_ROOT = Path(
    os.getenv(
        "LOCAL_MODELS_CACHE_ROOT",
        str(Path(__file__).resolve().parents[1] / "docker" / "volumes" / "local-models" / "huggingface"),
    )
)
LOCAL_MODEL_PATHS = {
    EMBEDDING_MODEL: CACHE_ROOT
    / "models--BAAI--bge-small-zh-v1.5"
    / "snapshots"
    / "7999e1d3359715c523056ef9478215996d62a620",
    RERANK_MODEL: CACHE_ROOT
    / "models--BAAI--bge-reranker-base"
    / "snapshots"
    / "2cfc18c9415c912f9d8155881c133215df768a70",
}

app = FastAPI(title="Dify Local Embedding and Rerank Service")

_embedding_tokenizer: Optional[Any] = None
_embedding_model: Optional[Any] = None
_rerank_tokenizer: Optional[Any] = None
_rerank_model: Optional[Any] = None
_model_load_lock = Lock()


@app.on_event("startup")
def preload_models() -> None:
    _get_embedding_components()
    _get_rerank_components()


class EmbeddingRequest(BaseModel):
    model: Optional[str] = None
    input: Union[str, list[str]]
    encoding_format: Optional[str] = None


class RerankRequest(BaseModel):
    model: Optional[str] = None
    query: str
    documents: list[Any] = Field(default_factory=list)
    top_n: Optional[int] = None


def _check_auth(authorization: Optional[str]) -> None:
    if not authorization:
        return

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token == SERVICE_KEY:
        return
    raise HTTPException(status_code=401, detail="Invalid bearer token")


def _get_embedding_components() -> Tuple[Any, Any]:
    global _embedding_tokenizer, _embedding_model
    with _model_load_lock:
        if _embedding_model is None:
            model_path = LOCAL_MODEL_PATHS[EMBEDDING_MODEL]
            _embedding_tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
            _embedding_model = AutoModel.from_pretrained(str(model_path), local_files_only=True)
            _embedding_model.eval()
    return _embedding_tokenizer, _embedding_model


def _get_rerank_components() -> Tuple[Any, Any]:
    global _rerank_tokenizer, _rerank_model
    with _model_load_lock:
        if _rerank_model is None:
            model_path = LOCAL_MODEL_PATHS[RERANK_MODEL]
            _rerank_tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
            _rerank_model = AutoModelForSequenceClassification.from_pretrained(str(model_path), local_files_only=True)
            _rerank_model.eval()
    return _rerank_tokenizer, _rerank_model


def _mean_pool(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    summed = torch.sum(last_hidden_state * mask, dim=1)
    counts = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / counts


def _document_to_text(document: Any) -> str:
    if isinstance(document, str):
        return document
    if isinstance(document, dict):
        content = document.get("content", document.get("text", document))
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif isinstance(item, str):
                    parts.append(item)
            return " ".join(part for part in parts if part)
        return str(content)
    return str(document)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/models")
def models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {"id": "bge-small-zh-v1.5", "object": "model", "owned_by": "local"},
            {"id": "bge-reranker-base", "object": "model", "owned_by": "local"},
        ],
    }


@app.post("/v1/embeddings")
def embeddings(request: EmbeddingRequest, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    _check_auth(authorization)
    started = time.perf_counter()
    texts = [request.input] if isinstance(request.input, str) else request.input
    texts = [str(text) for text in texts]

    tokenizer, model = _get_embedding_components()
    encoded = tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt")
    with torch.no_grad():
        output = model(**encoded)
        vectors = _mean_pool(output.last_hidden_state, encoded["attention_mask"])
        vectors = F.normalize(vectors, p=2, dim=1).cpu().tolist()
    data = [
        {"object": "embedding", "index": index, "embedding": vector}
        for index, vector in enumerate(vectors)
    ]

    token_estimate = sum(max(1, len(text) // 2) for text in texts)
    return {
        "object": "list",
        "model": request.model or "bge-small-zh-v1.5",
        "data": data,
        "usage": {
            "prompt_tokens": token_estimate,
            "total_tokens": token_estimate,
            "latency": round(time.perf_counter() - started, 6),
        },
    }


@app.post("/v1/rerank")
def rerank(request: RerankRequest, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    _check_auth(authorization)
    documents = [_document_to_text(document) for document in request.documents]
    if not documents:
        return {"model": request.model or "bge-reranker-base", "results": []}

    tokenizer, model = _get_rerank_components()
    pairs = [(request.query, document) for document in documents]
    encoded = tokenizer(
        pairs,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    )
    with torch.no_grad():
        logits = model(**encoded).logits
        scores = logits.view(-1).cpu().tolist()
    ranked = sorted(
        (
            {"index": index, "document": documents[index], "relevance_score": float(score)}
            for index, score in enumerate(scores)
        ),
        key=lambda item: item["relevance_score"],
        reverse=True,
    )
    if request.top_n is not None:
        ranked = ranked[: request.top_n]

    return {"model": request.model or "bge-reranker-base", "results": ranked}
