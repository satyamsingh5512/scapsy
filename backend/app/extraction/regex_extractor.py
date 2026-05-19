import re
from decimal import Decimal, InvalidOperation
from typing import Any

from bs4 import BeautifulSoup

from app.extraction.contracts import (
    ExtractedField,
    ExtractionContext,
    ExtractionField,
    ExtractionResult,
    ExtractionSchema,
    FieldType,
    score_field_coverage,
)


class RegexHeuristicExtractor:
    extractor_name = "regex_heuristics"

    EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
    PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3,5}\)?[\s.-]?)?\d{3,5}[\s.-]?\d{4}\b")
    URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
    MONEY_RE = re.compile(r"(?:[$€£₹]\s?\d[\d,]*(?:\.\d{1,2})?|\d[\d,]*(?:\.\d{1,2})?\s?(?:USD|EUR|GBP|INR))", re.IGNORECASE)
    ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

    async def extract(self, context: ExtractionContext, schema: ExtractionSchema) -> ExtractionResult:
        text = context.text()
        soup = BeautifulSoup(context.html, "html.parser")
        fields: dict[str, ExtractedField] = {}
        errors: list[str] = []

        for field in schema.fields:
            try:
                extracted = self._extract_field(field, text, soup, context)
                if extracted is not None:
                    fields[field.name] = extracted
            except re.error as exc:
                errors.append(f"{field.name}: invalid regex: {exc}")
            except (InvalidOperation, ValueError) as exc:
                errors.append(f"{field.name}: value normalization failed: {exc}")

        return ExtractionResult(
            extractor_name=self.extractor_name,
            schema_name=schema.name,
            fields=fields,
            confidence=score_field_coverage(fields, schema.name),
            errors=errors,
        )

    def _extract_field(
        self,
        field: ExtractionField,
        text: str,
        soup: BeautifulSoup,
        context: ExtractionContext,
    ) -> ExtractedField | None:
        if field.regex:
            match = re.search(field.regex, text, flags=re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.groupdict().get("value") if match.groupdict() else match.group(1 if match.groups() else 0)
                return self._build_field(field, value, 0.88, "user_regex", match.group(0))

        html_value = self._extract_from_html(field, soup, context)
        if html_value is not None:
            return html_value

        typed_value = self._extract_by_type(field, text)
        if typed_value is not None:
            return typed_value

        keyword_value = self._extract_by_label(field, text)
        if keyword_value is not None:
            return keyword_value

        return None

    def _extract_from_html(
        self,
        field: ExtractionField,
        soup: BeautifulSoup,
        context: ExtractionContext,
    ) -> ExtractedField | None:
        if field.name.lower() in {"title", "page_title"}:
            title = context.title or (soup.title.string.strip() if soup.title and soup.title.string else None)
            if title:
                return self._build_field(field, title, 0.9, "html_title", title)

        meta_names = {field.name.lower(), field.description.lower()}
        for tag in soup.find_all("meta"):
            key = (tag.get("name") or tag.get("property") or "").lower()
            content = tag.get("content")
            if content and key in meta_names:
                return self._build_field(field, content, 0.86, "html_meta", str(tag))
        return None

    def _extract_by_type(self, field: ExtractionField, text: str) -> ExtractedField | None:
        patterns = {
            FieldType.email: self.EMAIL_RE,
            FieldType.phone: self.PHONE_RE,
            FieldType.url: self.URL_RE,
            FieldType.money: self.MONEY_RE,
            FieldType.date: self.ISO_DATE_RE,
        }
        pattern = patterns.get(field.field_type)
        if pattern is None:
            return None
        match = pattern.search(text)
        if not match:
            return None
        return self._build_field(field, match.group(0), 0.82, f"{field.field_type.value}_pattern", match.group(0))

    def _extract_by_label(self, field: ExtractionField, text: str) -> ExtractedField | None:
        escaped_name = re.escape(field.name.replace("_", " "))
        label_re = re.compile(
            rf"(?:{escaped_name}|{re.escape(field.description)})\s*[:\-]\s*(?P<value>[^\n\r|]+)",
            re.IGNORECASE,
        )
        match = label_re.search(text)
        if not match:
            return None
        return self._build_field(field, match.group("value").strip(), 0.72, "label_heuristic", match.group(0))

    def _build_field(
        self,
        field: ExtractionField,
        raw_value: Any,
        confidence: float,
        source: str,
        evidence: str,
    ) -> ExtractedField:
        value = self._normalize_value(field.field_type, raw_value)
        return ExtractedField(
            name=field.name,
            value=value,
            confidence=confidence,
            source=source,
            evidence=evidence[:500],
        )

    def _normalize_value(self, field_type: FieldType, raw_value: Any) -> Any:
        value = str(raw_value).strip()
        if field_type == FieldType.integer:
            return int(re.sub(r"[^\d-]", "", value))
        if field_type == FieldType.number:
            return float(re.sub(r"[^\d.-]", "", value))
        if field_type == FieldType.money:
            amount = re.sub(r"[^\d.]", "", value)
            return {"raw": value, "amount": str(Decimal(amount)) if amount else None}
        if field_type == FieldType.boolean:
            return value.lower() in {"true", "yes", "1", "available", "active"}
        return value
