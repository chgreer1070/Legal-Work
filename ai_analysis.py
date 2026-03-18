"""
AI-powered document analysis using the Claude API.

Provides:
  - summarize()          – Generate a concise summary of document text
  - extract_metadata()   – Extract structured metadata (parties, dates, clauses, etc.)
  - classify_document()  – Classify document type and assess key attributes
  - analyze_document()   – Run all three analyses in one call
"""

import json
import os
from typing import Optional

import anthropic

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    """Lazy-init the Anthropic client (uses ANTHROPIC_API_KEY env var)."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


MODEL = "claude-opus-4-6"


# ── Summarization ────────────────────────────────────────────────────────────


def summarize(text: str, context: str = "") -> dict:
    """
    Return a structured summary of the document text.

    Returns dict with keys: summary, key_points (list[str])
    """
    client = _get_client()

    system = (
        "You are a legal document analyst. Produce clear, accurate summaries. "
        "Return valid JSON with keys: \"summary\" (string, 2-4 sentences) "
        "and \"key_points\" (array of strings, 3-7 bullet points)."
    )
    user_msg = f"Summarize the following document.\n\n"
    if context:
        user_msg += f"Context: {context}\n\n"
    user_msg += f"Document text:\n{text[:50000]}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "key_points": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["summary", "key_points"],
                    "additionalProperties": False,
                },
            }
        },
    )

    result_text = next(b.text for b in response.content if b.type == "text")
    return json.loads(result_text)


# ── Metadata Extraction ─────────────────────────────────────────────────────


def extract_metadata(text: str, source_filename: str = "") -> dict:
    """
    Extract structured metadata from document text.

    Returns dict with keys: document_type, parties, dates, references,
    monetary_values, obligations, jurisdictions
    """
    client = _get_client()

    system = (
        "You are an expert legal metadata extractor. Analyze the document and "
        "extract structured metadata. Return valid JSON with these keys:\n"
        "- \"document_type\": string (e.g. \"email\", \"contract\", \"memo\", \"invoice\", \"report\", \"presentation\", \"other\")\n"
        "- \"parties\": array of strings (people and organizations mentioned)\n"
        "- \"dates\": array of objects with \"date\" and \"context\" keys\n"
        "- \"references\": array of strings (case numbers, file refs, IDs)\n"
        "- \"monetary_values\": array of objects with \"amount\" and \"context\" keys\n"
        "- \"obligations\": array of strings (action items, deadlines, commitments)\n"
        "- \"jurisdictions\": array of strings (any legal jurisdictions mentioned)\n"
        "Use empty arrays when a field has no matches."
    )
    user_msg = ""
    if source_filename:
        user_msg += f"Source file: {source_filename}\n\n"
    user_msg += f"Document text:\n{text[:50000]}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "document_type": {"type": "string"},
                        "parties": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "dates": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "date": {"type": "string"},
                                    "context": {"type": "string"},
                                },
                                "required": ["date", "context"],
                                "additionalProperties": False,
                            },
                        },
                        "references": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "monetary_values": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "amount": {"type": "string"},
                                    "context": {"type": "string"},
                                },
                                "required": ["amount", "context"],
                                "additionalProperties": False,
                            },
                        },
                        "obligations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "jurisdictions": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "document_type",
                        "parties",
                        "dates",
                        "references",
                        "monetary_values",
                        "obligations",
                        "jurisdictions",
                    ],
                    "additionalProperties": False,
                },
            }
        },
    )

    result_text = next(b.text for b in response.content if b.type == "text")
    return json.loads(result_text)


# ── Classification ───────────────────────────────────────────────────────────


def classify_document(text: str, source_filename: str = "") -> dict:
    """
    Classify the document and assess key attributes.

    Returns dict with keys: category, subcategory, confidence,
    sensitivity, priority, tags, brief_description
    """
    client = _get_client()

    system = (
        "You are a legal document classifier. Classify the document and assess "
        "its attributes. Return valid JSON with these keys:\n"
        "- \"category\": string (e.g. \"correspondence\", \"contract\", \"litigation\", "
        "\"corporate\", \"regulatory\", \"financial\", \"other\")\n"
        "- \"subcategory\": string (more specific type)\n"
        "- \"confidence\": number between 0 and 1\n"
        "- \"sensitivity\": string (\"public\", \"internal\", \"confidential\", \"privileged\")\n"
        "- \"priority\": string (\"low\", \"medium\", \"high\", \"urgent\")\n"
        "- \"tags\": array of strings (relevant topic tags)\n"
        "- \"brief_description\": string (one-sentence description)"
    )
    user_msg = ""
    if source_filename:
        user_msg += f"Source file: {source_filename}\n\n"
    user_msg += f"Document text:\n{text[:50000]}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "subcategory": {"type": "string"},
                        "confidence": {"type": "number"},
                        "sensitivity": {"type": "string"},
                        "priority": {"type": "string"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "brief_description": {"type": "string"},
                    },
                    "required": [
                        "category",
                        "subcategory",
                        "confidence",
                        "sensitivity",
                        "priority",
                        "tags",
                        "brief_description",
                    ],
                    "additionalProperties": False,
                },
            }
        },
    )

    result_text = next(b.text for b in response.content if b.type == "text")
    return json.loads(result_text)


# ── Combined Analysis ────────────────────────────────────────────────────────


def analyze_document(text: str, source_filename: str = "") -> dict:
    """
    Run summarization, metadata extraction, and classification together.

    Returns dict with keys: summary, metadata, classification
    """
    context = f"from file: {source_filename}" if source_filename else ""

    return {
        "summary": summarize(text, context),
        "metadata": extract_metadata(text, source_filename),
        "classification": classify_document(text, source_filename),
    }
