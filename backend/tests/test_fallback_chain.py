import pytest

from app.extraction.contracts import ExtractedField, ExtractionContext, ExtractionResult, ExtractionSchema
from app.extraction.fallback_chain import ExtractionFallbackChain


class StaticExtractor:
    extractor_name = "static"

    async def extract(self, context: ExtractionContext, schema: ExtractionSchema) -> ExtractionResult:
        return ExtractionResult(
            extractor_name=self.extractor_name,
            schema_name=schema.name,
            fields={
                "title": ExtractedField(
                    name="title",
                    value="Static title",
                    confidence=0.95,
                    source="test",
                )
            },
            confidence=0.95,
        )


@pytest.mark.asyncio
async def test_fallback_chain_stops_on_high_confidence_result() -> None:
    schema = ExtractionSchema.model_validate(
        {
            "name": "test_schema",
            "fields": [{"name": "title", "description": "Title", "required": True}],
        }
    )
    result = await ExtractionFallbackChain(extractors=[StaticExtractor()], confidence_threshold=0.8).extract(
        ExtractionContext(url="https://example.com", html="<p>Hello</p>"),
        schema,
    )
    assert result.confidence >= 0.8
    assert result.data == {"title": "Static title"}
