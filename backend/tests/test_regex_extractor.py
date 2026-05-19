import pytest

from app.extraction.contracts import ExtractionContext, ExtractionField, ExtractionSchema, FieldType
from app.extraction.regex_extractor import RegexHeuristicExtractor


@pytest.mark.asyncio
async def test_regex_extractor_extracts_common_contact_fields() -> None:
    schema = ExtractionSchema(
        name="contact",
        fields=[
            ExtractionField(name="email", description="Email", field_type=FieldType.email),
            ExtractionField(name="phone", description="Phone", field_type=FieldType.phone),
            ExtractionField(name="title", description="Title", field_type=FieldType.text),
        ],
    )
    context = ExtractionContext(
        url="https://example.com",
        title="Example Intelligence",
        html="<html><title>Example Intelligence</title><body>Contact ops@example.com or +1 415 555 1212</body></html>",
    )
    result = await RegexHeuristicExtractor().extract(context, schema)
    assert result.data["email"] == "ops@example.com"
    assert "555" in result.data["phone"]
    assert result.data["title"] == "Example Intelligence"
