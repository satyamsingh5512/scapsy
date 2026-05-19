from app.extraction.schema_factory import default_schema, schema_from_job_payload


def test_default_schema_is_valid() -> None:
    schema = default_schema("Extract emails and links")
    assert schema.name == "default_page_intelligence"
    assert {field.name for field in schema.fields} >= {"title", "email", "phone", "url"}


def test_schema_from_payload_uses_provided_fields() -> None:
    schema = schema_from_job_payload(
        {
            "name": "company_scan",
            "description": "Company scan",
            "fields": [
                {
                    "name": "company",
                    "description": "Company name",
                    "field_type": "organization",
                    "required": True,
                }
            ],
        }
    )
    assert schema.name == "company_scan"
    assert schema.fields[0].name == "company"
    assert schema.fields[0].required is True
